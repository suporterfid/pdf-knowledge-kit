# Guia de Onboarding

## 1. Boas-vindas e visão geral

Bem-vindo(a) ao **PDF Knowledge Kit**! Este projeto transforma PDFs e Markdown em uma base de conhecimento com busca semântica, disponibilizando um backend FastAPI e um frontend React prontos para agentes de IA. Para uma visão completa de arquitetura, conectores e fluxo de ingestão, consulte o arquivo [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md).

## 2. Pré-requisitos

Antes de começar, garanta que seu ambiente possui as seguintes versões e ferramentas:

- **Python** 3.11 ou 3.12 (backend e scripts de ingestão)【F:PROJECT_OVERVIEW.md†L7-L26】【F:DEPLOYMENT.md†L10-L18】
- **Node.js** 20 e **npm** (frontend com Vite/Vitest)【F:PROJECT_OVERVIEW.md†L10-L13】【F:DEPLOYMENT.md†L10-L18】
- **Docker Engine** 24+ e Docker Compose plugin 2.20+ (stack completa)【F:DEPLOYMENT.md†L10-L18】
- **PostgreSQL 16** com extensão **pgvector** (local via Docker)【F:PROJECT_OVERVIEW.md†L8-L16】
- Dependências opcionais para OCR: `tesseract-ocr` e pacotes de idioma (`eng`, `por`, `spa`)【F:PROJECT_OVERVIEW.md†L20-L34】

## 3. Configuração do ambiente

1. **Clonar o repositório**
   ```bash
   git clone https://github.com/<sua-org>/pdf-knowledge-kit.git
   cd pdf-knowledge-kit
   ```
2. **Criar ambiente virtual Python e instalar dependências**
   ````bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt  # use requirements.lock para versões fixas
   ```【F:README.md†L34-L64】
   ````
3. **Instalar dependências do frontend**
   ````bash
   cd frontend
   npm install  # ou npm ci para builds reprodutíveis
   cd ..
   ```【F:README.md†L82-L96】
   ````
4. **Configurar variáveis de ambiente**
   ````bash
   cp .env.example .env
   # edite valores como DATABASE_URL, ADMIN_API_KEY, OPENAI_API_KEY etc.
   ```【F:PROJECT_OVERVIEW.md†L33-L56】【F:DEPLOYMENT.md†L18-L40】
   ````

## 4. Executando localmente

- **Stack completa via Docker Compose**

  ```bash
  docker compose up --build
  ```

  Isso inicia Postgres/pgvector, backend FastAPI e frontend Vite.【F:DEPLOYMENT.md†L42-L68】

- **Backend manual (fora do Docker)**

  ```bash
  docker compose up -d db  # sobe apenas o Postgres
  uvicorn app.main:app --reload
  ```

  API disponível em `http://localhost:8000` com documentação Swagger em `/docs`.【F:PROJECT_OVERVIEW.md†L36-L49】【F:README.md†L101-L119】

- **Frontend manual**
  ````bash
  cd frontend
  npm run dev  # http://localhost:5173
  ```【F:README.md†L120-L133】
  ````

## 5. Rodando testes

- **Backend**: dentro do venv ou do container, execute `pytest`.
  ````bash
  pytest
  ```【F:PROJECT_OVERVIEW.md†L36-L42】【F:README.md†L110-L112】
  ````
- **Frontend**: na pasta `frontend`, rode os testes com Vitest.
  ````bash
  cd frontend
  npm test
  ```【F:PROJECT_OVERVIEW.md†L74-L78】
  ````

## 6. Estrutura do projeto

- `app/` – aplicação FastAPI com serviços de ingestão, rotas REST e utilitários.【F:PROJECT_OVERVIEW.md†L13-L22】
- `frontend/` – cliente React/TypeScript com contexto de chat e console admin.【F:PROJECT_OVERVIEW.md†L13-L22】【F:FRONTEND_GUIDE.md†L7-L55】
- `tests/` – testes backend e frontend (pytest, Vitest).【F:PROJECT_OVERVIEW.md†L13-L22】【F:FRONTEND_GUIDE.md†L56-L83】
- `migrations/` – scripts de evolução de banco e schema inicial em `schema.sql`.【F:PROJECT_OVERVIEW.md†L13-L22】
- `tools/` – scripts utilitários como ingestão e consultas CLI.【F:PROJECT_OVERVIEW.md†L13-L22】
- `docker-compose.yml`/`Dockerfile` – orquestração da stack e imagem de produção.【F:PROJECT_OVERVIEW.md†L13-L22】【F:DEPLOYMENT.md†L52-L94】

## 7. Fluxo de contribuição

1. Crie uma branch a partir de `main` para cada feature ou correção.
2. Siga o estilo **PEP 8** para Python e os padrões descritos no guia do frontend (componentização, Tailwind e contexts).【F:FRONTEND_GUIDE.md†L85-L159】
3. Execute `pytest` e `npm test` antes de abrir o PR.
4. Abra o Pull Request com descrição clara, incluindo testes executados e impacto.
5. Solicite revisão e mantenha commits pequenos e descritivos.

## 8. Dicas de produtividade

- **Depuração**: o backend expõe `debugpy` quando rodado via Docker Compose, permitindo attach do VS Code.【F:DEPLOYMENT.md†L52-L68】
- **APIs**: acesse Swagger UI em `http://localhost:8000/docs` para explorar endpoints.【F:README.md†L101-L119】
- **Frontend**: UI disponível em `http://localhost:5173` (modo dev do Vite).【F:DEPLOYMENT.md†L62-L68】
- **Logs**: acompanhe `docker compose logs -f app` ou verifique arquivos em `logs/` configurados via `.env`.【F:DEPLOYMENT.md†L94-L112】
- **Monitoramento**: métrica Prometheus em `http://localhost:8000/api/metrics` (quando habilitado).【F:README.md†L70-L89】

## 9. Próximos passos sugeridos

1. Rodar a ingestão local de PDFs/Markdown:
   ```bash
   python ingest.py --docs ./docs  # use --ocr ou ENABLE_OCR=1 para PDFs escaneados
   ```
2. Consultar a base com a ferramenta CLI:
   ```bash
   python query.py --q "Qual é o fluxo de ingestão?" --k 5
   ```
3. Explorar o chat no frontend e validar respostas com fontes citadas.
4. Opcional: revisar `OPERATOR_GUIDE.md` e `API_REFERENCE.md` para operações avançadas.【F:PROJECT_OVERVIEW.md†L118-L136】

## 10. Links úteis

- [ARCHITECTURE.md](ARCHITECTURE.md) – detalhes de módulos backend/frontend e relacionamentos.【F:ARCHITECTURE.md†L1-L63】
- [DEPLOYMENT.md](DEPLOYMENT.md) – guia completo de infraestrutura, variáveis e CI/CD.【F:DEPLOYMENT.md†L1-L118】
- [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) – estrutura, componentes e padrões de código no React.【F:FRONTEND_GUIDE.md†L1-L130】
- [API_REFERENCE.md](API_REFERENCE.md) – documentação das rotas disponíveis (avançado).
- [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) – playbook operacional para monitoramento e suporte (avançado).

Bom trabalho! Sinta-se à vontade para pedir ajuda ao time sempre que tiver dúvidas.
