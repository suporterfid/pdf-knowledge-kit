# ISSUE-002: ConfigProvider Causa Chamadas API Prematuras

## Severidade
🔴 **CRÍTICA** - Contribui para loops infinitos e consumo excessivo de recursos

## Descrição
O `ConfigProvider` faz chamadas autenticadas à API `/api/config` antes que a autenticação esteja completamente inicializada. Isso causa tentativas de chamadas autenticadas que podem falhar, serem retentadas automaticamente pelo `fetchWithAuth`, e contribuir para o congelamento do navegador.

## Evidências

### Código Problemático
Localização: `frontend/src/config.tsx`

```typescript
export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppConfig>(() => {
    const injected = (window as any).__CONFIG__ || {};
    return { ...defaultConfig, ...injected } as AppConfig;
  });
  const apiFetch = useAuthenticatedFetch();  // ⚠️ Obtém fetch autenticado

  useEffect(() => {
    apiFetch('/api/config')  // ⚠️ Chama API imediatamente sem verificar auth status
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => setConfig((prev) => ({ ...prev, ...data })))
      .catch(() => {});  // ⚠️ Erro silenciosamente ignorado
  }, [apiFetch]);
  // ...
}
```

### Hierarquia de Providers
Localização: `frontend/src/main.tsx`

```typescript
<ThemeProvider>
  <AuthProvider>           {/* Auth ainda está inicializando */}
    <ConfigProvider>       {/* ConfigProvider já tenta chamar API */}
      <App />
    </ConfigProvider>
  </AuthProvider>
</ThemeProvider>
```

### Comportamento do useAuthenticatedFetch
Localização: `frontend/src/auth/AuthProvider.tsx` (linhas 452-486)

O `fetchWithAuth` automaticamente:
1. Tenta obter um access token válido via `ensureAccessToken()`
2. Se token expirou, tenta fazer refresh
3. Se refresh retorna 401, tenta novamente
4. Pode causar cascata de chamadas de refresh

## Impacto

1. **Chamadas desnecessárias**: API é chamada mesmo quando usuário não está autenticado
2. **Cascata de erros**: Falhas na autenticação propagam para config fetch
3. **Loops de retry**: Combined com ISSUE-001, cria múltiplos loops concorrentes
4. **Performance degradada**: Múltiplas chamadas HTTP simultâneas sobrecarregam o navegador
5. **UX ruim**: Atrasos na inicialização mesmo quando não é necessário

## Cenário de Reprodução

1. Usuário abre aplicação pela primeira vez (sem refresh token)
2. `AuthProvider` inicia em estado 'loading'
3. `ConfigProvider` imediatamente chama `apiFetch('/api/config')`
4. `fetchWithAuth` tenta obter token (que ainda não existe)
5. Pode tentar refresh (que falha por não ter refresh token)
6. Request para `/api/config` é feito sem autenticação ou com token inválido
7. Backend pode rejeitar a requisição
8. Se combinado com ISSUE-001, cria múltiplos loops concorrentes

## Análise de Root Cause

### Problema 1: Config não deveria requerer autenticação
O endpoint `/api/config` (em `app/main.py`) é público e não requer autenticação:

```python
@app.get("/api/config")
async def config():
    """Expose selected frontend configuration from environment variables."""
    return {
        "BRAND_NAME": os.getenv("BRAND_NAME", "PDF Knowledge Kit"),
        # ...
    }
```

Logo, não faz sentido usar `useAuthenticatedFetch()` para chamá-lo.

### Problema 2: Dependência desnecessária
Config é informação estática que não depende do usuário autenticado. Deve ser carregada antes ou independentemente da autenticação.

## Soluções Propostas

### Opção A: Usar fetch nativo para /api/config (Recomendada)
**Prioridade**: Alta
**Complexidade**: Baixa
**Impacto**: Mínimo

Substituir `useAuthenticatedFetch` por `fetch` nativo:

```typescript
export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppConfig>(() => {
    const injected = (window as any).__CONFIG__ || {};
    return { ...defaultConfig, ...injected } as AppConfig;
  });

  useEffect(() => {
    // Usar fetch nativo já que /api/config é público
    fetch('/api/config')
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => setConfig((prev) => ({ ...prev, ...data })))
      .catch((err) => {
        console.warn('Failed to load config from API, using defaults:', err);
      });
  }, []); // Remove apiFetch da dependência

  return (
    <ConfigContext.Provider value={config}>{children}</ConfigContext.Provider>
  );
}
```

**Vantagens**:
- Remove dependência circular com AuthProvider
- Config carrega independentemente do estado de autenticação
- Mais rápido (não espera token)
- Mais simples e direto
- Elimina possível fonte de loops

**Desvantagens**:
- Nenhuma significativa

### Opção B: Adiar carregamento até auth estar pronto
**Prioridade**: Média
**Complexidade**: Média
**Impacto**: Médio

```typescript
export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const { state } = useAuth();
  const apiFetch = useAuthenticatedFetch();
  
  useEffect(() => {
    // Só carregar config quando auth não estiver mais em 'loading'
    if (state.status === 'loading') return;
    
    apiFetch('/api/config')
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => setConfig((prev) => ({ ...prev, ...data })))
      .catch(() => {});
  }, [apiFetch, state.status]);
  // ...
}
```

**Vantagens**:
- Mantém uso de fetchWithAuth
- Evita chamadas prematuras

**Desvantagens**:
- Atrasa carregamento desnecessariamente
- Mantém complexidade desnecessária
- Config ainda não pode ser usado por usuários não autenticados

### Opção C: Carregar config antes de montar React
**Prioridade**: Baixa
**Complexidade**: Alta
**Impacto**: Alto

Carregar config no HTML antes de montar a aplicação React:

```html
<script>
  fetch('/api/config')
    .then(res => res.json())
    .then(data => { window.__CONFIG__ = data; })
    .finally(() => {
      // Montar React aqui
    });
</script>
```

**Vantagens**:
- Config sempre disponível ao montar
- Elimina race condition completamente

**Desvantagens**:
- Arquitetura mais complexa
- Dificulta SSR/SSG futuros
- Atrasa renderização inicial

## Recomendação
Implementar **Opção A** imediatamente. É a solução mais simples, correta e eficiente. O endpoint `/api/config` é público por design, então usar `fetch` nativo é a escolha correta.

## Testes Necessários

1. **Teste de carregamento inicial**: Verificar que config carrega corretamente na primeira visita
2. **Teste sem autenticação**: Verificar que config carrega mesmo sem usuário autenticado
3. **Teste de fallback**: Verificar que defaults são usados se API falhar
4. **Teste de performance**: Medir tempo de carregamento antes e depois
5. **Teste de concorrência**: Verificar que não há mais loops com ISSUE-001 corrigido

## Arquivos Afetados

- `frontend/src/config.tsx` (linhas 22-34)

## Prioridade de Implementação
🔴 **URGENTE** - Deve ser corrigido junto com ISSUE-001

## Estimativa
- Implementação: 10 minutos
- Testes: 20 minutos
- Total: 30 minutos

## Dependências
Nenhuma - pode ser implementado independentemente de ISSUE-001

## Relação com Outras Issues
- **ISSUE-001**: Quando combinadas, as duas issues criam múltiplos loops concorrentes que congelam o navegador
- Corrigir ambas elimina o sintoma de congelamento

## Tags
#bug #crítico #performance #race-condition #frontend #config
