from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
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

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()
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
async def chat(
    q: str = Form(...),
    k: int = Form(5),
    attachments: List[UploadFile] = File([]),
):
    return await chat_stream(q, k, attachments)


@app.get("/api/chat")
async def chat_get(q: str, k: int = 5):
    return await chat_stream(q, k, [])


async def chat_stream(
    q: str,
    k: int,
    attachments: List[UploadFile],
):
    attachment_texts: List[str] = []
    attachment_sources: List[Dict] = []
    for f in attachments:
        if f.content_type != "application/pdf":
            continue
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
