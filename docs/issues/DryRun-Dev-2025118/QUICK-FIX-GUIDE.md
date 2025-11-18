# Guia Rápido de Correção - Browser Freeze Issue

## TL;DR - Correção Mínima

Se você só quer desbloquear o desenvolvimento **agora**, faça estas duas mudanças:

### 1. Corrigir Rotas de Autenticação (2 minutos)

Edite `frontend/src/auth/AuthProvider.tsx`:

```typescript
// ANTES (linha ~290)
const response = await fetch('/api/auth/refresh', {

// DEPOIS
const response = await fetch('/api/tenant/accounts/refresh', {

// ===

// ANTES (linha ~343)
const response = await fetch('/api/auth/login', {

// DEPOIS
const response = await fetch('/api/tenant/accounts/login', {

// ===

// ANTES (linha ~371)
const response = await fetch('/api/auth/register', {

// DEPOIS
const response = await fetch('/api/tenant/accounts/register', {

// ===

// ANTES (linha ~399)
await fetch('/api/auth/logout', {

// DEPOIS
await fetch('/api/tenant/accounts/logout', {
```

**Buscar e substituir**:
```bash
cd frontend/src/auth
sed -i "s|'/api/auth/refresh'|'/api/tenant/accounts/refresh'|g" AuthProvider.tsx
sed -i "s|'/api/auth/login'|'/api/tenant/accounts/login'|g" AuthProvider.tsx
sed -i "s|'/api/auth/register'|'/api/tenant/accounts/register'|g" AuthProvider.tsx
sed -i "s|'/api/auth/logout'|'/api/tenant/accounts/logout'|g" AuthProvider.tsx
```

### 2. Corrigir ConfigProvider (1 minuto)

Edite `frontend/src/config.tsx`:

```typescript
// ANTES (linhas 22-34)
export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppConfig>(() => {
    const injected = (window as any).__CONFIG__ || {};
    return { ...defaultConfig, ...injected } as AppConfig;
  });
  const apiFetch = useAuthenticatedFetch();

  useEffect(() => {
    apiFetch('/api/config')
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => setConfig((prev) => ({ ...prev, ...data })))
      .catch(() => {});
  }, [apiFetch]);

// DEPOIS
export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppConfig>(() => {
    const injected = (window as any).__CONFIG__ || {};
    return { ...defaultConfig, ...injected } as AppConfig;
  });

  useEffect(() => {
    fetch('/api/config')  // ← Usar fetch nativo, API é pública
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => setConfig((prev) => ({ ...prev, ...data })))
      .catch((err) => {
        console.warn('Failed to load config:', err);
      });
  }, []);  // ← Remover apiFetch das dependências
```

### 3. Rebuild e Teste

```bash
cd frontend
npm run build
cd ..

# Se estiver usando Docker
docker compose restart app

# Testar
# Abrir http://localhost:5173
# Verificar que login funciona
```

## Verificação Rápida

### ✅ Se funcionou, você verá:
- Tela de login carrega normalmente
- Não há loops de requisições no DevTools Network
- Login funciona
- Browser não congela

### ❌ Se ainda tem problemas:
1. Limpe o cache do browser (Ctrl+Shift+Del)
2. Limpe localStorage:
   ```javascript
   localStorage.clear()
   location.reload()
   ```
3. Verifique se o backend está rodando:
   ```bash
   curl http://localhost:8000/api/health
   ```
4. Veja logs do backend:
   ```bash
   docker compose logs -f app
   ```

## Por Que Isso Funciona?

### Problema Original
1. Frontend chamava rotas `/api/auth/*` que não existem → 404
2. AuthProvider tentava fazer refresh infinitamente → loop
3. ConfigProvider tentava buscar config com auth falha → mais loops
4. Loops concorrentes consumiam recursos → browser congela

### Solução
1. Apontar para rotas corretas `/api/tenant/accounts/*` → sucesso
2. Remover auth desnecessária do config → menos chamadas
3. Sem loops → browser feliz

## Proteções Adicionais (Recomendadas)

Se você tem tempo (15 minutos extra), adicione proteções contra loops futuros:

### Adicionar Timeout ao Refresh

Em `AuthProvider.tsx`, dentro de `refreshWithToken`:

```typescript
const refreshWithToken = useCallback(
  async (refreshToken: string | null, preferredTenantId?: string | null) => {
    if (!refreshToken) {
      clearSession();
      return null;
    }
    if (refreshPromise.current) {
      return refreshPromise.current;
    }
    const promise = (async () => {
      // ✨ ADICIONAR TIMEOUT
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      try {
        const response = await fetch('/api/tenant/accounts/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ refreshToken }),
          signal: controller.signal,  // ✨ ADICIONAR SIGNAL
        });
        
        clearTimeout(timeoutId);  // ✨ LIMPAR TIMEOUT
        
        if (!response.ok) {
          clearSession();
          return null;
        }
        // ... resto do código ...
      } catch (error) {
        clearTimeout(timeoutId);  // ✨ LIMPAR TIMEOUT
        if ((error as Error).name === 'AbortError') {
          console.warn('Refresh timeout after 10s');
        }
        clearSession();
        return null;
      }
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

## Testando a Correção

### Teste 1: Login Funciona
```bash
# Backend deve estar rodando
curl -X POST http://localhost:8000/api/tenant/accounts/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@demo.local","password":"ChangeMe123!"}'

# Deve retornar tokens
```

### Teste 2: Não Há Loops
```bash
# Abrir DevTools → Network tab
# Filtrar por "Fetch/XHR"
# Recarregar página
# Verificar que cada endpoint é chamado apenas 1-2 vezes
```

### Teste 3: Performance Normal
```bash
# Abrir DevTools → Performance tab
# Gravar por 10 segundos
# Verificar que não há atividade contínua excessiva
```

## Troubleshooting

### "Ainda vejo 404 nas rotas"
- Verifique se salvou o arquivo corretamente
- Verifique se fez rebuild do frontend
- Verifique se o backend está realmente rodando
- Limpe cache do browser

### "Login retorna 401 Unauthorized"
- Verifique se o banco de dados tem usuários seed
- Execute seed script:
  ```bash
  docker compose exec app python seed.py
  ```
- Credenciais default: `admin@demo.local` / `ChangeMe123!`

### "Backend não inicia"
- Verifique variáveis de ambiente:
  ```bash
  cp .env.example .env
  ```
- Verifique se PostgreSQL está rodando:
  ```bash
  docker compose up -d db
  ```

### "ConfigProvider ainda causa problemas"
- Verifique que removeu `const apiFetch = useAuthenticatedFetch();`
- Verifique que mudou para `fetch()` nativo
- Verifique que removeu `apiFetch` do array de dependências do useEffect

## Commit das Mudanças

```bash
git add frontend/src/auth/AuthProvider.tsx
git add frontend/src/config.tsx
git commit -m "fix: correct auth API routes and remove auth from config fetch

- Update AuthProvider to use /api/tenant/accounts/* routes
- Change ConfigProvider to use native fetch (API is public)
- Fixes browser freeze caused by infinite retry loops

Resolves: Browser freeze on login page (ISSUE-001, ISSUE-002)"
```

## Próximos Passos

Depois de aplicar esta correção mínima:

1. ✅ Verifique que tudo funciona
2. 📖 Leia [README.md](./README.md) para entender o problema completo
3. 🔧 Implemente [ISSUE-003](./ISSUE-003-auth-refresh-infinite-loop.md) para proteções adicionais
4. 📝 Atualize [ISSUE-004](./ISSUE-004-missing-tenant-config.md) para facilitar setup futuro

## Ajuda Adicional

- **Issues Detalhadas**: Veja arquivos `ISSUE-*.md` nesta pasta
- **Análise Completa**: Veja [README.md](./README.md)
- **Logs**: `docker compose logs -f app`
- **Health Check**: `curl http://localhost:8000/api/health`

---

**Tempo estimado desta correção**: 5-10 minutos  
**Complexidade**: Baixa (substituir strings)  
**Risco**: Mínimo (correção cirúrgica)
