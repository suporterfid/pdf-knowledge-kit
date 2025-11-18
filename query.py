import argparse
import logging
import os
import sys
from collections.abc import Sequence
from typing import Any

import psycopg
from dotenv import load_dotenv
from fastembed import TextEmbedding
from langdetect import detect
from pgvector.psycopg import register_vector

logger = logging.getLogger(__name__)


def _echo(message: str) -> None:
    sys.stdout.write(f"{message}\n")


try:  # pragma: no cover - openai optional
    from openai import OpenAI
except Exception:  # pragma: no cover - openai optional
    OpenAI = None  # type: ignore


def _answer_with_context(question: str, context: str) -> str:
    """Generate an answer given a question and context using the LLM if available."""
    api_key = os.getenv("OPENAI_API_KEY")
    if OpenAI is not None and api_key:
        try:  # pragma: no cover - openai optional
            client = OpenAI()
            lang = os.getenv("OPENAI_LANG")
            if not lang:
                try:
                    lang = detect(question)
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
                        "content": f"Context:\n{context}\n\nQuestion:\n{question}",
                    },
                ],
            )
            message_content: Any = completion.choices[0].message.content
            if isinstance(message_content, str):
                return message_content.strip()
            if isinstance(message_content, Sequence):
                combined = "".join(
                    part.get("text", "")
                    for part in message_content
                    if isinstance(part, dict)
                )
                if combined:
                    return combined.strip()
            return context or f"You asked: {question}"
        except Exception as exc:  # pragma: no cover - openai optional
            logger.warning("OpenAI chat completion failed: %s", exc)
    return context or f"You asked: {question}"


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Consulta semântica (kNN) no pgvector")
    parser.add_argument("--q", type=str, required=True, help="Pergunta/consulta")
    parser.add_argument("--k", type=int, default=5, help="Número de trechos retornados")
    parser.add_argument(
        "--tenant-id",
        default=os.getenv("TENANT_ID"),
        help="Identificador do tenant (UUID)",
    )
    args = parser.parse_args()

    tenant_id = args.tenant_id
    if not tenant_id:
        parser.error("--tenant-id é obrigatório (ou defina TENANT_ID)")

    dsn = f"host={os.getenv('PGHOST','db')} port={os.getenv('PGPORT','5432')} dbname={os.getenv('PGDATABASE','pdfkb')} user={os.getenv('PGUSER','pdfkb')} password={os.getenv('PGPASSWORD','pdfkb')}"
    conn = psycopg.connect(dsn)
    register_vector(conn)
    with conn.cursor() as cur:
        cur.execute("SET app.tenant_id = %s", (tenant_id,))

    # Use a supported multilingual embedding model
    embedder = TextEmbedding(model_name="paraphrase-multilingual-MiniLM-L12-v2-cls")
    qvec = list(embedder.embed([f"query: {args.q}"]))[0]  # E5 prefix para consulta

    sql = """
    SELECT d.path, c.chunk_index, c.content, (c.embedding <-> %s) AS distance
    FROM chunks c
    JOIN documents d ON d.id = c.doc_id
    WHERE c.embedding IS NOT NULL
      AND d.tenant_id = app.current_tenant_id()
    ORDER BY c.embedding <-> %s
    LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (qvec, qvec, args.k))
        rows = cur.fetchall()

    context = "\n\n".join(content for _, _, content, _ in rows)
    answer = _answer_with_context(args.q, context)

    _echo("=" * 80)
    _echo("Resposta:")
    _echo(answer)
    _echo("=" * 80)
    _echo(f"Top {args.k} trechos mais similares para: {args.q!r}\n")
    for i, (path, idx, content, dist) in enumerate(rows, 1):
        _echo(f"[{i}] {path}  #chunk {idx}  (dist={dist:.4f})")
        preview = content.strip().replace("\n", " ")
        preview = (preview[:600] + "…") if len(preview) > 600 else preview
        _echo(preview)
        _echo("-" * 80)

    conn.close()


if __name__ == "__main__":
    main()
