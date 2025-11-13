# Guia de Contribuição

Obrigado por contribuir com o **PDF Knowledge Kit**! Para manter a qualidade do projeto, siga as etapas abaixo antes de abrir um pull request:

1. **Prepare o ambiente**
   - Use Python 3.10+.
   - Crie um ambiente virtual e instale as dependências principais:
     ```bash
     pip install -r requirements.txt
     ```
   - Instale as ferramentas de apoio ao desenvolvimento:
     ```bash
     pip install -r requirements-dev.txt
     ```

2. **Garanta qualidade e segurança**
   - Execute os validadores locais:
     ```bash
     ruff check .
     black --check .
     mypy --config-file pyproject.toml
     bandit -c pyproject.toml -r app/
     ```
   - Aplique correções com `ruff format` ou `black` quando necessário.

3. **Rode os testes automatizados**
   - Backend: `pytest`
   - Frontend: `cd frontend && npm test`

4. **Atualize a documentação**
   - Revise e ajuste arquivos como `README.md`, `DEPLOYMENT.md`, `ARCHITECTURE.md` e demais guias se a alteração impactar os tópicos cobertos.

5. **Abra o PR**
   - Descreva claramente as mudanças e destaque qualquer impacto em APIs, migrações de banco ou configurações.

Seguindo estas etapas alinhadas com as diretrizes do projeto (type hints obrigatórios, testes e documentação atualizada), garantimos um fluxo de revisão mais rápido e releases previsíveis. Obrigado pelo suporte!
