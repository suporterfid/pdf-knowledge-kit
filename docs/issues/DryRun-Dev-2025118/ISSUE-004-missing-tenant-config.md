# ISSUE-004: Configurações de Tenant Token Ausentes no .env.example

## Status
✅ **RESOLVIDO** - Implementado em 18/11/2025

## Severidade
🟡 **MÉDIA** - Afeta deployment e configuração inicial

## Descrição
O arquivo `.env.example` não inclui as variáveis de ambiente necessárias para configuração de tokens JWT multi-tenant (`TENANT_TOKEN_SECRET`, `TENANT_TOKEN_ISSUER`, `TENANT_TOKEN_AUDIENCE`). Isso dificulta a configuração inicial e pode causar erros de autenticação se o backend não conseguir gerar/validar tokens corretamente.

## Resolução Implementada
- ✅ Adicionadas variáveis TENANT_TOKEN_* ao .env.example
- ✅ Incluídos comentários explicativos sobre cada variável
- ✅ Adicionado exemplo de comando para gerar secret seguro
- ✅ Definidos valores de desenvolvimento apropriados
- ✅ Alertas sobre necessidade de mudança em produção

## Evidências

### .env.example atual
Localização: `.env.example`

```bash
# Example environment configuration for pdf-knowledge-kit

# ---------------------------------------------------------------------------
# API keys for admin ingestion endpoints
# Default development values are admin/oper/view
ADMIN_API_KEY=
OP_API_KEY=
VIEW_API_KEY=

# ---------------------------------------------------------------------------
# Database
DATABASE_URL=postgresql://pdfkb:pdfkb@db:5432/pdfkb
PGHOST=db
PGPORT=5432
PGDATABASE=pdfkb
PGUSER=pdfkb
PGPASSWORD=pdfkb

# ... outras configurações ...

# ❌ FALTANDO: Variáveis de tenant token
```

### Variáveis esperadas pelo código
Localização: `app/core/auth.py` (referências verificadas no projeto)

O sistema espera estas variáveis:
- `TENANT_TOKEN_SECRET` - Secret para assinar JWT
- `TENANT_TOKEN_ISSUER` - Issuer claim do JWT
- `TENANT_TOKEN_AUDIENCE` - Audience claim do JWT
- `TENANT_TOKEN_ALGORITHM` (opcional, default: HS256)

### Evidência do uso no README
Localização: `README.md` (linhas 126-134)

```markdown
## Variáveis de ambiente essenciais

| Variável | Descrição |
| -------- | --------- |
| `TENANT_TOKEN_SECRET`, `TENANT_TOKEN_ISSUER`, `TENANT_TOKEN_AUDIENCE` | Parâmetros para assinar e validar JWTs multi-inquilino. `TENANT_TOKEN_ALGORITHM` (padrão `HS256`) é opcional. |
```

O README documenta estas variáveis como essenciais, mas elas não estão no `.env.example`.

## Impacto

### Durante Desenvolvimento
1. **Dificuldade de setup**: Desenvolvedores não sabem quais valores usar
2. **Erros crípticos**: Backend pode falhar ao gerar tokens sem mensagem clara
3. **Tempo perdido**: Desenvolvedores precisam pesquisar documentação ou código
4. **Inconsistência**: Cada desenvolvedor pode usar valores diferentes

### Durante Deployment
1. **Falha de produção**: Deploy pode falhar se variáveis obrigatórias não forem configuradas
2. **Segurança comprometida**: Defaults inseguros podem ser usados
3. **Tokens inválidos**: Sistema pode gerar tokens que não podem ser validados

### Experiência do Usuário
1. **Login falha silenciosamente**: Se tokens não forem gerados corretamente
2. **Sessões não persistem**: Refresh tokens podem ser inválidos
3. **Erros de autorização**: Claims de tenant podem estar incorretas

## Análise de Root Cause

### Por que as variáveis estão faltando?
1. `.env.example` pode ter sido criado antes da implementação multi-tenant
2. Documentação foi atualizada mas `.env.example` foi esquecido
3. Variáveis podem ter defaults no código, levando a falsa impressão de que são opcionais

### Onde são usadas?
Procurando no código:

```bash
# Localizar uso das variáveis
grep -r "TENANT_TOKEN_SECRET" app/
grep -r "TENANT_TOKEN_ISSUER" app/
grep -r "TENANT_TOKEN_AUDIENCE" app/
```

Provavelmente em:
- `app/security/auth.py` ou similar - geração de tokens
- `app/core/auth.py` - validação de tokens
- `app/security/*.py` - funções de autenticação

## Soluções Propostas

### Opção A: Adicionar variáveis ao .env.example (Recomendada)
**Prioridade**: Alta
**Complexidade**: Trivial
**Impacto**: Mínimo

Adicionar seção de tenant tokens ao `.env.example`:

```bash
# ---------------------------------------------------------------------------
# Tenant Authentication (JWT)
# Secret key for signing tenant JWTs. MUST be changed in production.
# Generate with: openssl rand -hex 32
TENANT_TOKEN_SECRET=change-me-in-production-use-strong-random-value

# JWT issuer (typically your domain or app name)
TENANT_TOKEN_ISSUER=pdf-knowledge-kit

# JWT audience (typically your domain or API endpoint)
TENANT_TOKEN_AUDIENCE=pdf-knowledge-kit-api

# JWT signing algorithm (optional, default: HS256)
# TENANT_TOKEN_ALGORITHM=HS256
```

**Vantagens**:
- Solução direta e completa
- Documenta valores esperados
- Inclui comentários explicativos
- Mostra como gerar valores seguros

**Desvantagens**:
- Nenhuma

### Opção B: Adicionar com valores vazios
**Prioridade**: Média
**Complexidade**: Trivial
**Impacto**: Mínimo

```bash
# ---------------------------------------------------------------------------
# Tenant Authentication
TENANT_TOKEN_SECRET=
TENANT_TOKEN_ISSUER=
TENANT_TOKEN_AUDIENCE=
```

**Vantagens**:
- Simples
- Força usuário a definir valores

**Desvantagens**:
- Não documenta o que colocar
- Não mostra como gerar valores seguros
- Menos útil que Opção A

### Opção C: Deixar como opcional com defaults no código
**Prioridade**: Baixa
**Complexidade**: Baixa
**Impacto**: Médio

Implementar defaults seguros no código e deixar variáveis opcionais.

**Vantagens**:
- Funciona "out of the box"

**Desvantagens**:
- Defaults podem ser inseguros para produção
- Obscurece configuração necessária
- Não recomendado para secrets

## Recomendação
Implementar **Opção A** com valores de desenvolvimento e comentários detalhados. Adicionar também seção no README explicando:
1. Como gerar valores seguros para produção
2. Por que cada variável é necessária
3. Impacto de não configurar corretamente

## Valores Sugeridos para Desenvolvimento

```bash
# Para desenvolvimento local (NUNCA usar em produção)
TENANT_TOKEN_SECRET=dev-secret-key-change-in-production-123456789abcdef
TENANT_TOKEN_ISSUER=pdf-knowledge-kit-dev
TENANT_TOKEN_AUDIENCE=http://localhost:8000

# Para produção (gerar valores únicos)
# TENANT_TOKEN_SECRET=$(openssl rand -hex 32)
# TENANT_TOKEN_ISSUER=your-domain.com
# TENANT_TOKEN_AUDIENCE=https://api.your-domain.com
```

## Testes Necessários

1. **Teste de configuração completa**: Verificar que app inicia com todas as variáveis configuradas
2. **Teste de variáveis ausentes**: Verificar que app falha gracefully se variáveis obrigatórias estão faltando
3. **Teste de token gerado**: Verificar que tokens são válidos com a configuração do .env.example
4. **Teste de refresh**: Verificar que refresh tokens funcionam com a configuração
5. **Teste de documentação**: Verificar que instruções no .env.example são claras e suficientes

## Arquivos Afetados

### Criar/Modificar
- `.env.example` - Adicionar seção de tenant tokens

### Verificar/Atualizar
- `README.md` - Garantir que seção de variáveis está sincronizada
- `DEPLOYMENT.md` - Adicionar instruções sobre geração de secrets seguros
- `ONBOARDING.md` - Incluir passo sobre configuração de tenant tokens

## Prioridade de Implementação
🟡 **MÉDIA** - Deve ser incluído antes da próxima release, mas não bloqueia desenvolvimento imediato

## Estimativa
- Implementação: 15 minutos
- Documentação adicional: 20 minutos
- Testes: 15 minutos
- Total: 50 minutos

## Dependências
Nenhuma - pode ser implementado independentemente

## Benefícios Adicionais

1. **Onboarding mais rápido**: Novos desenvolvedores configuram ambiente mais facilmente
2. **Menos erros**: Valores de exemplo previnem erros comuns
3. **Segurança documentada**: Comentários alertam sobre necessidade de mudar em produção
4. **Consistência**: Todos os ambientes de desenvolvimento usam mesma configuração

## Checklist de Implementação

- [ ] Adicionar variáveis ao `.env.example` com valores de desenvolvimento
- [ ] Adicionar comentários explicativos
- [ ] Adicionar exemplo de geração de valores seguros
- [ ] Verificar sincronização com README.md
- [ ] Atualizar DEPLOYMENT.md se necessário
- [ ] Testar que app inicia corretamente com valores do exemplo
- [ ] Documentar processo de rotação de secrets para produção

## Tags
#enhancement #configuration #documentation #deployment #security
