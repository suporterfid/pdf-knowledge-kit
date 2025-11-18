# Issues e Análises Técnicas

Este diretório contém análises detalhadas de problemas identificados no projeto, incluindo diagnósticos, root cause analysis e planos de correção.

## Índice de Issues

### [DryRun-Dev-2025118](./DryRun-Dev-2025118/) - Browser Freeze no Ambiente de Desenvolvimento

**Status**: 🔄 Em Progresso - Issues críticas resolvidas (ISSUE-001, ISSUE-002)  
**Data**: 18/11/2025  
**Severidade**: Bloqueador de desenvolvimento

**Problema**: Browser congela ao acessar `http://localhost:5173` após carregar tela de login

**Root Cause**: Loops infinitos de requisições HTTP causados por:
1. Incompatibilidade de rotas de autenticação (frontend → `/api/auth/*`, backend → `/api/tenant/accounts/*`)
2. Race condition no ConfigProvider (chamada autenticada prematura)
3. Falta de proteções contra retry infinito

**Documentos**:
- [📋 Executive Summary](./DryRun-Dev-2025118/EXECUTIVE-SUMMARY.md) - Visão executiva
- [📖 Análise Completa](./DryRun-Dev-2025118/README.md) - Roadmap detalhado
- [⚡ Quick Fix Guide](./DryRun-Dev-2025118/QUICK-FIX-GUIDE.md) - Correção em 5 minutos
- [🔧 Technical Flow](./DryRun-Dev-2025118/TECHNICAL-FLOW.md) - Diagramas técnicos

**Issues Individuais**:
- [ISSUE-001](./DryRun-Dev-2025118/ISSUE-001-auth-routes-mismatch.md) - Incompatibilidade de rotas (✅ Resolvido)
- [ISSUE-002](./DryRun-Dev-2025118/ISSUE-002-config-provider-race-condition.md) - Race condition no config (✅ Resolvido)
- [ISSUE-003](./DryRun-Dev-2025118/ISSUE-003-auth-refresh-infinite-loop.md) - Loops infinitos (🟠 Alto)
- [ISSUE-004](./DryRun-Dev-2025118/ISSUE-004-missing-tenant-config.md) - Config de tenant ausente (🟡 Médio)

**Correção Estimada**: 1h 15min (mínima) a 4h 35min (completa)

---

## Como Usar Este Diretório

### Para Desenvolvedores

1. **Encontrou um bug?** Verifique se já existe análise aqui
2. **Precisa de contexto?** Leia o README.md da issue específica
3. **Quer correção rápida?** Busque o QUICK-FIX-GUIDE.md
4. **Precisa de detalhes?** Veja os arquivos ISSUE-*.md individuais

### Para Gerentes/PMs

1. **Quer entender impacto?** Leia EXECUTIVE-SUMMARY.md
2. **Precisa de estimativas?** Veja o README.md com roadmap
3. **Quer métricas?** Procure seções de "Impacto" e "Estimativas"

### Para Arquitetos/Tech Leads

1. **Quer análise profunda?** Leia TECHNICAL-FLOW.md
2. **Precisa de root cause?** Veja seções de análise nos ISSUE-*.md
3. **Quer soluções alternativas?** Cada ISSUE tem "Soluções Propostas"

## Estrutura de Uma Análise de Issue

Cada diretório de issue contém:

```
issue-name/
├── README.md                    # Visão geral e roadmap
├── EXECUTIVE-SUMMARY.md         # Sumário executivo (opcional)
├── TECHNICAL-FLOW.md            # Diagramas e fluxos técnicos (opcional)
├── QUICK-FIX-GUIDE.md          # Guia rápido de correção (opcional)
├── ISSUE-NNN-description.md    # Issues individuais detalhadas
└── assets/                      # Screenshots, logs, etc (opcional)
```

### Conteúdo de Cada ISSUE-*.md

1. **Severidade**: Crítico/Alto/Médio/Baixo
2. **Descrição**: O que é o problema
3. **Evidências**: Código, logs, screenshots
4. **Impacto**: Consequências do bug
5. **Root Cause**: Por que acontece
6. **Soluções Propostas**: Opções com prós/contras
7. **Recomendação**: Melhor caminho
8. **Testes**: Como validar correção
9. **Estimativa**: Tempo necessário
10. **Tags**: Para busca e categorização

## Convenções de Nomenclatura

### Diretórios de Issues
- Formato: `TipoDeIssue-Data` ou `DescriçãoCurta-Data`
- Exemplos:
  - `DryRun-Dev-20251118`
  - `ProductionIncident-20251215`
  - `PerformanceIssue-Q42025`

### Arquivos de Issue
- Formato: `ISSUE-NNN-short-description.md`
- Números sequenciais por diretório
- Descrição em kebab-case
- Exemplos:
  - `ISSUE-001-auth-routes-mismatch.md`
  - `ISSUE-002-memory-leak.md`
  - `ISSUE-003-race-condition.md`

## Severidades

| Emoji | Severidade | Descrição | SLA de Correção |
|-------|-----------|-----------|-----------------|
| 🔴 | Crítico | Bloqueia produção ou desenvolvimento | Imediato (horas) |
| 🟠 | Alto | Afeta funcionalidade importante | 1-3 dias |
| 🟡 | Médio | Afeta UX mas tem workaround | 1-2 semanas |
| 🔵 | Baixo | Melhoria ou nice-to-have | Backlog |

## Status de Issues

- ✅ **Resolvido** - Correção implementada e validada
- 🔄 **Em Progresso** - Correção sendo implementada
- 📋 **Documentado** - Análise completa, aguardando implementação
- 🔍 **Investigando** - Ainda em análise
- ⏸️ **Pausado** - Aguardando decisão ou pré-requisito
- ❌ **Fechado** - Não será corrigido (won't fix)

## Contribuindo com Análises

Para adicionar uma nova análise de issue:

1. Crie diretório com nome descritivo e data
2. Crie pelo menos README.md com análise
3. Siga template de estrutura acima
4. Adicione entrada neste índice
5. Commit com mensagem: `docs: add analysis for [problema]`

## Recursos Adicionais

- [ARCHITECTURE.md](../../ARCHITECTURE.md) - Arquitetura do sistema
- [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md) - Guia de troubleshooting (se existir)
- [DEPLOYMENT.md](../../DEPLOYMENT.md) - Guia de deployment
- [CHANGELOG.md](../../CHANGELOG.md) - Histórico de mudanças

---

**Última atualização**: 18/11/2025  
**Responsável**: Time de Desenvolvimento
