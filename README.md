# Multiagent/AI Knowledge Base → Vector DB (pgvector) Starter Kit

Crie rapidamente uma base de conhecimento a partir de **arquivos PDF**, **documentos do office**, **links** e **Markdown** em uma pasta local e habilite **busca semântica** para um agente de IA.

Inclui uma interface web inspirada no ChatGPT com histórico de conversas, anexos, destaque de código e alternância de tema claro/escuro.

## Visão Geral

O projeto disponibiliza um agente de IA completo: um backend em Python expõe APIs de ingestão, consulta semântica e chat em streaming, enquanto o frontend em React oferece a experiência conversacional pronta para uso.

### Fluxo principal

1. **Extrai** textos dos PDFs e arquivos Markdown.
2. **Divide** em _chunks_ (trechos) com sobreposição.
3. **Gera embeddings** (multilíngue, PT/EN) com `fastembed`.
4. **Armazena** em **PostgreSQL + pgvector**.
5. **Consulta** por similaridade (kNN) com `query.py` ou pelas rotas FastAPI — pronto para integrar no seu agente.

> Dimensão dos vetores: **384** (modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`).

### Experiência de uso

- Chat com streaming SSE, histórico de conversas, upload temporário de arquivos e resposta opcional com LLM (OpenAI).
- Interface React com temas claro/escuro, destaques de código e notificações.
- Scripts CLI (`ingest.py`, `query.py`) para ingestão e validação rápida sem depender do frontend.

### Suporte a idiomas

O modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` atende mais de 50 idiomas e foi verificado com frases em **inglês**, **português brasileiro** e **espanhol**. Línguas fora desse conjunto podem gerar embeddings de qualidade reduzida e resultados menos precisos.

---

## Stack Tecnológica

### Backend (Python)

- **FastAPI** para as rotas públicas, admin e SSE (`sse-starlette`).
- **Uvicorn** com `--reload` em desenvolvimento e suporte a `debugpy`.
- **fastembed** para geração de embeddings e `rank-bm25` como fallback lexical.
- **pypdf**, `pdf2image`, `pytesseract` e utilitários para extração de texto e OCR.
- **psycopg** + `pgvector` para persistência, além de `python-dotenv`, `pydantic`, `SlowAPI` (rate limiting) e métricas com `prometheus-fastapi-instrumentator`.

### Frontend (React)

- **React 18** com **Vite** e **TypeScript**.
- **Tailwind CSS** para estilização, `react-router-dom` para rotas e `react-toastify` para feedback.
- Renderização segura de Markdown com `markdown-it` + `DOMPurify` e destaque de código via `Prism.js`.

### Banco de dados e armazenamento

- **PostgreSQL** com a extensão **pgvector** para busca semântica.
- Migrações em `migrations/` e schema inicial em `schema.sql`.
- Uploads temporários gravados em `UPLOAD_DIR` (padrão `tmp/uploads`), com limpeza automática via `BackgroundTasks`.

### Ferramentas e observabilidade

- **Dockerfile** e **docker-compose.yml** para desenvolvimento e deploy.
- Métricas Prometheus expostas em `/api/metrics` e logs diários com rotação automática.
- Testes com `pytest` (backend) e `vitest`/`@testing-library/react` (frontend).

## Configuração do Ambiente

### Pré-requisitos

- **Docker** + **Docker Compose** (necessários para subir o Postgres com pgvector ou rodar tudo em containers).
- **Python 3.10+** com `pip`.
- _(Opcional p/ OCR)_ `tesseract-ocr`, pacotes de idioma (`tesseract-ocr-eng`, `tesseract-ocr-por`, `tesseract-ocr-spa`) e `poppler-utils`. O `Dockerfile` já instala esses pacotes.

### Preparar o backend (Python)

```bash
git clone https://github.com/<sua-org>/pdf-knowledge-kit.git
cd pdf-knowledge-kit
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt  # ou use requirements.lock para versões travadas
pip install -r requirements-dev.txt  # ferramentas de lint, formatação e análise estática
```

- Prefira `requirements.lock` para ambientes reproduzíveis; `requirements.txt` mantém flexibilidade com intervalos `>=`.
- Use `pip install -r requirements.txt --no-deps` se quiser habilitar somente partes específicas do stack (por exemplo, para containers slim).

### Dependências opcionais

Os conectores opcionais trazem bibliotecas extras:

| Finalidade                     | Pacotes                                                  | Observações                                                         |
| ------------------------------ | -------------------------------------------------------- | ------------------------------------------------------------------- |
| Conversão de documentos Office | `python-docx`, `openpyxl`                                | Já listados no arquivo principal.                                   |
| Transcrição (AWS)              | `boto3`                                                  | Requer `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_REGION`. |
| Transcrição (Whisper local)    | `faster-whisper` (GPU/CPU otimizada) ou `openai-whisper` | Instale apenas um dos pacotes conforme o backend desejado.          |

Você também pode instalar pacotes avulsos como `pip install boto3 faster-whisper` em ambientes enxutos.

### Banco de dados local (pgvector)

Suba o Postgres com pgvector usando Docker Compose:

```bash
docker compose up -d db
```

O serviço já cria o banco `pdfkb` com a extensão `vector`. Caso rode manualmente, aplique `schema.sql` e as migrações de `migrations/`.

### Variáveis de ambiente

```bash
cp .env.example .env  # personalize conforme necessário
```

Detalhes completos estão na seção [Variáveis de ambiente](#variáveis-de-ambiente).

### Preparar o frontend (React)

```bash
cd frontend
npm install
cd ..
```

### Validação rápida

```bash
pytest
```

### Qualidade de código (lint e segurança)

1. Ative o ambiente virtual e instale as ferramentas auxiliares:

   ```bash
   pip install -r requirements-dev.txt
   ```

2. Rode as checagens antes de abrir um PR:

   | Ferramenta | Comando | Objetivo |
   | ---------- | ------- | -------- |
   | **Ruff**   | `ruff check .` | Lint e diagnósticos rápidos para Python. |
   | **Black**  | `black --check .` | Confirma que o código segue o formato padrão. |
   | **MyPy**   | `mypy --config-file pyproject.toml` | Valida os tipos estáticos do backend. |
   | **Bandit** | `bandit -c pyproject.toml -r app/` | Aponta problemas de segurança em tempo de desenvolvimento. |

Use `ruff format` ou `black` sem a flag `--check` para aplicar correções automáticas quando necessário.


## Como Executar

### Backend (API e agente)

```bash
# garantir que o Postgres está no ar
docker compose up -d db

# iniciar o backend com recarregamento automático
uvicorn app.main:app --reload
```

- A API ficará disponível em `http://localhost:8000` (documentação interativa em `/docs`).
- Utilize `uvicorn app.main:app --host 0.0.0.0 --port 8000` para expor em outras máquinas.

### Ferramentas de linha de comando

- **Ingestão** de PDFs/Markdown:

  ```bash
  python ingest.py --docs ./docs  # adicione --ocr ou ENABLE_OCR=1 para PDFs escaneados
  ```

- **Consulta** semântica via CLI:

  ```bash
  python query.py --q "Como configuro potência de leitura?" --k 5
  ```

- Parâmetros adicionais permitem apontar para outras pastas (`--docs` ou `DOCS_DIR`) e URLs públicas (`--url`, `--urls-file`).

### Frontend (React/Vite)

```bash
cd frontend
npm run dev  # http://localhost:5173

# build de produção opcional
npm run build  # gera artefatos em app/static
```

Para desenvolvimento full-stack com Docker/VS Code veja [Depuração com VS Code + Docker Desktop](#depuração-com-vs-code--docker-desktop).

### Passo a passo (rápido)

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

## Deploy

### Ingestão de PDFs/Markdown com Docker

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

| Variável             | Padrão  | Descrição                                                  |
| -------------------- | ------- | ---------------------------------------------------------- |
| `LOG_DIR`            | `logs/` | Diretório dos arquivos de log (no Docker: `/var/log/app`). |
| `LOG_LEVEL`          | `INFO`  | Nível mínimo de log.                                       |
| `LOG_JSON`           | `false` | Saída em formato JSON.                                     |
| `LOG_REQUEST_BODIES` | `false` | Inclui corpo da requisição no access log.                  |
| `LOG_RETENTION_DAYS` | `7`     | Quantidade de dias mantidos após rotação.                  |
| `LOG_ROTATE_UTC`     | `false` | Rotaciona usando UTC.                                      |

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

## Métricas

A aplicação expõe métricas no formato **Prometheus** em `/api/metrics`.
Ao rodar localmente ou via Docker, você pode verificar as métricas com:

```bash
curl http://localhost:8000/api/metrics
```

Esses dados podem ser coletados por Prometheus ou outras ferramentas de monitoramento.

## Build do chat e frontend

## Depuração com VS Code + Docker Desktop

Use as configurações já incluídas em `.vscode/launch.json` para depurar o stack completo:

- Abra o projeto no VS Code e certifique-se de que o Docker Desktop está em execução.
- Pressione F5 e selecione "Fullstack: Backend + Frontend".
  - O VS Code executa `docker compose up -d --build` (db, backend e frontend).
  - O backend inicia com `debugpy` ouvindo em `5678` (não bloqueia a API). Você pode anexar a qualquer momento.
  - O VS Code se anexa ao backend (mapeamento de código fonte `/app` ⇄ workspace).
  - O Chrome é aberto em `http://localhost:5173` (Vite) para depuração do React.

Também é possível iniciar individualmente:

- "Backend: Attach FastAPI (Docker)" para apenas o backend.
- "Frontend: Launch Chrome (Vite)" para apenas o frontend.

Observações:

- Hot reload habilitado: `uvicorn --reload` no backend e Vite no frontend.
- Quebre pontos normalmente nos arquivos locais; o mapeamento com os containers já está configurado.
- Após a sessão, você pode parar os serviços com a tarefa `compose: down` no VS Code (Terminal > Run Task).

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

- **PGHOST**, **PGPORT**, **PGDATABASE**, **PGUSER**, **PGPASSWORD** – conexão com o Postgres/pgvector (padrões: `db`, `5432`, `pdfkb`, `pdfkb`, `pdfkb`).
- **DOCS_DIR** – pasta padrão para os arquivos. Qualquer `.md` nessa pasta é ingerido junto com os PDFs.
  - **OPENAI_API_KEY**, **OPENAI_MODEL**, **OPENAI_LANG**, **SYSTEM_PROMPT**, **USE_LLM** – integrações com LLM (opcional). `SYSTEM_PROMPT` permite configurar o tom/persona do agente.
- **TOP_K**, **MAX_CONTEXT_CHARS** – ajustes de recuperação de trechos.
- **UPLOAD_DIR**, **UPLOAD_TTL**, **UPLOAD_MAX_SIZE**, **UPLOAD_MAX_FILES**, **UPLOAD_ALLOWED_MIME_TYPES** – controle de uploads temporários.
- **CORS_ALLOW_ORIGINS**, **BRAND_NAME**, **POWERED_BY_LABEL**, **LOGO_URL** – personalização da UI. `POWERED_BY_LABEL` define o texto do rodapé (padrão: "Powered by PDF Knowledge Kit").
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

Recursos da interface:

- Barra lateral com histórico de conversas (criar, renomear, excluir).
- Avatares e bolhas com realce de código via Prism.
- Botões para copiar, regenerar e avaliar cada resposta.
- Pré-visualização de PDFs anexados.
- Alternância entre tema claro e escuro.

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

### Deploy em produção

#### Bare metal

1. Instale **PostgreSQL** com a extensão **pgvector** e crie o banco:

```bash
psql -c 'CREATE EXTENSION IF NOT EXISTS vector;' "$PGDATABASE"
psql -f schema.sql "$PGDATABASE"
psql -f migrations/002_add_admin_ingestion.sql "$PGDATABASE"
psql -f migrations/003_extend_ingestion_tables.sql "$PGDATABASE"  # novas colunas de metadados
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

## Debug com Dev Containers (VS Code)

- Pré-requisitos: Docker Desktop; VS Code com extensão "Dev Containers"; acesso à internet para baixar imagens.
- Abrir no container:
  - Abra a pasta do projeto no VS Code.
  - Paleta de Comandos → "Dev Containers: Reopen in Container" (ou "Rebuild and Reopen in Container").
  - O VS Code usa `.devcontainer/devcontainer.json` + `docker-compose.yml` e sobe `db`, `app` e `frontend`.
- Aguardar o banco ficar healthy:
  - O serviço `db` fica "healthy" via `pg_isready`; a primeira execução pode demorar por download de imagens.
  - Para um reset completo: `docker compose down -v` e depois `docker compose up -d`.
- Iniciar o debug:
  - Backend: pressione F5 e selecione "Attach to FastAPI (Docker)". O backend já inicia com `debugpy` em `0.0.0.0:5678` e `--wait-for-client`, então ele começa a rodar após o attach. Quebre em `app/` normalmente.
  - Full‑stack: selecione "Fullstack: Backend + Frontend" para anexar ao backend e abrir o Vite dev server no navegador.
- Portas úteis:
  - API: `http://localhost:8000` (OpenAPI em `/docs`, health em `/api/health`)
  - Frontend: `http://localhost:5173`
  - Debug Python (debugpy): `5678`
- Conexão ao Postgres nos containers:
  - Use o host `db` (não `localhost`). A `.env` já define `PGHOST=db` e `DATABASE_URL=postgresql://pdfkb:pdfkb@db:5432/pdfkb`.
- Dicas rápidas:
  - Logs: `docker compose logs -f db app frontend`
  - Shell no container: `docker compose exec app bash`
  - Reset do banco (apaga volume): `docker compose down -v`

#### Docker

1. Copie `.env.example` para `.env` e ajuste.
2. Construa e suba os serviços:

```bash
docker compose up --build -d
```

> Nota (Docker/Dev Containers): dentro dos containers use o host `db` (não `localhost`) para acessar o Postgres. A `.env` já define `PGHOST=db` e `DATABASE_URL=postgresql://pdfkb:pdfkb@db:5432/pdfkb`. 3. Ingerir documentos dentro do container:

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
  - Traga os trechos + metadados e alimente o _prompt_ do agente (_RAG_).
  - Para respostas fiéis, **mostre as fontes** (caminho do arquivo e página, quando houver).

## Respostas humanizadas com OpenAI

O kit pode complementar os trechos retornados com uma resposta em linguagem natural gerada pela API da OpenAI.

1. Configure as variáveis de ambiente:

```bash
export OPENAI_API_KEY="sua-chave"
export OPENAI_MODEL="gpt-4o-mini"  # ou outro modelo compatível
export OPENAI_LANG="pt"            # opcional: força o idioma da resposta
```

Se `OPENAI_LANG` não for definido, o idioma da pergunta é detectado automaticamente e a resposta é devolvida no mesmo idioma.

### Exemplo (CLI)

```bash
python query.py --q "¿Cuál es la capital de Francia?" --k 3
# Resposta: La capital de Francia es París.
```

### Exemplo (API)

```bash
curl -s -X POST http://localhost:8000/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"q":"Qual é a capital da Alemanha?"}'
```

Resposta:

```json
{ "answer": "A capital da Alemanha é Berlim.", "from_llm": true }
```

## Tenant accounts e autenticação

Use o conjunto de endpoints em `/api/tenant/accounts` para criar organizações, emitir tokens JWT e administrar convites de usuários. O fluxo básico envolve:

1. Registrar uma organização + usuário administrador (`POST /api/tenant/accounts/register`).
2. Fazer login (`POST /api/tenant/accounts/login`) para receber um par `access_token`/`refresh_token`.
3. Enviar o `access_token` no cabeçalho `Authorization: Bearer <token>` para proteger os demais endpoints.
4. Renovar credenciais com `/refresh`, revogar com `/logout` e rotacionar todos os tokens ativos via `/rotate-credentials`.
5. Administradores podem convidar novos membros (`/invite`) e os convidados finalizam o cadastro em `/accept-invite`.

Exemplo de registro e login:

```bash
curl -s -X POST http://localhost:8000/api/tenant/accounts/register \
  -H 'Content-Type: application/json' \
  -d '{
        "organization_name": "Acme Inc",
        "subdomain": "acme",
        "admin_name": "Alice",
        "admin_email": "alice@acme.dev",
        "password": "Str0ngPass!"
      }'

curl -s -X POST http://localhost:8000/api/tenant/accounts/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "alice@acme.dev", "password": "Str0ngPass!"}'
```

O corpo de resposta inclui `roles` (`viewer` < `operator` < `admin`) e metadados da organização. Tokens de atualização expiram por padrão em 14 dias, mas podem ser invalidados a qualquer momento pelos endpoints acima.

## Admin Ingestion

The `/api/admin/ingest/*` endpoints let operators trigger ingestion jobs remotely. Jobs run in the background and immediately return a `job_id`. Each job writes its own log file that can be polled while the work proceeds.

### Roles and environment variables

Requests must send um token JWT no cabeçalho `Authorization: Bearer <token>`. O `access_token` embute a hierarquia de papéis:

- **viewer** – acesso somente leitura a jobs e fontes.
- **operator** – viewer + iniciar/cancelar jobs.
- **admin** – operações avançadas de manutenção.

Configure os parâmetros de assinatura JWT no ambiente:

```bash
TENANT_TOKEN_SECRET=super-secret-key
TENANT_TOKEN_ISSUER=https://auth.example.com
TENANT_TOKEN_AUDIENCE=chatvolt
# (opcional) ACCESS_TOKEN_TTL_SECONDS e REFRESH_TOKEN_TTL_SECONDS para customizar expirações
```

### Job lifecycle, logs, and monitoring

Jobs move from `pending` → `running` → `completed`/`failed`/`canceled`. Logs are stored per job and exposed via `GET /api/admin/ingest/jobs/<JOB_ID>/logs`. The endpoint returns a slice of text and the next byte offset so clients can poll to tail progress.

```bash
# List jobs
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/api/admin/ingest/jobs

# Inspect a single job
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/api/admin/ingest/jobs/<JOB_ID>

# Read logs from the beginning
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/admin/ingest/jobs/<JOB_ID>/logs?offset=0"

# Cancel a running job
curl -X POST -H "Authorization: Bearer $OPERATOR_TOKEN" \
  http://localhost:8000/api/admin/ingest/jobs/<JOB_ID>/cancel

# Re-run a job using the same source
curl -X POST -H "Authorization: Bearer $OPERATOR_TOKEN" \
  http://localhost:8000/api/admin/ingest/jobs/<JOB_ID>/rerun
```

### Ingestion examples

```bash
# Local file
curl -X POST http://localhost:8000/api/admin/ingest/local \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -d "path=/app/docs/example.pdf"

# Single URL
curl -X POST http://localhost:8000/api/admin/ingest/url \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -d "url=https://example.com/doc"

# List of URLs
curl -X POST http://localhost:8000/api/admin/ingest/urls \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://a.com/doc1", "https://b.com/doc2"]}'

# Database connector job
curl -X POST http://localhost:8000/api/admin/ingest/database \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "label": "crm",
        "params": {
          "host": "db.internal",
          "database": "crm",
          "queries": [
            {
              "name": "customers",
              "sql": "SELECT id, notes FROM customers",
              "text_column": "notes",
              "id_column": "id"
            }
          ]
        },
        "credentials": {"username": "reader", "password": "s3cret"}
      }'

# REST connector job
curl -X POST http://localhost:8000/api/admin/ingest/api \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "label": "status-page",
        "params": {
          "base_url": "https://status.example.com",
          "endpoint": "/incidents",
          "text_fields": ["summary", "updates.0.body"],
          "id_field": "id"
        }
      }'

# Transcription connector job (set connector_metadata.media_type="video" for video sources)
curl -X POST http://localhost:8000/api/admin/ingest/transcription \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "label": "all-hands",
        "connector_metadata": {"media_type": "audio"},
        "params": {"provider": "mock", "media_uri": "s3://bucket/all-hands.mp3"}
      }'
```

### Catálogo de conectores e payloads

| Conector                                              | Quando usar                                                    | Campos obrigatórios                                                                                        | Credenciais                                                                                                     | Variáveis de ambiente relevantes                                                                                                   |
| ----------------------------------------------------- | -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Database** (`/api/admin/ingest/database`)           | Extrair textos de tabelas relacionais.                         | `params.queries[]` com `sql`, `text_column`, `id_column`. Opcionalmente `params.dsn` ou `host`/`database`. | `credentials.values.username` e `credentials.values.password` (ou DSN completo).                                | `DATABASE_URL` ou `PGHOST`/`PGUSER`/`PGPASSWORD` para uso interno.                                                                 |
| **REST/API** (`/api/admin/ingest/api`)                | Consumir APIs REST JSON.                                       | `params.endpoint` (ou `base_url`), `params.text_fields`, `params.id_field`.                                | `credentials.values.headers` ou `token`.                                                                        | `ADMIN_UI_ORIGINS` para CORS quando a UI admin roda em outra origem.                                                               |
| **Transcription** (`/api/admin/ingest/transcription`) | Transcrever áudio/vídeo por provedor externo ou Whisper local. | `params.provider` (`mock`, `whisper`, `aws_transcribe`), `params.media_uri`.                               | `credentials.values` pode conter `aws_access_key_id`/`aws_secret_access_key` ou tokens específicos do provedor. | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` para AWS; `WHISPER_MODEL`/`WHISPER_COMPUTE_TYPE` opcionais via payload. |

> **Dica:** a API recusa payloads que contenham apenas `{"secret_id": "..."}`. Resolva o segredo (via Vault/KMS) e envie o valor real para que o backend armazene uma cópia criptografada no banco.

### Automação (registro e monitoramento de conectores)

O script `tools/register_connector.py` demonstra como registrar conectores reutilizáveis e acompanhar o progresso de jobs:

```bash
python tools/register_connector.py \
  --host http://localhost:8000 \
  --operator-key "$OPERATOR_API_KEY" \
  --name prod-crm \
  --database-host db.internal \
  --database-name crm
```

O script expõe utilitários para:

1. Criar definições de conector (database, REST ou transcrição).
2. Iniciar um job usando a definição recém-criada.
3. Fazer _polling_ de `/api/admin/ingest/jobs/<JOB_ID>` para coletar `job_metadata`, `sync_state` e históricos de versão.
4. Listar logs incrementais com `GET /api/admin/ingest/jobs/<JOB_ID>/logs?offset=<n>`.

Veja o código para exemplos adicionais de payloads, incluindo anexar `connector_metadata` e enviar credenciais inline.

> Consulte também [`OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md) para um passo a passo completo de automação e governança dos conectores.

### Práticas de segredos

Credenciais fornecidas às rotas admin são armazenadas em texto claro no banco – por isso recomenda-se:

1. Gerar os segredos dinamicamente (por exemplo, via HashiCorp Vault, AWS Secrets Manager ou Azure Key Vault) e injectá-los somente no momento da chamada.
2. Caso a organização exija criptografia em repouso, configure camadas externas como KMS na infraestrutura do banco ou insira lógica customizada em `app/routers/admin_ingest_api.py` para criptografar `credentials` antes de persistir.
3. Nunca envie apenas referências (`secret_id`); resolva o valor real e inclua `credentials.values` ou `credentials.token`.

## Testes

- **Backend**: garanta que o Postgres esteja disponível (ex.: `docker compose up -d db`) e execute:

  ```bash
  pytest
  ```

- **Frontend**: dentro de `frontend/`, instale as dependências e rode os testes com Vitest/Testing Library:

  ```bash
  cd frontend
  npm test
  ```

- **Suítes direcionadas**: use marcadores do Pytest para executar apenas partes críticas, como `pytest -k "connector or ingest"`.

### Ambiente de testes avançados

Os testes que cobrem conectores exigem alguns recursos adicionais:

- **Banco de dados de exemplo**: `testing.postgresql` sobe um Postgres efêmero. Instale o pacote (já listado em `requirements.txt`) e tenha `libpq` disponível. Nenhuma configuração extra é necessária.
- **Serviços de transcrição**: os testes utilizam `MockTranscriptionProvider`, portanto não precisam de AWS ou Whisper instalados. Para validar provedores reais, configure as dependências opcionais (`boto3`, `faster-whisper`/`openai-whisper`) e defina variáveis como `AWS_REGION` e `AWS_PROFILE`/`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`.
- **Fixtures de mídia**: `tests/test_transcription_connector.py` gera arquivos WAV sintéticos automaticamente; não é preciso manter amostras no repositório.

Execute:

```bash
docker compose up -d db  # banco usado pelos testes de API/admin
pytest -k "connector or ingest"  # roda apenas as suítes relacionadas
```

Para rodar a suíte inteira, garanta que `npm install && npm test` também seja executado dentro de `frontend/`.

### Source management

```bash
# List known sources
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/api/admin/ingest/sources
```

Connector definitions follow the same RBAC rules: viewers can list metadata, while only operators can create, update, or delete entries. Secrets must be supplied inline—requests that only provide a `secret_id` without actual credentials are rejected with **400 Bad Request** to prevent storing unresolved references.

```bash
# List connector definitions (viewer)
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/api/admin/ingest/connector_definitions

# Create a reusable database connector (operator)
curl -X POST http://localhost:8000/api/admin/ingest/connector_definitions \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "prod-crm",
        "type": "database",
        "params": {"host": "db", "database": "crm", "queries": [{"sql": "SELECT id, notes FROM customers", "text_column": "notes", "id_column": "id"}]},
        "credentials": {"username": "reader", "password": "s3cret"}
      }'
```

### Admin UI

Admin features live under `frontend/src/admin` inside the main frontend project. To work on them, start the frontend dev server and visit the `/admin` route:

```bash
cd frontend
npm install
npm run dev
```

If you need to serve the UI from another origin, set `ADMIN_UI_ORIGINS` before starting the backend so CORS allows the requests.

## Dicas francas

- PDFs escaneados (sem texto) exigem **OCR** (ex.: Tesseract). Habilite com `--ocr` (opcionalmente `--ocr-lang`) ou `ENABLE_OCR=1`/`OCR_LANG`.
- A busca agora ocorre em duas etapas: (1) recuperação vetorial via pgvector, (2) reranqueamento léxico com BM25 nos candidatos.
- Benefícios: melhora a precisão do top-K final em consultas curtas/termos específicos, com custo baixo.
- Implementação:
  - O backend busca um conjunto maior (pré-K = `max(k*4, 20)`) e aplica BM25 para ordenar e cortar para `k`.
  - Código: `app/rag.py` (`_bm25_rerank` e `build_context`).
- Ajustes: valores são fixos no código; podemos expor variáveis se quiser calibrar `k`/`pré-K`.
- Endpoint para registrar feedback de respostas e apoiar melhoria contínua.

  - `question` (string, opcional): pergunta do usuário.
  - `sessionId` (string, opcional): sessão/conversa.

    "question": "Como configuro potência de leitura?",

- Persistência: registros na tabela `feedbacks` (migração `migrations/005_add_feedback_table.sql`).
- Inicialização: o backend garante schema/migrações antes de inserir (idempotente).
- Métricas: simples agregar por `helpful=false`, período (`created_at`) e origem (`session_id`/`sources`). Se quiser, expomos endpoints de agregação.

- A busca agora ocorre em duas etapas: (1) recuperação vetorial via pgvector, (2) reranqueamento léxico com BM25 nos candidatos.
- Benefícios: melhora a precisão do top-K final em consultas curtas/termos específicos, com custo baixo.
- Implementação:
  - O backend busca um conjunto maior (pré-K = `max(k*4, 20)`) e aplica BM25 para ordenar e cortar para `k`.
  - Embeddings: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (mean pooling).
  - Código: `app/rag.py` (`_bm25_rerank` e `build_context`).
- Ajustes: valores são fixos no código; podemos expor variáveis se quiser calibrar `k`/pré-K.

## Feedback de Qualidade

- Endpoint para registrar feedback de respostas e apoiar melhoria contínua.
- Rota: `POST /api/feedback`
- Corpo (JSON):
  - `helpful` (bool): se a resposta ajudou.
  - `question` (string, opcional): pergunta do usuário.
  - `answer` (string, opcional): resposta fornecida.
  - `sessionId` (string, opcional): sessão/conversa.
  - `sources` (json, opcional): fontes citadas (ex.: lista com `path`, `chunk_index`, etc.).
- Exemplo (curl):

```bash
curl -s -X POST http://localhost:8000/api/feedback \
  -H 'Content-Type: application/json' \
  -d '{
    "helpful": true,
    "question": "Como configuro potencia de leitura?",
    "answer": "...",
    "sessionId": "S123",
    "sources": [{"path": "/app/docs/manual.pdf", "chunk_index": 0}]
  }'
```

- Persistência: registros na tabela `feedbacks` (migração `migrations/005_add_feedback_table.sql`).
- Inicialização: o backend garante schema/migrações antes de inserir (idempotente).
- Métricas: simples agregar por `helpful=false`, período (`created_at`) e origem (`session_id`/`sources`). Se quiser, expomos endpoints de agregação.

## Contribuição

Consulte o [CONTRIBUTING.md](CONTRIBUTING.md) para obter o checklist completo de ambiente, ferramentas de qualidade e documentação necessária antes de abrir um PR.

## Documentação adicional

### Arquitetura e Desenvolvimento

- [ARCHITECTURE.md](ARCHITECTURE.md) – visão de alto nível dos componentes e fluxos.
- [API_REFERENCE.md](API_REFERENCE.md) – contratos das rotas HTTP expostas.
- [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) – convenções para o app React/Vite.
- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) – narrativa executiva e funcionalidades.

### Operação e Deploy

- [DEPLOYMENT.md](DEPLOYMENT.md) – estratégias de deploy adicionais e práticas recomendadas.
- [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) – automação e governança dos conectores.

### Releases e Produção

- [PRODUCTION_RELEASE_REQUIREMENTS.md](PRODUCTION_RELEASE_REQUIREMENTS.md) – requisitos completos para preparar releases de produção.
- [VERSION_STRATEGY.md](VERSION_STRATEGY.md) – estratégia de versionamento semântico.
- [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) – checklist passo-a-passo para criar releases.
- [CHANGELOG.md](CHANGELOG.md) – histórico de mudanças e releases.
