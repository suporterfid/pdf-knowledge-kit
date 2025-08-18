from fastapi import FastAPI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import os
import json
from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector
from fastembed import TextEmbedding

load_dotenv()

app = FastAPI()

embedder = TextEmbedding(model_name="intfloat/multilingual-e5-small")


def get_conn():
    dsn = (
        f"host={os.getenv('PGHOST','localhost')} "
        f"port={os.getenv('PGPORT','5432')} "
        f"dbname={os.getenv('PGDATABASE','pdfkb')} "
        f"user={os.getenv('PGUSER','pdfkb')} "
        f"password={os.getenv('PGPASSWORD','pdfkb')}"
    )
    conn = psycopg.connect(dsn)
    register_vector(conn)
    return conn


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
    conn = get_conn()
    qvec = list(embedder.embed([f"query: {req.q}"]))[0]
    sql = """
    SELECT d.path, c.chunk_index, c.content, (c.embedding <-> %s) AS distance
    FROM chunks c
    JOIN documents d ON d.id = c.doc_id
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <-> %s
    LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (qvec, qvec, req.k))
        rows = cur.fetchall()
    conn.close()
    results = [
        {
            "path": path,
            "chunk_index": idx,
            "content": content,
            "distance": dist,
        }
        for path, idx, content, dist in rows
    ]
    return {"results": results}


class ChatRequest(BaseModel):
    q: str
    k: int = 5


@app.post("/api/chat")
async def chat(req: ChatRequest):
    async def event_gen():
        try:
            conn = get_conn()
            qvec = list(embedder.embed([f"query: {req.q}"]))[0]
            sql = """
            SELECT d.path, c.chunk_index, c.content, (c.embedding <-> %s) AS distance
            FROM chunks c
            JOIN documents d ON d.id = c.doc_id
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <-> %s
            LIMIT %s;
            """
            with conn.cursor() as cur:
                cur.execute(sql, (qvec, qvec, req.k))
                rows = cur.fetchall()
            conn.close()
            sources = [
                {
                    "path": path,
                    "chunk_index": idx,
                    "content": content,
                    "distance": dist,
                }
                for path, idx, content, dist in rows
            ]
            answer = f"Você perguntou: {req.q}"
            for token in answer.split():
                yield {"event": "token", "data": token}
            yield {"event": "sources", "data": json.dumps(sources)}
            yield {"event": "done", "data": ""}
        except Exception as e:
            yield {"event": "error", "data": str(e)}
    return EventSourceResponse(event_gen())
