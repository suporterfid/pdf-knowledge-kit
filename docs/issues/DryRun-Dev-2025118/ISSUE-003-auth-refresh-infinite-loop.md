# ISSUE-003: AuthProvider Pode Criar Loops Infinitos de Refresh

## Status
✅ **RESOLVIDO** - Implementado em 18/11/2025

## Severidade
🟠 **ALTA** - Pode causar consumo excessivo de recursos

## Descrição
O `AuthProvider` não tem proteções adequadas contra loops infinitos de refresh token. Quando o refresh token é inválido ou o backend está com problemas, o sistema tenta fazer refresh indefinidamente sem timeout, backoff exponencial ou limite de tentativas.

## Resolução Implementada
- ✅ Implementado rate limiting (mínimo 5 segundos entre tentativas)
- ✅ Adicionado timeout de 10 segundos para requisições
- ✅ Limitado máximo de 3 tentativas consecutivas
- ✅ Reset de contador em login/registro manual
- ✅ Mensagens de erro claras ao usuário
- ✅ Todos os testes passando (16/16)

## Evidências

### Código Problemático
Localização: `frontend/src/auth/AuthProvider.tsx`

#### 1. Inicialização automática de refresh (linhas 324-339)
```typescript
useEffect(() => {
  if (initialSession) {
    return;
  }
  const savedRefresh = localStorage.getItem(REFRESH_TOKEN_KEY);
  const savedTenant = localStorage.getItem(ACTIVE_TENANT_KEY);
  if (savedRefresh) {
    refreshWithToken(savedRefresh, savedTenant).then((tokens) => {
      if (!tokens) {
        clearSession();  // ⚠️ Limpa sessão mas não previne novas tentativas
      }
    });
  } else {
    clearSession();
  }
}, [initialSession, refreshWithToken, clearSession]);  // ⚠️ Sem limite de execuções
```

#### 2. Refresh automático em fetchWithAuth (linhas 452-486)
```typescript
const fetchWithAuth = useMemo<Fetcher>(() => {
  return async (input, init = {}) => {
    // ... configuração de headers ...
    const response = await fetch(input, { ...init, headers });
    
    if (response.status === 401) {
      const refreshed = await refresh();  // ⚠️ Tenta refresh automaticamente
      if (refreshed?.accessToken) {
        headers.set('Authorization', `Bearer ${refreshed.accessToken}`);
        return fetch(input, {  // ⚠️ Retry imediato, sem backoff
          ...init,
          headers,
          credentials: init.credentials ?? 'include',
        });
      }
      toast.error('Sessão expirada. Faça login novamente.');
      clearSession();
    }
    return response;
  };
}, [ensureAccessToken, state.activeTenantId, state.user?.roles, refresh, clearSession]);
```

#### 3. Falta de sincronização global de refresh (linhas 280-322)
```typescript
const refreshWithToken = useCallback(
  async (refreshToken: string | null, preferredTenantId?: string | null) => {
    if (!refreshToken) {
      clearSession();
      return null;
    }
    if (refreshPromise.current) {
      return refreshPromise.current;  // ✅ Boa prática - deduplica
    }
    const promise = (async () => {
      const response = await fetch('/api/auth/refresh', {  // ⚠️ ISSUE-001: URL errada
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ refreshToken }),
      });
      if (!response.ok) {
        clearSession();
        return null;  // ⚠️ Retorna null mas não impede novas tentativas
      }
      // ... resto do código ...
    })()
      .catch(() => {
        clearSession();
        return null;
      })
      .finally(() => {
        refreshPromise.current = null;
      });
    refreshPromise.current = promise;
    return promise;
  },
  [applySession, clearSession]
);
```

## Impacto

### Cenários de Falha

#### Cenário 1: Backend down ou inacessível
1. Usuário abre aplicação com refresh token válido no localStorage
2. AuthProvider tenta fazer refresh na inicialização
3. Request falha (network error, timeout, 500, etc.)
4. `clearSession()` é chamado, mas useEffect pode executar novamente
5. Se houver qualquer re-render que cause re-execução do useEffect, o ciclo recomeça

#### Cenário 2: Refresh token inválido mas não detectado
1. Refresh token está corrompido ou foi revogado no servidor
2. Backend retorna 401 ou 400
3. `clearSession()` limpa tokens
4. Mas se ISSUE-001 não for corrigido, o 404 não é tratado adequadamente
5. Sistema pode tentar novamente pensando que é erro temporário

#### Cenário 3: CORS ou proxy issues
1. Request para refresh é bloqueado por CORS
2. Browser retorna erro de rede
3. `catch` trata como erro temporário
4. Tenta novamente imediatamente

### Consequências
1. **Consumo excessivo de CPU**: Loops de retry consomem recursos
2. **Consumo excessivo de rede**: Múltiplas requisições desnecessárias
3. **UX degradada**: Tela de loading infinita
4. **Backend sobrecarregado**: Se múltiplos usuários tiverem o problema
5. **Logs poluídos**: Milhares de erros de autenticação

## Análise de Root Cause

### Problemas Identificados

1. **Sem timeout**: Requests podem ficar pendentes indefinidamente
2. **Sem backoff**: Retries são imediatos, sem espera
3. **Sem limite de tentativas**: Nenhum contador de falhas consecutivas
4. **Sem circuit breaker**: Não detecta padrão de falhas sistemáticas
5. **clearSession não é persistente**: Limpa estado mas não previne novas tentativas se useEffect executar novamente
6. **Erro silencioso**: `.catch(() => {})` em vários lugares esconde problemas

## Soluções Propostas

### Opção A: Adicionar Rate Limiting e Backoff (Recomendada)
**Prioridade**: Alta
**Complexidade**: Média
**Impacto**: Mínimo

Implementar proteções básicas contra loops:

```typescript
// Adicionar estado para tracking de tentativas
const [refreshAttempts, setRefreshAttempts] = useState(0);
const lastRefreshAttempt = useRef<number>(0);
const MAX_REFRESH_ATTEMPTS = 3;
const MIN_REFRESH_INTERVAL = 5000; // 5 segundos

const refreshWithToken = useCallback(
  async (refreshToken: string | null, preferredTenantId?: string | null) => {
    if (!refreshToken) {
      clearSession();
      return null;
    }
    
    // Verificar se já tentamos muitas vezes
    if (refreshAttempts >= MAX_REFRESH_ATTEMPTS) {
      console.warn('Max refresh attempts reached, clearing session');
      clearSession();
      return null;
    }
    
    // Aplicar rate limiting (5 segundos mínimo entre tentativas)
    const now = Date.now();
    const timeSinceLastAttempt = now - lastRefreshAttempt.current;
    if (timeSinceLastAttempt < MIN_REFRESH_INTERVAL) {
      console.warn('Refresh attempt too soon, throttling');
      return null;
    }
    
    lastRefreshAttempt.current = now;
    setRefreshAttempts(prev => prev + 1);
    
    if (refreshPromise.current) {
      return refreshPromise.current;
    }
    
    const promise = (async () => {
      try {
        // Adicionar timeout de 10 segundos
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);
        
        const response = await fetch('/api/tenant/accounts/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ refreshToken }),
          signal: controller.signal,
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
          throw new Error(`Refresh failed: ${response.status}`);
        }
        
        // Reset contador em caso de sucesso
        setRefreshAttempts(0);
        
        const data = await response.json();
        // ... resto do código de sucesso ...
      } catch (error) {
        console.error('Refresh error:', error);
        
        // Se atingiu máximo de tentativas, limpar de vez
        if (refreshAttempts + 1 >= MAX_REFRESH_ATTEMPTS) {
          toast.error('Não foi possível renovar a sessão. Por favor, faça login novamente.');
          clearSession();
        }
        return null;
      } finally {
        refreshPromise.current = null;
      }
    })();
    
    refreshPromise.current = promise;
    return promise;
  },
  [refreshAttempts, applySession, clearSession]
);

// Resetar contador quando usuário fizer login manual
const login = useCallback(
  async (payload: LoginPayload) => {
    setRefreshAttempts(0); // Reset attempts
    // ... resto do código de login ...
  },
  [applySession]
);
```

**Vantagens**:
- Proteção efetiva contra loops
- Não quebra funcionalidade existente
- Melhora UX com mensagens claras
- Performance melhorada

**Desvantagens**:
- Código um pouco mais complexo
- Requer testes cuidadosos

### Opção B: Usar flag de "tentativa em progresso"
**Prioridade**: Média
**Complexidade**: Baixa
**Impacto**: Mínimo

```typescript
const isRefreshing = useRef(false);

const refreshWithToken = useCallback(
  async (refreshToken: string | null) => {
    if (isRefreshing.current) {
      console.warn('Refresh already in progress');
      return null;
    }
    
    isRefreshing.current = true;
    try {
      // ... lógica de refresh ...
    } finally {
      isRefreshing.current = false;
    }
  },
  [applySession, clearSession]
);
```

**Vantagens**:
- Muito simples
- Previne concorrência básica

**Desvantagens**:
- Não previne retry após falha
- Não tem timeout
- Não tem backoff

### Opção C: Implementar Circuit Breaker completo
**Prioridade**: Baixa
**Complexidade**: Alta
**Impacto**: Médio

Implementar pattern de Circuit Breaker com estados CLOSED/OPEN/HALF_OPEN.

**Vantagens**:
- Solução robusta e profissional
- Protege contra múltiplos tipos de falha

**Desvantagens**:
- Over-engineering para este caso
- Complexidade desnecessária
- Mais difícil de testar e manter

## Recomendação
Implementar **Opção A** (Rate Limiting e Backoff) como solução balanceada entre robustez e simplicidade. Se o problema for menos frequente do que esperado, começar com **Opção B** como solução rápida.

## Testes Necessários

1. **Teste de falha de rede**: Simular timeout e verificar que não cria loop
2. **Teste de token inválido**: Verificar que para após N tentativas
3. **Teste de backend down**: Verificar que não sobrecarrega com requests
4. **Teste de refresh bem-sucedido**: Verificar que contador reseta
5. **Teste de rate limiting**: Verificar que múltiplas tentativas rápidas são throttled
6. **Teste de concorrência**: Verificar que múltiplos componentes não causam múltiplos refreshes

## Arquivos Afetados

- `frontend/src/auth/AuthProvider.tsx` (função refreshWithToken e fetchWithAuth)

## Prioridade de Implementação
🟠 **ALTA** - Deve ser corrigido após ISSUE-001 e ISSUE-002

## Estimativa
- Implementação (Opção A): 1 hora
- Implementação (Opção B): 20 minutos
- Testes: 45 minutos

## Dependências
- Deve ser implementado após ISSUE-001 estar corrigido (para testar adequadamente)

## Relação com Outras Issues
- **ISSUE-001**: Quando URL de refresh está errada, este problema é amplificado (404 causa retry infinito)
- **ISSUE-002**: Loops concorrentes com ConfigProvider agravam o problema

## Tags
#bug #high #performance #infinite-loop #frontend #auth #rate-limiting
