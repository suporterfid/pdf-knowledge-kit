# PDF/Markdown → Vector DB (pgvector) Starter Kit

Crie rapidamente uma base de conhecimento a partir de **arquivos PDF** e **Markdown** em uma pasta local e habilite **busca semântica** para um agente de IA.

## Visão geral
1. **Extrai** textos dos PDFs e arquivos Markdown.
2. **Divide** em *chunks* (trechos) com sobreposição.
3. **Gera embeddings** (multilíngue, PT/EN) com `fastembed`.
4. **Armazena** em **PostgreSQL + pgvector**.
5. **Consulta** por similaridade (kNN) com `query.py` — pronto para integrar no seu agente.

> Dimensão dos vetores: **384** (modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`).

### Suporte a idiomas
O modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` atende mais de 50 idiomas
e foi verificado com frases em **inglês**, **português brasileiro** e **espanhol**.
Línguas fora desse conjunto podem gerar embeddings de qualidade reduzida e
resultados menos precisos.

---

## Requisitos
- **Docker** + **Docker Compose** (para o Postgres com pgvector).
- **Python 3.10+** com `pip`.
- *(Opcional p/ OCR)* `tesseract-ocr`, pacotes de idioma (`tesseract-ocr-eng`, `tesseract-ocr-por`, `tesseract-ocr-spa`) e `poppler-utils`.
O `Dockerfile` já instala esses pacotes.

## Ambiente de desenvolvimento
1. Clone este repositório.
2. Crie um ambiente virtual e instale as dependências:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
3. Suba o Postgres local com pgvector:
```bash
docker compose up -d db
```
4. Execute os testes para validar o setup:
```bash
pytest
```
5. Inicie o backend em modo `reload`:
```bash
uvicorn app.main:app --reload
```
6. (Opcional) Para a interface, entre em `frontend/` e rode `npm install && npm run dev`.

## Passo a passo (rápido)
```bash
# 1) Suba o Postgres com pgvector
docker compose up -d db

# 2) Instale as dependências Python
python -m venv .venv && source .venv/bin/activate  # no Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3) Configure variáveis de ambiente (opcional)
cp .env.example .env  # edite se quiser

# 4) Coloque seus PDFs e arquivos Markdown (.md) na pasta ./docs/
#    Arquivos .md nessa pasta são ingeridos junto com os PDFs
#    (ou aponte outra pasta com --docs / DOCS_DIR)

# 5) Ingestão
python ingest.py --docs ./docs  # use --ocr (ex.: --ocr-lang eng+por) ou ENABLE_OCR=1 para PDFs escaneados

# 6) Consulta (exemplo)
python query.py --q "Como configuro potência de leitura?" --k 5
```

## Ingestão de PDFs/Markdown com Docker

1. **Tornar os arquivos acessíveis ao container**

   - Coloque os arquivos na pasta `docs/` do projeto.
   - Essa pasta já está mapeada dentro do container; tudo nela ficará disponível em `/app/docs` quando o serviço subir.

2. **Ingerir os arquivos no banco**

   No diretório raiz do projeto, execute:

   ```bash
   docker compose run --rm app python ingest.py --docs /app/docs  # adicione --ocr/--ocr-lang ou ENABLE_OCR=1 se preciso
   ```

   Esse script lê os PDFs e arquivos Markdown e grava os vetores no **PostgreSQL/pgvector**.

3. **Subir a aplicação**

   Inicie os serviços normalmente:

   ```bash
   docker compose up --build
   ```

   Isso lança o backend e o frontend, que já podem consultar os documentos ingeridos.

4. **(Opcional) Usar outra pasta local**

   Se preferir outra pasta, **antes** de subir os containers, altere o mapeamento de volume em `docker-compose.yml` para apontar para o diretório desejado.

   Exemplo para Windows:

   ```yaml
   volumes:
     - C:/Users/alexa/Dropbox/Delivery/Impinj/R700/FAQ:/app/docs:ro
   ```

   Depois, rode a ingestão:

   ```bash
   docker compose run --rm app python ingest.py --docs /app/docs  # adicione --ocr/--ocr-lang ou ENABLE_OCR=1 se preciso
   ```

   Ou mapeie o volume diretamente na execução:

   ```bash
   docker compose run --rm \
     -v "C:/Users/alexa/Dropbox/Delivery/Impinj/R700/FAQ:/app/docs:ro" \
    app python ingest.py --docs /app/docs  # adicione --ocr ou ENABLE_OCR=1 se preciso
   ```


## Ingestão de páginas web públicas

Além de arquivos locais, o `ingest.py` também pode buscar e indexar páginas da web acessíveis publicamente.

```bash
# Uma ou mais URLs diretamente na linha de comando
python ingest.py --url https://exemplo.com/sobre --url https://example.com/en/doc

# Lista de URLs (uma por linha)
python ingest.py --urls-file urls.txt
# ou defina URLS_FILE=urls.txt e o script usará esse caminho por padrão
```

O conteúdo dessas páginas deve estar em **inglês**, **português** ou **espanhol** (EN/PT/ES).

## Logging

A aplicação grava dois arquivos de log em `LOG_DIR` (padrão `logs/` localmente):

- `app.log` – eventos da aplicação.
- `access.log` – requisições/respostas HTTP.

Os arquivos são **rotacionados diariamente à meia-noite** e mantidos por `LOG_RETENTION_DAYS` dias (padrão: 7).
Defina `LOG_ROTATE_UTC=true` para rotacionar em UTC.

Principais variáveis de ambiente:

| Variável              | Padrão    | Descrição |
|----------------------|-----------|-----------|
| `LOG_DIR`            | `logs/`   | Diretório dos arquivos de log (no Docker: `/var/log/app`). |
| `LOG_LEVEL`          | `INFO`    | Nível mínimo de log. |
| `LOG_JSON`           | `false`   | Saída em formato JSON. |
| `LOG_REQUEST_BODIES` | `false`   | Inclui corpo da requisição no access log. |
| `LOG_RETENTION_DAYS` | `7`       | Quantidade de dias mantidos após rotação. |
| `LOG_ROTATE_UTC`     | `false`   | Rotaciona usando UTC. |

Para verificar rapidamente os valores efetivos dessas configurações, execute:

```bash
python -m tools.print_log_config
```

### Tailing logs

```bash
# Local
tail -f logs/app.log

# Docker
docker compose logs -f app
docker compose exec app tail -f /var/log/app/app.log
```

Para persistir os logs dos containers no host, mapeie um volume:

```yaml
app:
  volumes:
    - ./logs:/var/log/app
```

## Build do chat e frontend

```bash
# Backend standalone
uvicorn app.main:app --reload  # roda em http://localhost:8000

# ou construa tudo com Docker
docker compose up --build

# Frontend (opcional para alterar a interface)
cd frontend
npm install
npm run build  # gera os arquivos em app/static
```

## Variáveis de ambiente
Copie `.env.example` para `.env` e ajuste conforme necessário. Exemplo mínimo:

```env
DOCS_DIR=./docs           # PDFs e Markdown (.md) lidos desta pasta
ENABLE_OCR=0              # OCR só para PDFs escaneados (não afeta .md)
OCR_LANG=eng+por+spa      # ex.: PDFs em inglês, português e espanhol
```

Principais chaves disponíveis:

- **PGHOST**, **PGPORT**, **PGDATABASE**, **PGUSER**, **PGPASSWORD** – conexão com o Postgres/pgvector.
- **DOCS_DIR** – pasta padrão para os arquivos. Qualquer `.md` nessa pasta é ingerido junto com os PDFs.
- **OPENAI_API_KEY**, **OPENAI_MODEL**, **USE_LLM** – integrações com LLM (opcional).
- **TOP_K**, **MAX_CONTEXT_CHARS** – ajustes de recuperação de trechos.
- **UPLOAD_DIR**, **UPLOAD_TTL**, **UPLOAD_MAX_SIZE**, **UPLOAD_ALLOWED_MIME_TYPES** – controle de uploads temporários.
- **CORS_ALLOW_ORIGINS**, **BRAND_NAME**, **POWERED_BY_LABEL**, **LOGO_URL** – personalização da UI.
- **ENABLE_OCR** – habilita OCR em execuções não interativas (override de `--ocr`).
- **OCR_LANG** – idiomas do Tesseract para OCR. Combine múltiplos códigos com `+` (ex.: `eng+por`).

## OCR (Tesseract)

Por padrão, o OCR usa `OCR_LANG=eng+por+spa` (Inglês, Português e Espanhol). Altere os idiomas com `--ocr-lang` ou definindo a variável `OCR_LANG` antes da execução.

### Instalação

Para PDFs escaneados, instale o mecanismo de OCR, os pacotes de idioma e os conversores de PDF (o `Dockerfile` já inclui `tesseract-ocr-eng`, `tesseract-ocr-por` e `tesseract-ocr-spa`):

```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-por tesseract-ocr-spa poppler-utils
# macOS (Homebrew)
brew install tesseract poppler
# Ver idiomas disponíveis
tesseract --list-langs
```

### Como habilitar

- **Linha de comando (override):**

  ```bash
  python ingest.py --ocr --ocr-lang eng --docs ./docs
  ```

- **Variáveis de ambiente (override):**

  ```bash
  ENABLE_OCR=1 OCR_LANG=spa+por python ingest.py --docs ./docs
  ```

### Desempenho e suporte a idiomas

- OCR aumenta o tempo de ingestão (cada página é renderizada e processada).
- `OCR_LANG` e `--ocr-lang` aceitam múltiplos códigos (ex.: `eng+por+spa`). Cada idioma extra deixa o processamento mais lento, mas pode melhorar a precisão em documentos multilíngues; instale os pacotes correspondentes.

### Solução de problemas

- `tesseract: command not found` ou `pdftoppm: command not found` → instale `tesseract-ocr` e `poppler-utils` e verifique o `PATH`.
- `Error opening data file` ou `Failed loading language` → o pacote de idioma não está instalado. Rode `tesseract --list-langs` e instale, por exemplo, `sudo apt install tesseract-ocr-spa`.

## Uso do chat
1. Garanta que o backend esteja rodando (com `uvicorn` ou Docker).
2. Acesse `http://localhost:8000` no navegador.
3. Envie mensagens pelo campo de texto. Opcionalmente, anexe um PDF pequeno para enriquecer o contexto.
4. Durante a geração da resposta, use **Cancelar** para interromper o streaming e **Enviar** novamente para retomar.

## Estrutura
```
pdf_knowledge_kit/
├─ docker-compose.yml      # Postgres + pgvector
├─ requirements.txt        # Dependências
├─ schema.sql              # Criação de tabelas/índices
├─ migrations/             # Migrações incrementais do banco de dados
├─ ingest.py               # Varre PDFs/Markdown, extrai, fatia e insere
├─ query.py                # Busca semântica
├─ .env.example            # Configs de conexão
└─ docs/                   # Coloque seus PDFs e Markdown aqui
```

## Deploy em produção

### Bare metal
1. Instale **PostgreSQL** com a extensão **pgvector** e crie o banco:
```bash
psql -c 'CREATE EXTENSION IF NOT EXISTS vector;' "$PGDATABASE"
psql -f schema.sql "$PGDATABASE"
psql -f migrations/002_add_admin_ingestion.sql "$PGDATABASE"
```
2. Configure as variáveis de ambiente (veja `.env.example`).
3. Ingestione os documentos:
```bash
python ingest.py --docs ./docs
```
4. Inicie a API com um servidor como **gunicorn** ou **uvicorn**:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
5. Teste:
```bash
curl http://localhost:8000/api/health
```

### Docker
1. Copie `.env.example` para `.env` e ajuste.
2. Construa e suba os serviços:
```bash
docker compose up --build -d
```
3. Ingerir documentos dentro do container:
```bash
docker compose run --rm app python ingest.py --docs /app/docs
```
4. Verifique a API:
```bash
curl http://localhost:8000/api/health
```

## Integração no seu agente de IA (resumo)
- Use `query.py` como referência: gere embedding da pergunta e rode SQL:
  `SELECT ... ORDER BY embedding <-> :vec LIMIT :k`.
- Traga os trechos + metadados e alimente o *prompt* do agente (*RAG*).
- Para respostas fiéis, **mostre as fontes** (caminho do arquivo e página, quando houver).

## Dicas francas
- PDFs escaneados (sem texto) exigem **OCR** (ex.: Tesseract). Habilite com `--ocr` (opcionalmente `--ocr-lang`) ou `ENABLE_OCR=1`/`OCR_LANG`.
- Para lotes grandes (milhares de páginas), rode ingestão em *batches* e crie o índice **depois**.
- Se já usa Postgres no seu stack, pgvector é simples e barato. Se quiser um serviço dedicado, olhe **Qdrant** ou **Weaviate**.
 
## Critérios de acessibilidade e desempenho
- Texto alternativo e rótulos ARIA para componentes interativos.
- Navegação total por teclado e foco visível.
- Contraste mínimo de 4.5:1 nas cores da interface.
- Respostas transmitidas via **SSE** para reduzir latência.
- Limpeza automática de uploads e limites de tamanho para preservar recursos.

Boa construção! 🚀
(gerado em 2025-08-18)
