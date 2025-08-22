import os
import argparse
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector

from fastembed import TextEmbedding

try:  # pragma: no cover - openai optional
    from openai import OpenAI
except Exception:  # pragma: no cover - openai optional
    OpenAI = None  # type: ignore


def _answer_with_context(question: str, context: str) -> str:
    """Generate an answer given a question and context using the LLM if available."""
    api_key = os.getenv("OPENAI_API_KEY")
    if OpenAI and api_key:
        try:  # pragma: no cover - openai optional
            client = OpenAI()
            completion = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                messages=[
                    {
                        "role": "system",
                        "content": "Responda à pergunta com base no contexto fornecido.",
                    },
                    {
                        "role": "user",
                        "content": f"Contexto:\n{context}\n\nPergunta:\n{question}",
                    },
                ],
            )
            return completion.choices[0].message["content"].strip()
        except Exception:  # pragma: no cover - openai optional
            pass
    return context or f"Você perguntou: {question}"

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Consulta semântica (kNN) no pgvector")
    parser.add_argument("--q", type=str, required=True, help="Pergunta/consulta")
    parser.add_argument("--k", type=int, default=5, help="Número de trechos retornados")
    args = parser.parse_args()

    dsn = f"host={os.getenv('PGHOST','db')} port={os.getenv('PGPORT','5432')} dbname={os.getenv('PGDATABASE','pdfkb')} user={os.getenv('PGUSER','pdfkb')} password={os.getenv('PGPASSWORD','pdfkb')}"
    conn = psycopg.connect(dsn)
    register_vector(conn)

    # Use a supported multilingual embedding model
    embedder = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    qvec = list(embedder.embed([f'query: {args.q}']))[0]  # E5 prefix para consulta

    sql = """
    SELECT d.path, c.chunk_index, c.content, (c.embedding <-> %s) AS distance
    FROM chunks c
    JOIN documents d ON d.id = c.doc_id
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <-> %s
    LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (qvec, qvec, args.k))
        rows = cur.fetchall()

    context = "\n\n".join(content for _, _, content, _ in rows)
    answer = _answer_with_context(args.q, context)

    print("=" * 80)
    print("Resposta:")
    print(answer)
    print("=" * 80)
    print(f"Top {args.k} trechos mais similares para: {args.q!r}\n")
    for i, (path, idx, content, dist) in enumerate(rows, 1):
        print(f"[{i}] {path}  #chunk {idx}  (dist={dist:.4f})")
        preview = content.strip().replace("\n", " ")
        preview = (preview[:600] + "…") if len(preview) > 600 else preview
        print(preview)
        print("-" * 80)

    conn.close()

if __name__ == "__main__":
    main()
