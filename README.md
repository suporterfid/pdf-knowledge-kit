# PDF → Vector DB (pgvector) Starter Kit

Crie rapidamente uma base de conhecimento a partir de **arquivos PDF** em uma pasta local e habilite **busca semântica** para um agente de IA.

## Visão geral
1. **Extrai** textos dos PDFs.
2. **Divide** em *chunks* (trechos) com sobreposição.
3. **Gera embeddings** (multilíngue, PT/EN) com `fastembed`.
4. **Armazena** em **PostgreSQL + pgvector**.
5. **Consulta** por similaridade (kNN) com `query.py` — pronto para integrar no seu agente.

> Dimensão dos vetores: **384** (modelo `intfloat/multilingual-e5-small`).

---

## Requisitos
- **Docker** + **Docker Compose** (para o Postgres com pgvector).
- **Python 3.10+** com `pip`.

## Passo a passo (rápido)
```bash
# 1) Suba o Postgres com pgvector
docker compose up -d db

# 2) Instale as dependências Python
python -m venv .venv && source .venv/bin/activate  # no Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3) Configure variáveis de ambiente (opcional)
cp .env.example .env  # edite se quiser

# 4) Coloque seus PDFs na pasta ./docs/
#    (ou aponte outra pasta com --docs / DOCS_DIR)

# 5) Ingestão
python ingest.py --docs ./docs

# 6) Consulta (exemplo)
python query.py --q "Como configuro potência de leitura?" --k 5
```

## Estrutura
```
pdf_knowledge_kit/
├─ docker-compose.yml      # Postgres + pgvector
├─ requirements.txt        # Dependências
├─ schema.sql              # Criação de tabelas/índices
├─ ingest.py               # Varre PDFs, extrai, fatia e insere
├─ query.py                # Busca semântica
├─ .env.example            # Configs de conexão
└─ docs/                   # Coloque seus PDFs aqui
```

## Integração no seu agente de IA (resumo)
- Use `query.py` como referência: gere embedding da pergunta e rode SQL:
  `SELECT ... ORDER BY embedding <-> :vec LIMIT :k`.
- Traga os trechos + metadados e alimente o *prompt* do agente (*RAG*).
- Para respostas fiéis, **mostre as fontes** (caminho do PDF e página).

## Dicas francas
- PDFs escaneados (sem texto) exigem **OCR** (ex.: Tesseract). Este kit não faz OCR por padrão — adicione se precisar.
- Para lotes grandes (milhares de páginas), rode ingestão em *batches* e crie o índice **depois**.
- Se já usa Postgres no seu stack, pgvector é simples e barato. Se quiser um serviço dedicado, olhe **Qdrant** ou **Weaviate**.

Boa construção! 🚀
(gerado em 2025-08-18)
