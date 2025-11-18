# ISSUE-001: Incompatibilidade Crítica de Rotas de Autenticação

## Status
✅ **RESOLVIDO** - Implementado em 18/11/2025

## Severidade
🔴 **CRÍTICA** - Bloqueia completamente o uso da aplicação

## Descrição
Existe uma incompatibilidade total entre as rotas de autenticação chamadas pelo frontend e as rotas expostas pelo backend. Isso causa falhas 404 em todas as operações de autenticação (login, registro, refresh, logout), resultando em loops infinitos de retry que congelam o navegador.

## Resolução Implementada
- ✅ Atualizadas todas as rotas de autenticação em `frontend/src/auth/AuthProvider.tsx`
- ✅ Atualizado mock de teste em `frontend/src/chat.test.tsx`
- ✅ Todos os testes passando (16/16)

## Evidências

### Rotas Chamadas pelo Frontend
Localização: `frontend/src/auth/AuthProvider.tsx`

```typescript
// Linha 290: Refresh
const response = await fetch('/api/auth/refresh', {
  method: 'POST',
  // ...
});

// Linha 343: Login
const response = await fetch('/api/auth/login', {
  method: 'POST',
  // ...
});

// Linha 371: Register
const response = await fetch('/api/auth/register', {
  method: 'POST',
  // ...
});

// Linha 399: Logout
await fetch('/api/auth/logout', {
  method: 'POST',
  // ...
});
```

### Rotas Expostas pelo Backend
Localização: `app/routers/tenant_accounts.py`

```python
router = APIRouter(prefix="/api/tenant/accounts", tags=["tenant-accounts"])

@router.post("/login", response_model=AuthenticatedResponse)  # /api/tenant/accounts/login
@router.post("/register", ...)  # /api/tenant/accounts/register
@router.post("/refresh", ...)   # /api/tenant/accounts/refresh
@router.post("/logout", ...)    # /api/tenant/accounts/logout
```

O router `/api/auth` existe em `app/routers/auth_api.py`, mas apenas expõe:
- `GET /api/auth/roles`

## Impacto

1. **Login impossível**: Usuários não conseguem fazer login
2. **Registro impossível**: Novos usuários não conseguem se cadastrar
3. **Loops infinitos**: AuthProvider tenta fazer refresh automaticamente ao carregar a página, falhando e retentando indefinidamente
4. **Congelamento do navegador**: O loop de requests consome todos os recursos do navegador

## Cenário de Reprodução

1. Acessar `http://localhost:5173`
2. Se houver refresh token no localStorage, AuthProvider tenta automaticamente fazer refresh
3. Request para `/api/auth/refresh` retorna 404
4. AuthProvider retenta (sem limite)
5. Browser congela por falta de recursos

## Soluções Propostas

### Opção A: Atualizar Frontend (Recomendada)
**Prioridade**: Alta
**Complexidade**: Baixa
**Impacto**: Mínimo

Atualizar as URLs no `AuthProvider.tsx` para usar `/api/tenant/accounts/*`:

```typescript
// Em AuthProvider.tsx, substituir:
'/api/auth/refresh' → '/api/tenant/accounts/refresh'
'/api/auth/login' → '/api/tenant/accounts/login'
'/api/auth/register' → '/api/tenant/accounts/register'
'/api/auth/logout' → '/api/tenant/accounts/logout'
```

**Vantagens**:
- Mudança mínima e localizada
- Não afeta API existente
- Mantém compatibilidade com possíveis clientes externos

**Desvantagens**:
- URLs mais longas

### Opção B: Adicionar Aliases no Backend
**Prioridade**: Baixa
**Complexidade**: Média
**Impacto**: Médio

Adicionar rotas alias em `app/routers/auth_api.py` que redirecionam para `tenant_accounts`:

```python
# Em auth_api.py
@router.post("/login")
async def login_alias(payload: LoginRequest, request: Request, session: SessionDep):
    # Delegar para tenant_accounts.login
    pass
```

**Vantagens**:
- Frontend não precisa mudar
- Pode manter ambas APIs

**Desvantagens**:
- Duplicação de código
- Mais difícil de manter
- Confusão sobre qual API usar

### Opção C: Mover Rotas para /api/auth
**Prioridade**: Baixa
**Complexidade**: Alta
**Impacto**: Alto

Mover todas as rotas de `tenant_accounts.py` para `auth_api.py`:

**Vantagens**:
- URLs mais curtas e intuitivas
- Consolidação de rotas de autenticação

**Desvantagens**:
- Breaking change grande
- Pode afetar clientes externos
- Requer refatoração significativa

## Recomendação
Implementar **Opção A** imediatamente para desbloquear o desenvolvimento. A mudança é cirúrgica, localizada e de baixo risco.

## Testes Necessários

1. **Teste de Login**: Verificar que login funciona com nova rota
2. **Teste de Registro**: Verificar que registro funciona
3. **Teste de Refresh**: Verificar que refresh automático não causa loop
4. **Teste de Logout**: Verificar que logout funciona corretamente
5. **Teste de Performance**: Garantir que não há mais loops infinitos

## Arquivos Afetados

### Frontend (Opção A)
- `frontend/src/auth/AuthProvider.tsx` (linhas 290, 343, 371, 399)

### Testes a Atualizar
- `frontend/src/chat.test.tsx` (mock de login)
- `frontend/src/admin/__tests__/*.test.tsx` (mocks de auth)

## Prioridade de Implementação
🔴 **URGENTE** - Deve ser corrigido antes de qualquer outro trabalho

## Estimativa
- Implementação: 15 minutos
- Testes: 30 minutos
- Total: 45 minutos

## Dependências
Nenhuma - pode ser implementado imediatamente

## Tags
#bug #crítico #autenticação #frontend #backend #api-mismatch
