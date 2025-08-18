from fastapi import FastAPI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import os
import json
from dotenv import load_dotenv
from typing import Dict

from .rag import build_context

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - openai optional
    OpenAI = None  # type: ignore

load_dotenv()

app = FastAPI()

client = OpenAI() if (OpenAI and os.getenv("OPENAI_API_KEY")) else None


class AskRequest(BaseModel):
    q: str
    k: int = 5


@app.get("/")
async def root():
    return {"message": "PDF Knowledge Kit API"}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/ask")
async def ask(req: AskRequest):
    _, results = build_context(req.q, req.k)
    return {"results": results}


class ChatRequest(BaseModel):
    q: str
    k: int = 5


@app.post("/api/chat")
async def chat(req: ChatRequest):
    async def event_gen():
        try:
            context, sources = build_context(req.q, req.k)
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
                                "content": f"Contexto:\n{context}\n\nPergunta:\n{req.q}",
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
                    answer = context or f"Você perguntou: {req.q}"
                    for token in answer.split():
                        yield {"event": "token", "data": token}
                    n = len(answer.split())
                    usage = {
                        "prompt_tokens": 0,
                        "completion_tokens": n,
                        "total_tokens": n,
                    }
            else:
                answer = context or f"Você perguntou: {req.q}"
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
