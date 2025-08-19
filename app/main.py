from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks,
    Form,
    Request,
)
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
import asyncio
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import os
import json
from dotenv import load_dotenv
from typing import Dict, List
from io import BytesIO
from pypdf import PdfReader

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .rag import build_context

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - openai optional
    OpenAI = None  # type: ignore

load_dotenv()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "tmp/uploads")
UPLOAD_TTL = int(os.getenv("UPLOAD_TTL", "3600"))
UPLOAD_MAX_SIZE = int(os.getenv("UPLOAD_MAX_SIZE", str(5 * 1024 * 1024)))
UPLOAD_ALLOWED_MIME_TYPES = os.getenv("UPLOAD_ALLOWED_MIME_TYPES", "application/pdf").split(",")

CHAT_MAX_MESSAGE_LENGTH = int(os.getenv("CHAT_MAX_MESSAGE_LENGTH", "5000"))
SESSION_ID_MAX_LENGTH = int(os.getenv("SESSION_ID_MAX_LENGTH", "64"))

os.makedirs(UPLOAD_DIR, exist_ok=True)
 

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


limiter = Limiter(key_func=get_client_ip)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount(
    "/",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True),
    name="static",
)

client = OpenAI() if (OpenAI and os.getenv("OPENAI_API_KEY")) else None


async def remove_file_after_ttl(path: str, ttl: int) -> None:
    await asyncio.sleep(ttl)
    try:
        os.remove(path)
    except OSError:
        pass


class AskRequest(BaseModel):
    q: str
    k: int = 5

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/config")
async def config():
    return {
        "BRAND_NAME": os.getenv("BRAND_NAME", "PDF Knowledge Kit"),
        "POWERED_BY_LABEL": os.getenv(
            "POWERED_BY_LABEL", "Powered by PDF Knowledge Kit"
        ),
        "LOGO_URL": os.getenv("LOGO_URL", ""),
    }


@app.post("/api/upload")
async def upload(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
):
    if file.content_type not in UPLOAD_ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")
    contents = await file.read()
    if len(contents) > UPLOAD_MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
    filename = f"{uuid4().hex}-{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(contents)
    background_tasks.add_task(remove_file_after_ttl, file_path, UPLOAD_TTL)
    url = f"/uploads/{filename}"
    return {"url": url}


@app.post("/api/ask")
async def ask(req: AskRequest):
    _, results = build_context(req.q, req.k)
    return {"results": results}


@app.post("/api/chat")
@limiter.limit("5/minute")
async def chat(
    request: Request,
    q: str = Form(...),
    k: int = Form(5),
    attachments: str = Form("[]"),
    sessionId: str = Form(...),
    files: List[UploadFile] = File([]),
):
    if len(q) > CHAT_MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail="Message too long")
    if len(sessionId) > SESSION_ID_MAX_LENGTH:
        raise HTTPException(status_code=400, detail="Invalid sessionId")
    for f in files:
        if f.content_type not in UPLOAD_ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=400, detail="Invalid file type")
    return await chat_stream(q, k, files, json.loads(attachments))


@app.get("/api/chat")
@limiter.limit("5/minute")
async def chat_get(request: Request, q: str, k: int = 5, sessionId: str = ""):
    if len(q) > CHAT_MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail="Message too long")
    if sessionId and len(sessionId) > SESSION_ID_MAX_LENGTH:
        raise HTTPException(status_code=400, detail="Invalid sessionId")
    return await chat_stream(q, k, [], [])


async def chat_stream(
    q: str,
    k: int,
    files: List[UploadFile],
    attachments_meta: List[Dict],
):
    attachment_texts: List[str] = []
    attachment_sources: List[Dict] = []
    for f in files:
        if f.content_type not in UPLOAD_ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=400, detail="Invalid file type")
        data = await f.read()
        reader = PdfReader(BytesIO(data))
        text = "".join(page.extract_text() or "" for page in reader.pages)
        attachment_texts.append(text)
        attachment_sources.append(
            {
                "path": f.filename,
                "chunk_index": None,
                "content": text,
                "distance": None,
            }
        )

    for item in attachments_meta:
        url = item.get("url")
        name = item.get("name", url)
        if not url:
            continue
        file_path = os.path.join(UPLOAD_DIR, os.path.basename(url))
        try:
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                text = "".join(page.extract_text() or "" for page in reader.pages)
            attachment_texts.append(text)
            attachment_sources.append(
                {
                    "path": name,
                    "chunk_index": None,
                    "content": text,
                    "distance": None,
                }
            )
        except OSError:
            continue
    attachment_context = "\n\n".join(attachment_texts)
    combined_q = q if not attachment_context else f"{q}\n\n{attachment_context}"

    async def event_gen():
        try:
            context_db, sources = build_context(combined_q, k)
            if attachment_context:
                context = attachment_context + ("\n\n" + context_db if context_db else "")
                sources = attachment_sources + sources
            else:
                context = context_db
            usage: Dict = {}
            if client:
                try:
                    completion = client.chat.completions.create(
                        model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                        messages=[
                            {
                                "role": "system",
                                "content": "Responda à pergunta com base no contexto fornecido.",
                            },
                            {
                                "role": "user",
                                "content": f"Contexto:\n{context}\n\nPergunta:\n{q}",
                            },
                        ],
                        stream=True,
                    )
                    for chunk in completion:
                        if chunk.choices:
                            delta = chunk.choices[0].delta
                            token = getattr(delta, "content", None)
                            if token:
                                yield {"event": "token", "data": token}
                        if getattr(chunk, "usage", None):
                            u = chunk.usage
                            usage = {
                                "prompt_tokens": u.prompt_tokens,
                                "completion_tokens": u.completion_tokens,
                                "total_tokens": u.total_tokens,
                            }
                except Exception:
                    answer = context or f"Você perguntou: {q}"
                    for token in answer.split():
                        yield {"event": "token", "data": token}
                    n = len(answer.split())
                    usage = {
                        "prompt_tokens": 0,
                        "completion_tokens": n,
                        "total_tokens": n,
                    }
            else:
                answer = context or f"Você perguntou: {q}"
                for token in answer.split():
                    yield {"event": "token", "data": token}
                n = len(answer.split())
                usage = {
                    "prompt_tokens": 0,
                    "completion_tokens": n,
                    "total_tokens": n,
                }
            yield {"event": "sources", "data": json.dumps(sources)}
            yield {"event": "done", "data": json.dumps({"usage": usage})}
        except Exception as e:
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_gen())
