import os
import argparse
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector

from fastembed import TextEmbedding

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Consulta semântica (kNN) no pgvector")
    parser.add_argument("--q", type=str, required=True, help="Pergunta/consulta")
    parser.add_argument("--k", type=int, default=5, help="Número de trechos retornados")
    args = parser.parse_args()

    dsn = f"host={os.getenv('PGHOST','localhost')} port={os.getenv('PGPORT','5432')} dbname={os.getenv('PGDATABASE','pdfkb')} user={os.getenv('PGUSER','pdfkb')} password={os.getenv('PGPASSWORD','pdfkb')}"
    conn = psycopg.connect(dsn)
    register_vector(conn)

    embedder = TextEmbedding(model_name="intfloat/multilingual-e5-small")
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

    print("="*80)
    print(f"Top {args.k} trechos mais similares para: {args.q!r}\n")
    for i, (path, idx, content, dist) in enumerate(rows, 1):
        print(f"[{i}] {path}  #chunk {idx}  (dist={dist:.4f})")
        preview = content.strip().replace("\n", " ")
        preview = (preview[:600] + "…") if len(preview) > 600 else preview
        print(preview)
        print("-"*80)

    conn.close()

if __name__ == "__main__":
    main()
