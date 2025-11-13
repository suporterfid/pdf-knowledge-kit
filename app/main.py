"""FastAPI application wiring for PDF Knowledge Kit.

This module bootstraps the HTTP API used by the project:

- Configures logging, CORS (optional for the admin UI), Prometheus metrics
  and rate limiting.
- Serves static uploads and exposes endpoints for health/config, file upload,
  question answering (RAG), and chat streaming.
- Integrates optional OpenAI responses when an API key is configured, falling
  back to deterministic answers based on retrieved context otherwise.

The code is structured to be readable for new contributors: each route has a
short docstring and helper functions explain non-obvious details (e.g., LLM
language handling, upload limits, SSE pipeline).
"""

import asyncio
import json
import logging
import os
from io import BytesIO
from typing import Annotated
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langdetect import detect
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from pypdf import PdfReader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .__version__ import __build_date__, __commit_sha__, __version__
from .app_logging import init_logging
from .core.tenant_middleware import TenantContextMiddleware
from .rag import build_context
from .routers import (
    admin_ingest_api,
    agents,
    auth_api,
    conversations,
    feedback_api,
    tenant_accounts,
    webhooks,
)
from .sse_utils import sse_word_buffer

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - openai optional
    OpenAI = None  # type: ignore

load_dotenv()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "tmp/uploads")
UPLOAD_TTL = int(os.getenv("UPLOAD_TTL", "3600"))
UPLOAD_MAX_SIZE = int(os.getenv("UPLOAD_MAX_SIZE", str(5 * 1024 * 1024)))
UPLOAD_MAX_FILES = int(os.getenv("UPLOAD_MAX_FILES", "5"))
UPLOAD_ALLOWED_MIME_TYPES = os.getenv(
    "UPLOAD_ALLOWED_MIME_TYPES", "application/pdf"
).split(",")

logger = logging.getLogger(__name__)

CHAT_MAX_MESSAGE_LENGTH = int(os.getenv("CHAT_MAX_MESSAGE_LENGTH", "5000"))
SESSION_ID_MAX_LENGTH = int(os.getenv("SESSION_ID_MAX_LENGTH", "64"))

SingleUpload = Annotated[UploadFile, File(...)]
MultiUpload = Annotated[list[UploadFile], File([])]

os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_client_ip(request: Request) -> str:
    """Extract a best-effort client IP for rate limiting.

    Prefer ``X-Forwarded-For`` (first hop) if present, otherwise use the
    socket peer address. This function is used by SlowAPI to key the limiter.
    """
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
app.add_middleware(TenantContextMiddleware)
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
app.include_router(feedback_api.router)
app.include_router(agents.router)
app.include_router(conversations.router)
app.include_router(tenant_accounts.router)
app.include_router(webhooks.router)

# Expose Prometheus metrics
Instrumentator().instrument(app).expose(
    app, include_in_schema=False, endpoint="/api/metrics"
)
client = OpenAI() if (OpenAI and os.getenv("OPENAI_API_KEY")) else None


def _resolve_request_tenant(request: Request) -> str:
    tenant = getattr(request.state, "tenant_id", None)
    if not tenant:
        tenant = request.headers.get("X-Debug-Tenant")
    if not tenant:
        tenant = os.getenv("TENANT_ID")
    if not tenant:
        raise HTTPException(status_code=400, detail="Tenant identifier is required")
    return str(tenant)


async def remove_file_after_ttl(path: str, ttl: int) -> None:
    """Delete a temporary uploaded file after a time-to-live (seconds).

    Runs in the background via ``BackgroundTasks`` to keep request latency
    low for the upload endpoint.
    """
    await asyncio.sleep(ttl)
    try:
        os.remove(path)
    except OSError:
        pass


class AskRequest(BaseModel):
    """Payload for the question-answering endpoint."""

    q: str
    k: int = 5


def _answer_with_context(question: str, context: str) -> tuple[str, bool]:
    """Return an answer for ``question`` based on ``context``.

    If an OpenAI client is configured (``OPENAI_API_KEY`` set), the function
    prompts the model with the supplied context; otherwise it falls back to a
    simple deterministic response so the system remains usable in development
    and CI without network access.

    Returns a pair ``(answer, used_llm)`` indicating whether an LLM was used.
    """
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
            system_prompt = (
                f"{custom_prompt} {base_prompt}" if custom_prompt else base_prompt
            )
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
        except Exception as exc:  # pragma: no cover - openai optional
            logger.warning("OpenAI chat completion failed: %s", exc)
    answer = context or f"You asked: {question}"
    return answer, False


@app.get("/api/health")
async def health():
    """Liveness/readiness probe with a minimal JSON body."""
    return {"status": "ok"}


@app.get("/api/version")
async def version():
    """Return version information for the application."""
    return {
        "version": __version__,
        "build_date": __build_date__,
        "commit_sha": __commit_sha__,
    }


@app.get("/api/config")
async def config():
    """Expose selected frontend configuration from environment variables."""
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
async def upload(background_tasks: BackgroundTasks, file: SingleUpload):
    """Accept a single PDF upload for temporary use in chat sessions.

    The file is validated by MIME type and size, stored under ``UPLOAD_DIR``
    and scheduled for deletion after ``UPLOAD_TTL`` seconds. The response
    includes a relative URL that the frontend can attach to a chat turn.
    """
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
async def ask(req: AskRequest, request: Request):
    """Answer a question using RAG.

    Retrieves the most relevant chunks (vector search + reranker) to build a
    context string, then generates the final answer with or without LLM.
    """
    tenant_id = _resolve_request_tenant(request)
    context, sources = build_context(req.q, req.k, tenant_id=tenant_id)
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
    *,
    files: MultiUpload,
):
    """Streaming chat endpoint (SSE) with optional file attachments.

    Rate-limited by client IP. Validates message and session lengths, checks
    each uploaded file type, and then streams tokens using SSE utilities.
    """
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
    """GET variant for chat streaming (no file uploads)."""
    if len(q) > CHAT_MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail="Message too long")
    if sessionId and len(sessionId) > SESSION_ID_MAX_LENGTH:
        raise HTTPException(status_code=400, detail="Invalid sessionId")
    return await chat_stream(request, q, k, [], [])


async def chat_stream(
    request: Request,
    q: str,
    k: int,
    files: list[UploadFile],
    attachments_meta: list[dict],
):
    """Shared implementation for chat endpoints.

    - Extracts text from in-memory uploads (PDFs) and from previously uploaded
      temporary files referenced by ``attachments_meta``.
    - Builds an attachment context and concatenates with user query for
      retrieval/answering, streaming tokens via SSE.
    """
    attachment_texts: list[str] = []
    attachment_sources: list[dict] = []
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

    usage: dict = {}
    context = ""
    sources: list[dict] = []

    tenant_id = _resolve_request_tenant(request)

    async def token_iter():
        nonlocal usage, context, sources
        context_db, sources_db = build_context(combined_q, k, tenant_id=tenant_id)
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
                    f"Reply in {lang}."
                    if lang
                    else "Reply in the same language as the question."
                )
                base_prompt = "Answer the user's question using the supplied context."
                custom_prompt = os.getenv("SYSTEM_PROMPT")
                system_prompt = (
                    f"{custom_prompt} {base_prompt}" if custom_prompt else base_prompt
                )
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
                yield "event: sources\n" + "data: " + json.dumps(
                    sources, ensure_ascii=False
                ) + "\n\n"
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
