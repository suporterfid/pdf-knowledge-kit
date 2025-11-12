# AGENTS.md - Configuração do Projeto ChatVolt MVP

## Stack Tecnológica

- Backend: Python 3.10+, FastAPI, PostgreSQL, pgvector
- Frontend: React 18, TypeScript, Vite, Tailwind CSS

## Padrões de Código

- Python: snake_case, type hints obrigatórios, docstrings Google
- TypeScript: camelCase, PascalCase para componentes React
- SQL: snake_case, UUID primary keys, Row Level Security

## Diretrizes de Implementação

- Sempre implementar testes unitários
- Usar Row Level Security para multi-tenancy
- Componentes React funcionais com hooks
- Tratamento de erro consistente
- A cada alteração revisar e se necessário atualizar os arquivos: ARCHITECTURE.md, CHANGELOG.md, DEPLOYMENT.md, FRONTEND_GUIDE.md, OPERATOR_GUIDE.md, PROJECT_OVERVIEW.md, README.md
- Para releases, seguir RELEASE_CHECKLIST.md e atualizar VERSION_STRATEGY.md conforme necessário
