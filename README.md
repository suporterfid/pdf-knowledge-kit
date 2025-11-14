# PDF Knowledge Kit

> Plataforma completa para transformar PDFs, Markdown, planilhas e fontes remotas em uma base vetorial com busca semântica e chat multi-inquilino.

## Visão geral

O PDF Knowledge Kit combina um backend FastAPI, frontend React e um conjunto de ferramentas de ingestão para acelerar projetos de *Retrieval-Augmented Generation* (RAG). A aplicação lê documentos, divide o conteúdo em trechos, gera *embeddings* multilíngues com `fastembed` e grava tudo em um banco PostgreSQL com `pgvector`. A API expõe rotas de chat com *streaming* (SSE), feedback, gerenciamento de agentes e administração de tenants, enquanto o frontend reproduz uma experiência semelhante ao ChatGPT.

A versão atual do pacote é **1.0.1** (veja `app/__version__.py`). Releases oficiais são publicados no GitHub e seguem SemVer; consulte o `CHANGELOG.md` para saber o que mudou em cada entrega.

## Principais recursos

- Multi-inquilino com isolamento por Row Level Security (RLS) e autenticação JWT.
- Ingestão assíncrona de PDFs, Markdown, URLs, consultas SQL, REST e transcrições.
- Busca semântica com `pgvector` e fallback lexical opcional (`rank-bm25`).
- Chat com SSE, histórico, uploads temporários e respostas opcionais via OpenAI.
- Interface React 18 + Vite com temas claro/escuro, destaques de código e notificações.
- Observabilidade com métricas Prometheus e *logging* rotacionado.
- Scripts CLI (`ingest.py`, `query.py`, `embedding.py`) para automação e testes rápidos.
- Pipeline de qualidade com `pytest`, `vitest`, `ruff`, `black`, `mypy` e `bandit`.

## Arquitetura em alto nível

| Camada | Descrição |
| ------ | --------- |
| **Backend (`app/`)** | FastAPI + SQLAlchemy/psycopg. Rotas em `app/routers`, regras de negócio em `app/agents`, `app/conversations`, `app/ingestion`, etc. `app/main.py` monta middlewares (rate limiting, CORS, tenant) e expõe `/api/*`. |
| **Ingestão** | `app/ingestion/service.py` coordena *chunking*, OCR, conectores e gravação de dados. Jobs são rastreados com status e arquivos de log. |
| **RAG** | `app/rag.py` gera contexto com o modelo `paraphrase-multilingual-MiniLM-L12-v2-cls`, registrado em `embedding.py`. |
| **Frontend (`frontend/`)** | React + TypeScript + Tailwind. `npm run build` gera artefatos servidos por FastAPI em `app/static`. |
| **Banco de dados** | `schema.sql` cria a estrutura base (idempotente). Migrações incrementais estão em `migrations/*.sql`. |
| **Ferramentas** | `tools/register_connector.py` registra conectores e acompanha jobs; `tools/print_log_config.py` exibe a configuração efetiva de logs. |

## Pré-requisitos

- **Docker 24+** e **Docker Compose** para a stack completa (opcional, porém recomendado).
- **Python 3.10** com `pip` para o backend.
- **Node.js 18+** e `npm` para o frontend (Vite 5).
- **PostgreSQL 15+** com extensão `pgvector` habilitada.
- _(Opcional)_ `tesseract-ocr` + pacotes de idioma e `poppler-utils` para OCR.

## Configuração rápida com Docker Compose

1. Copie as variáveis padrão:
   ```bash
   cp .env.example .env
   ```
2. Ajuste credenciais do banco, chaves JWT (`TENANT_TOKEN_*`) e chaves de API (OpenAI ou admin) conforme necessário.
3. Suba a stack completa (db, backend, frontend):
   ```bash
   docker compose up --build
   ```
4. Acesse o frontend em `http://localhost:5173` e a documentação da API em `http://localhost:8000/docs`.

Ao finalizar o processo, o script `seed.py` executado no container da API provisiona automaticamente um tenant e um usuário de demonstração, além de ingerir o PDF de exemplo incluído no repositório. Por padrão, os acessos são criados com o e-mail `admin@demo.local` e a senha `ChangeMe123!` (ajuste as variáveis `SEED_ADMIN_EMAIL`/`SEED_ADMIN_PASSWORD` no `.env` para personalizar). **Altere essas credenciais em qualquer ambiente real** e remova os usuários/tenants de teste conforme a política de segurança da sua organização.

O documento padrão encontra-se em `sample_data/example_document.pdf`. Substitua o arquivo pelo conteúdo desejado ou remova-o do diretório para impedir que seja ingerido automaticamente durante o seed.

Use `docker compose up -d db` quando quiser apenas o banco. Para derrubar tudo, execute `docker compose down` (adicione `-v` para limpar volumes, incluindo o banco).

## Configuração local (Python + Node)

```bash
# 1. Clone e crie o ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Instale dependências do backend
pip install -r requirements.txt
pip install -r requirements-dev.txt  # lint, testes e ferramentas auxiliares

# 3. Suba o Postgres com pgvector (ou aponte para uma instância existente)
docker compose up -d db

# 4. Prepare o banco
psql postgresql://pdfkb:pdfkb@localhost:5432/pdfkb -f schema.sql
for migration in migrations/*.sql; do psql postgresql://pdfkb:pdfkb@localhost:5432/pdfkb -f "$migration"; done

# 5. Preencha o arquivo .env
cp .env.example .env
# edite valores como DATABASE_URL, TENANT_TOKEN_SECRET e TENANT_ID

# 6. Instale o frontend
cd frontend
npm install
cd ..
```

Para iniciar os serviços em desenvolvimento:

```bash
# Backend com recarregamento automático
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm run dev  # http://localhost:5173
```

## Criando um tenant para desenvolvimento

A aplicação exige um tenant ativo para configurar `app.tenant_id` no banco. Cadastre uma organização e um usuário administrador via API:

```bash
curl -X POST http://localhost:8000/api/tenant/accounts/register \
  -H 'Content-Type: application/json' \
  -d '{
        "organization_name": "Acme Corp",
        "subdomain": "acme",
        "admin_name": "Alice",
        "admin_email": "alice@acme.dev",
        "password": "Str0ngPass!"
      }'
```

A resposta traz os tokens e o `organization.id`. Configure-o como tenant padrão durante o desenvolvimento:

```bash
export TENANT_ID="<uuid-da-organizacao>"
```

Para autenticar requisições protegidas, reutilize o `access_token` retornado (JWT) no cabeçalho `Authorization: Bearer <token>`. O `refresh_token` pode gerar novos tokens via `/api/tenant/accounts/refresh`.

Durante o desenvolvimento é possível enviar `X-Debug-Tenant: <uuid>` para algumas rotas públicas (chat, feedback, ingestão administrativa), mas o fluxo suportado em produção usa apenas JWTs assinados com `TENANT_TOKEN_SECRET`.

## Variáveis de ambiente essenciais

| Variável | Descrição |
| -------- | --------- |
| `DATABASE_URL` | DSN completo usado pelos *routers* administrativos. Use o mesmo host/porta do Postgres. |
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` | Conexão padrão usada por scripts e serviços internos. |
| `TENANT_ID` | Tenant padrão para scripts CLI e rotas públicas em desenvolvimento. |
| `TENANT_TOKEN_SECRET`, `TENANT_TOKEN_ISSUER`, `TENANT_TOKEN_AUDIENCE` | Parâmetros para assinar e validar JWTs multi-inquilino. `TENANT_TOKEN_ALGORITHM` (padrão `HS256`) é opcional. |
| `ADMIN_API_KEY`, `OP_API_KEY`, `VIEW_API_KEY` | Chaves usadas pelos endpoints de ingestão administrativa (`X-API-Key`). |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_LANG`, `SYSTEM_PROMPT` | Ativam respostas complementares via OpenAI. |
| `DOCS_DIR`, `ENABLE_OCR`, `OCR_LANG` | Ajustes padrão da CLI de ingestão. |
| `UPLOAD_DIR`, `UPLOAD_TTL`, `UPLOAD_MAX_SIZE`, `UPLOAD_MAX_FILES` | Controle de uploads temporários do chat. |
| `LOG_DIR`, `LOG_LEVEL`, `LOG_JSON`, `LOG_RETENTION_DAYS` | Configuração do *logging*. |
| `BRAND_NAME`, `LOGO_URL`, `POWERED_BY_LABEL`, `ADMIN_UI_ORIGINS` | Personalização da UI e CORS para o painel administrativo. |

Consulte `.env.example` para a lista completa.

## Ingestão de conteúdo

### Arquivos locais

```bash
python ingest.py --docs ./docs --tenant-id "$TENANT_ID"
# Habilite OCR quando necessário
python ingest.py --docs ./docs --ocr --ocr-lang eng+por --tenant-id "$TENANT_ID"
```

O script percorre a pasta indicada (recursivamente), registra jobs e aguarda a conclusão. As mesmas funções estão disponíveis via `app.ingestion.service` para uso programático.

### URLs públicas

```bash
python ingest.py --url https://example.com/faq --tenant-id "$TENANT_ID"
python ingest.py --urls-file urls.txt --tenant-id "$TENANT_ID"
```

### Conectores remotos

Use o endpoint `/api/admin/ingest/*` ou o helper `tools/register_connector.py`:

```bash
python tools/register_connector.py register \
  --host http://localhost:8000 \
  --api-key "$ADMIN_API_KEY" \
  --definition connector.json
```

O script publica a definição e dispara jobs para conectores do tipo banco de dados, API REST ou transcrição (Whisper/AWS). Cada job gera um arquivo de log individual acessível via `/api/admin/ingest/jobs/{job_id}/logs`.

### Monitoramento de jobs

- Listar jobs: `GET /api/admin/ingest/jobs`
- Ver detalhes: `GET /api/admin/ingest/jobs/{job_id}`
- Seguir logs em tempo real: `tools/register_connector.py logs --job-id <id>`

## Consulta e chat

### CLI `query.py`

```bash
python query.py --q "Como configuro o conector REST?" --k 5 --tenant-id "$TENANT_ID"
```

O script calcula o embedding da pergunta, executa `kNN` no Postgres e, se configurado, chama a API da OpenAI para redigir uma resposta em linguagem natural.

### API HTTP

- `/api/ask` – responde em JSON (`answer`, trechos e metadados). Aceita `X-Debug-Tenant` em desenvolvimento.
- `/api/chat/stream` – canal SSE para chat passo a passo.
- `/api/conversations/*` – CRUD de conversas e mensagens.
- `/api/feedback` – registra sinalizações de qualidade.

Inclua `Authorization: Bearer <access_token>` para tenants reais.

### Frontend

O frontend consome as rotas acima e oferece:

- Troca de tema claro/escuro.
- Upload temporário de arquivos (validados pelo backend).
- Histórico de conversas com persistência por tenant.
- Destaque de trechos relevantes com citações.

Para gerar o *bundle* de produção:

```bash
cd frontend
npm run build  # artefatos em app/static
```

## Observabilidade

- **Logs:** gravados em `LOG_DIR` (padrão `./logs`) como `app.log` e `access.log`, com rotação diária e retenção configurável. Para inspecionar ao vivo:
  ```bash
  tail -f logs/app.log
  docker compose logs -f app
  ```
- **Métricas Prometheus:** `GET /api/metrics` expõe contadores de requisições, latência e status HTTP.
- **Saúde:** `GET /api/health` confirma dependências básicas.

## Testes e qualidade

Execute as checagens antes de abrir um PR:

```bash
# Testes Python
pytest

# Testes do frontend
cd frontend
npm run test
cd ..

# Lint e formatação
ruff check --config pyproject.toml .
black --check --config pyproject.toml .

# Tipagem e segurança
mypy --config-file pyproject.toml
bandit -c pyproject.toml -r app/
```

Use `ruff format` ou `black` (sem `--check`) para aplicar correções automáticas.

## Estrutura do repositório

```
app/                # Backend FastAPI, serviços de ingestão e domínio
frontend/           # Aplicação React (Vite + Tailwind)
migrations/         # Scripts SQL incrementais
schema.sql          # Esquema base idempotente
ingest.py, query.py # CLIs principais
embedding.py        # Registro do modelo customizado no fastembed
tools/              # Scripts auxiliares (conectores, logs)
```

Documentação complementar:

- `ARCHITECTURE.md` – detalhes da arquitetura.
- `PROJECT_OVERVIEW.md` – visão executiva e mapa dos módulos.
- `OPERATOR_GUIDE.md` e `DEPLOYMENT.md` – operação e deploy.
- `API_REFERENCE.md` – rotas disponíveis.

## Próximos passos

1. Crie um tenant, ingira um conjunto de documentos piloto e valide a precisão usando o `query.py`.
2. Personalize a UI com `BRAND_NAME`, `POWERED_BY_LABEL` e um logotipo próprio.
3. Configure pipelines de ingestão recorrente com os conectores disponíveis.
4. Monitore métricas e ajuste *rate limits*, OCR e tamanhos de chunk conforme as necessidades do seu domínio.
