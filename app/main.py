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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from uuid import uuid4
import asyncio
from pydantic import BaseModel
import os
import json
from dotenv import load_dotenv
from typing import Dict, List
from io import BytesIO
from pypdf import PdfReader
from langdetect import detect

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from .rag import build_context
from .sse_utils import sse_word_buffer
from .app_logging import init_logging
from .routers import admin_ingest_api, auth_api

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - openai optional
    OpenAI = None  # type: ignore

load_dotenv()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "tmp/uploads")
UPLOAD_TTL = int(os.getenv("UPLOAD_TTL", "3600"))
UPLOAD_MAX_SIZE = int(os.getenv("UPLOAD_MAX_SIZE", str(5 * 1024 * 1024)))
UPLOAD_MAX_FILES = int(os.getenv("UPLOAD_MAX_FILES", "5"))
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
init_logging(app)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
# Optional CORS for admin UI
admin_ui_origins = os.getenv("ADMIN_UI_ORIGINS")
if admin_ui_origins:
    origins = [o.strip() for o in admin_ui_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.include_router(admin_ingest_api.router)
app.include_router(auth_api.router)
 
# Expose Prometheus metrics
Instrumentator().instrument(app).expose(
    app, include_in_schema=False, endpoint="/api/metrics"
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


def _answer_with_context(question: str, context: str) -> tuple[str, bool]:
    """Generate an answer given a question and context using the LLM if available."""
    lang = os.getenv("OPENAI_LANG")
    if not lang:
        try:
            lang = detect(question)
        except Exception:  # pragma: no cover - detection optional
            lang = None
    lang_instruction = (
        f"Reply in {lang}." if lang else "Reply in the same language as the question."
    )
    if client:
        try:  # pragma: no cover - openai optional
            base_prompt = "Answer the user's question using the supplied context."
            custom_prompt = os.getenv("SYSTEM_PROMPT")
            system_prompt = f"{custom_prompt} {base_prompt}" if custom_prompt else base_prompt
            system_prompt = f"{system_prompt} {lang_instruction}"
            completion = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": f"Context:\n{context}\n\nQuestion:\n{question}",
                    },
                ],
            )
            answer = completion.choices[0].message["content"].strip()
            return answer, True
        except Exception:  # pragma: no cover - openai optional
            pass
    answer = context or f"You asked: {question}"
    return answer, False

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
        "UPLOAD_MAX_SIZE": UPLOAD_MAX_SIZE,
        "UPLOAD_MAX_FILES": UPLOAD_MAX_FILES,
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
    context, sources = build_context(req.q, req.k)
    answer, used_llm = _answer_with_context(req.q, context)
    return {"answer": answer, "sources": sources, "used_llm": used_llm}


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
    return await chat_stream(request, q, k, files, json.loads(attachments))


@app.get("/api/chat")
@limiter.limit("5/minute")
async def chat_get(request: Request, q: str, k: int = 5, sessionId: str = ""):
    if len(q) > CHAT_MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail="Message too long")
    if sessionId and len(sessionId) > SESSION_ID_MAX_LENGTH:
        raise HTTPException(status_code=400, detail="Invalid sessionId")
    return await chat_stream(request, q, k, [], [])


async def chat_stream(
    request: Request,
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

    usage: Dict = {}
    context = ""
    sources: List[Dict] = []

    async def token_iter():
        nonlocal usage, context, sources
        context_db, sources_db = build_context(combined_q, k)
        if attachment_context:
            context = attachment_context + ("\n\n" + context_db if context_db else "")
            sources = attachment_sources + sources_db
        else:
            context = context_db
            sources = sources_db
        if client:
            try:
                lang = os.getenv("OPENAI_LANG")
                if not lang:
                    try:
                        lang = detect(q)
                    except Exception:  # pragma: no cover - detection optional
                        lang = None
                lang_instruction = (
                    f"Reply in {lang}." if lang else "Reply in the same language as the question."
                )
                base_prompt = "Answer the user's question using the supplied context."
                custom_prompt = os.getenv("SYSTEM_PROMPT")
                system_prompt = f"{custom_prompt} {base_prompt}" if custom_prompt else base_prompt
                system_prompt = f"{system_prompt} {lang_instruction}"
                completion = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": f"Context:\n{context}\n\nQuestion:\n{q}",
                        },
                    ],
                    stream=True,
                )
                for chunk in completion:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        token = getattr(delta, "content", None)
                        if token:
                            yield token
                    if getattr(chunk, "usage", None):
                        u = chunk.usage
                        usage = {
                            "prompt_tokens": u.prompt_tokens,
                            "completion_tokens": u.completion_tokens,
                            "total_tokens": u.total_tokens,
                        }
            except Exception:
                answer = context or f"You asked: {q}"
                for token in answer.split():
                    yield token
                n = len(answer.split())
                usage = {
                    "prompt_tokens": 0,
                    "completion_tokens": n,
                    "total_tokens": n,
                }
        else:
            answer = context or f"You asked: {q}"
            for token in answer.split():
                yield token
            n = len(answer.split())
            usage = {
                "prompt_tokens": 0,
                "completion_tokens": n,
                "total_tokens": n,
            }

    async def event_stream():
        try:
            async for chunk in sse_word_buffer(token_iter()):
                if await request.is_disconnected():
                    break
                yield chunk
            if sources:
                yield "event: sources\n" + "data: " + json.dumps(sources, ensure_ascii=False) + "\n\n"
            yield "event: done\n" + "data: " + json.dumps({"usage": usage}) + "\n\n"
        except Exception as e:
            msg = str(e).replace("\n", " ")
            yield f"event: error\ndata: {msg}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

app.mount(
    "/",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True),
    name="static",
)
