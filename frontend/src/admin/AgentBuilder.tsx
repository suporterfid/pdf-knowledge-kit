import React, { useCallback, useEffect, useMemo, useState } from 'react';
import clsx from 'clsx';
import { useAuthenticatedFetch } from '../auth/AuthProvider';
import useAuth from '../hooks/useAuth';

interface AgentSummary {
  id: number;
  name: string;
  provider: string;
  model: string;
  description?: string;
  latest_version?: { version: number } | null;
}

interface AgentVersion {
  id: number;
  agent_id: number;
  version: number;
  label?: string | null;
  created_by?: string | null;
  created_at: string;
}

interface AgentTestRecord {
  id: number;
  input_prompt: string;
  status: string;
  ran_at: string;
  response: { text?: string };
}

interface AgentDetail extends AgentSummary {
  slug: string;
  persona: Record<string, any>;
  prompt_template?: string | null;
  response_parameters: Record<string, any>;
  deployment_metadata: Record<string, any>;
  tags: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
  versions?: AgentVersion[];
  tests?: AgentTestRecord[];
}

interface AgentListResponse {
  items: AgentSummary[];
  total: number;
}

interface AgentTestResponse {
  status: string;
  output: string;
  rendered_prompt: string;
  parameters: Record<string, any>;
  record: AgentTestRecord;
}

interface AgentFormState {
  name: string;
  description: string;
  provider: string;
  model: string;
  personaType: string;
  personaTone: string;
  personaStyle: string;
  promptTemplate: string;
  temperature: number;
}

const defaultForm: AgentFormState = {
  name: '',
  description: '',
  provider: 'openai',
  model: 'gpt-4o-mini',
  personaType: 'general',
  personaTone: 'friendly',
  personaStyle: 'concise',
  promptTemplate: '',
  temperature: 0.7,
};

function detailToForm(detail: AgentDetail): AgentFormState {
  return {
    name: detail.name,
    description: detail.description || '',
    provider: detail.provider,
    model: detail.model,
    personaType: (detail.persona && (detail.persona.type || detail.persona.persona)) || 'general',
    personaTone: detail.persona?.tone || '',
    personaStyle: detail.persona?.style || '',
    promptTemplate: detail.prompt_template || '',
    temperature: Number(detail.response_parameters?.temperature ?? 0.7),
  };
}

export default function AgentBuilder() {
  const apiFetch = useAuthenticatedFetch();
  const { roles, tenantId, tenants, setActiveTenant } = useAuth();
  const canOperate = roles.includes('operator') || roles.includes('admin');

  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [providers, setProviders] = useState<string[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentDetail | null>(null);
  const [form, setForm] = useState<AgentFormState>(defaultForm);
  const [loading, setLoading] = useState(false);
  const [testInput, setTestInput] = useState('Hello! How can you help me today?');
  const [testResult, setTestResult] = useState<AgentTestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tenantOptions = tenants.length > 0 ? tenants : tenantId ? [{ id: tenantId }] : [];

  const handleTenantChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setActiveTenant(event.target.value);
  };

  const environments = useMemo(() => {
    return (
      (selectedAgent?.deployment_metadata?.environments as Record<string, any>) || {}
    );
  }, [selectedAgent]);

  const loadAgents = useCallback(async () => {
    try {
      const url = tenantId ? `/api/agents?tenantId=${tenantId}` : '/api/agents';
      const res = await apiFetch(url);
      if (!res.ok) throw new Error('Failed to load agents');
      const data = (await res.json()) as AgentListResponse;
      setAgents(data.items || []);
    } catch {
      setAgents([]);
    }
  }, [apiFetch, tenantId]);

  const loadProviders = useCallback(async () => {
    try {
      const url = tenantId ? `/api/agents/providers?tenantId=${tenantId}` : '/api/agents/providers';
      const res = await apiFetch(url);
      if (!res.ok) throw new Error('Failed to load providers');
      const data = (await res.json()) as Record<string, string | null>;
      setProviders(Object.keys(data));
    } catch {
      setProviders(['openai', 'anthropic', 'google', 'meta']);
    }
  }, [apiFetch, tenantId]);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  const resetForm = useCallback(() => {
    setSelectedAgent(null);
    setForm(defaultForm);
    setTestResult(null);
  }, []);

  useEffect(() => {
    resetForm();
  }, [tenantId, resetForm]);

  const selectAgent = async (agentId: number) => {
    setError(null);
    try {
      const url = tenantId ? `/api/agents/${agentId}?tenantId=${tenantId}` : `/api/agents/${agentId}`;
      const res = await apiFetch(url);
      if (!res.ok) throw new Error('Failed to load agent');
      const data = (await res.json()) as AgentDetail;
      setSelectedAgent(data);
      setForm(detailToForm(data));
      setTestResult(null);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const buildPayload = () => {
    const persona: Record<string, string> = {
      type: form.personaType,
    };
    if (form.personaTone) persona.tone = form.personaTone;
    if (form.personaStyle) persona.style = form.personaStyle;
    const responseParameters = {
      temperature: Number.isFinite(form.temperature) ? form.temperature : 0.7,
    };
    return { persona, responseParameters };
  };

  const saveAgent = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    const { persona, responseParameters } = buildPayload();
    const basePayload = {
      name: form.name,
      description: form.description,
      provider: form.provider,
      model: form.model,
      persona,
      persona_type: form.personaType,
      prompt_template: form.promptTemplate || undefined,
      response_parameters: responseParameters,
      tags: selectedAgent?.tags || [],
    };
    try {
      const tenantSuffix = tenantId ? `?tenantId=${tenantId}` : '';
      const res = selectedAgent
        ? await apiFetch(`/api/agents/${selectedAgent.id}${tenantSuffix}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(basePayload),
          })
        : await apiFetch(`/api/agents${tenantSuffix}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              ...basePayload,
              initial_version_label: 'v1',
            }),
          });
      if (!res.ok) throw new Error('Unable to save agent');
      const detail = (await res.json()) as AgentDetail;
      setSelectedAgent(detail);
      setForm(detailToForm(detail));
      await loadAgents();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const runTest = async () => {
    if (!selectedAgent) return;
    setLoading(true);
    setError(null);
    try {
      const tenantSuffix = tenantId ? `?tenantId=${tenantId}` : '';
      const res = await apiFetch(`/api/agents/${selectedAgent.id}/test${tenantSuffix}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: testInput }),
      });
      if (!res.ok) throw new Error('Failed to run test');
      const data = (await res.json()) as AgentTestResponse;
      setTestResult(data);
      await selectAgent(selectedAgent.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const deployAgent = async () => {
    if (!selectedAgent) return;
    setLoading(true);
    setError(null);
    try {
      const tenantSuffix = tenantId ? `?tenantId=${tenantId}` : '';
      const res = await apiFetch(`/api/agents/${selectedAgent.id}/deploy${tenantSuffix}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          environment: 'sandbox',
          metadata: { triggered_from_ui: true },
        }),
      });
      if (!res.ok) throw new Error('Deployment failed');
      const data = (await res.json()) as AgentDetail;
      setSelectedAgent(data);
      await loadAgents();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleFieldChange = (key: keyof AgentFormState) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      const value =
        key === 'temperature' ? Number(event.target.value) : event.target.value;
      setForm((prev) => ({ ...prev, [key]: value }));
    };

  if (!canOperate) {
    return <p>You do not have permission to manage agents.</p>;
  }

  return (
    <div className="agent-builder space-y-6">
      <header className="admin-card flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="font-heading text-2xl font-semibold text-primary">Agentes por tenant</h2>
          <p className="text-sm text-text-secondary">
            Selecione uma organização para visualizar e editar os agentes disponíveis.
          </p>
        </div>
        {tenantOptions.length > 0 && (
          <label className="flex flex-col gap-2 text-sm text-text-secondary md:flex-row md:items-center">
            <span className="font-semibold">Organização:</span>
            <select
              value={tenantId ?? tenantOptions[0].id}
              onChange={handleTenantChange}
              className="w-full md:w-auto"
            >
              {tenantOptions.map((tenant) => (
                <option key={tenant.id} value={tenant.id}>
                  {tenant.name || tenant.slug || tenant.id}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>
      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)] xl:grid-cols-[360px_minmax(0,1fr)]">
        <section
          aria-label="Agent list"
          className="space-y-4 rounded-3xl border border-border bg-surface p-6 shadow-soft"
        >
          <header className="flex items-center justify-between">
            <h2 className="font-heading text-xl font-semibold text-primary">Agents</h2>
            <button
              type="button"
              className="button button--accent"
              onClick={resetForm}
              aria-label="Create new agent"
            >
              New Agent
            </button>
          </header>
          {agents.length === 0 ? (
            <p className="text-sm text-text-muted">No agents created yet.</p>
          ) : (
            <ul className="space-y-3">
              {agents.map((agent) => (
                <li key={agent.id}>
                  <button
                    type="button"
                    onClick={() => selectAgent(agent.id)}
                    aria-label={`Edit ${agent.name}`}
                    className={clsx(
                      'w-full rounded-2xl border p-4 text-left transition focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface',
                      selectedAgent?.id === agent.id
                        ? 'border-transparent bg-primary text-on-primary shadow-soft'
                        : 'border-border bg-surface-alt text-text-primary hover:border-primary hover:bg-surface'
                    )}
                  >
                    <strong
                      className={clsx(
                        'block text-base',
                        selectedAgent?.id === agent.id ? 'text-on-primary' : 'text-text-primary'
                      )}
                    >
                      {agent.name}
                    </strong>
                    <div
                      className={clsx(
                        'mt-1 text-sm',
                        selectedAgent?.id === agent.id ? 'text-on-primary' : 'text-text-secondary'
                      )}
                    >
                      {agent.provider} · {agent.model}
                      {agent.latest_version?.version && (
                        <span> · v{agent.latest_version.version}</span>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="space-y-6">
          <section
            aria-label="Agent builder form"
            className="space-y-6 rounded-3xl border border-border bg-surface p-6 shadow-soft"
          >
            <div className="flex flex-col gap-2">
              <h2 className="font-heading text-xl font-semibold text-primary">
                {selectedAgent ? `Edit ${selectedAgent.name}` : 'Create new agent'}
              </h2>
              {error && <p role="alert" className="text-sm text-danger">{error}</p>}
            </div>
            <form
              onSubmit={saveAgent}
              aria-label="Agent configuration form"
              className="grid gap-4"
            >
              <label htmlFor="agent-name" className="flex flex-col gap-1 text-sm text-text-secondary">
                <span className="font-semibold">Name</span>
                <input
                  id="agent-name"
                  value={form.name}
                  onChange={handleFieldChange('name')}
                  required
                  className="w-full"
                />
              </label>

              <label
                htmlFor="agent-description"
                className="flex flex-col gap-1 text-sm text-text-secondary"
              >
                <span className="font-semibold">Description</span>
                <textarea
                  id="agent-description"
                  value={form.description}
                  onChange={handleFieldChange('description')}
                  rows={2}
                  className="w-full"
                />
              </label>

              <label
                htmlFor="agent-provider"
                className="flex flex-col gap-1 text-sm text-text-secondary"
              >
                <span className="font-semibold">Provider</span>
                <select
                  id="agent-provider"
                  value={form.provider}
                  onChange={handleFieldChange('provider')}
                  className="w-full"
                >
                  {providers.map((provider) => (
                    <option key={provider} value={provider}>
                      {provider}
                    </option>
                  ))}
                </select>
              </label>

              <label htmlFor="agent-model" className="flex flex-col gap-1 text-sm text-text-secondary">
                <span className="font-semibold">Model</span>
                <input
                  id="agent-model"
                  value={form.model}
                  onChange={handleFieldChange('model')}
                  required
                  className="w-full"
                />
              </label>

              <fieldset className="grid gap-3 rounded-2xl border border-border bg-surface-alt p-4">
                <legend className="px-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
                  Personality
                </legend>
                <label htmlFor="persona-type" className="flex flex-col gap-1 text-sm text-text-secondary">
                  <span className="font-semibold">Persona Type</span>
                  <select
                    id="persona-type"
                    value={form.personaType}
                    onChange={handleFieldChange('personaType')}
                    className="w-full"
                  >
                    <option value="general">General</option>
                    <option value="support">Support</option>
                    <option value="sales">Sales</option>
                    <option value="hr">HR</option>
                  </select>
                </label>

                <label htmlFor="persona-tone" className="flex flex-col gap-1 text-sm text-text-secondary">
                  <span className="font-semibold">Tone</span>
                  <input
                    id="persona-tone"
                    value={form.personaTone}
                    onChange={handleFieldChange('personaTone')}
                    className="w-full"
                  />
                </label>

                <label htmlFor="persona-style" className="flex flex-col gap-1 text-sm text-text-secondary">
                  <span className="font-semibold">Style</span>
                  <input
                    id="persona-style"
                    value={form.personaStyle}
                    onChange={handleFieldChange('personaStyle')}
                    className="w-full"
                  />
                </label>
              </fieldset>

              <label htmlFor="prompt-template" className="flex flex-col gap-1 text-sm text-text-secondary">
                <span className="font-semibold">Prompt Template</span>
                <textarea
                  id="prompt-template"
                  value={form.promptTemplate}
                  onChange={handleFieldChange('promptTemplate')}
                  rows={4}
                  className="w-full"
                  placeholder="Provide custom system instructions or leave blank for defaults"
                />
              </label>

              <label htmlFor="temperature" className="flex flex-col gap-1 text-sm text-text-secondary">
                <span className="font-semibold">Temperature</span>
                <input
                  id="temperature"
                  type="number"
                  step="0.1"
                  min="0"
                  max="1.5"
                  value={form.temperature}
                  onChange={handleFieldChange('temperature')}
                  className="w-full"
                />
              </label>

              <button type="submit" className="button" disabled={loading}>
                {selectedAgent ? 'Update agent' : 'Create agent'}
              </button>
            </form>

            {selectedAgent && (
              <div className="space-y-3 rounded-2xl border border-border bg-surface-alt p-4">
                <h3 className="font-heading text-lg font-semibold text-primary">Deployment</h3>
                <p className="text-sm text-text-secondary">
                  Provider credentials:{' '}
                  <span
                    className={clsx(
                      'badge',
                      selectedAgent.deployment_metadata?.provider_credentials?.configured
                        ? 'status-success'
                        : 'status-danger'
                    )}
                  >
                    {selectedAgent.deployment_metadata?.provider_credentials?.configured
                      ? 'configured'
                      : 'missing'}
                  </span>
                </p>
                {Object.keys(environments).length > 0 ? (
                  <ul className="space-y-2 text-sm text-text-secondary">
                    {Object.entries(environments).map(([env, info]) => (
                      <li key={env} className="rounded-xl border border-border bg-surface p-3">
                        <strong className="font-semibold text-text-primary">{env}</strong>:{' '}
                        {info.endpoint_url || 'no endpoint'}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-text-muted">No deployments yet.</p>
                )}
              </div>
            )}
          </section>

          <section
            aria-label="Sandbox tester"
            className="space-y-4 rounded-3xl border border-border bg-surface p-6 shadow-soft"
          >
            <div className="flex flex-col gap-2">
              <h2 className="font-heading text-xl font-semibold text-primary">Sandbox tester</h2>
              <p className="text-sm text-text-secondary">
                Valide rapidamente ajustes do agente antes de publicar as alterações.
              </p>
            </div>
            <textarea
              aria-label="Test prompt"
              value={testInput}
              onChange={(e) => setTestInput(e.target.value)}
              rows={4}
              className="w-full"
            />
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                className="button button--accent"
                onClick={runTest}
                disabled={!selectedAgent || loading}
              >
                Run test
              </button>
              <button
                type="button"
                className="button"
                onClick={deployAgent}
                disabled={!selectedAgent || loading}
              >
                Deploy to sandbox
              </button>
            </div>
            {testResult && (
              <div role="status" className="space-y-3 rounded-2xl border border-border bg-surface-alt p-4">
                <h3 className="font-heading text-lg font-semibold text-primary">Latest test</h3>
                <p className="text-sm text-text-secondary">{testResult.output}</p>
                <pre className="overflow-x-auto rounded-xl bg-surface p-4 text-xs text-text-secondary">
                  {testResult.rendered_prompt}
                </pre>
              </div>
            )}
            {selectedAgent?.tests && selectedAgent.tests.length > 0 && (
              <div className="space-y-3 rounded-2xl border border-border bg-surface-alt p-4">
                <h3 className="font-heading text-lg font-semibold text-primary">Test history</h3>
                <ul className="space-y-2 text-sm text-text-secondary">
                  {selectedAgent.tests.map((record) => (
                    <li key={record.id} className="flex flex-col gap-1 rounded-xl border border-border bg-surface p-3">
                      <span className="font-medium text-text-primary">
                        {new Date(record.ran_at).toLocaleString()}
                      </span>
                      <span>{record.status}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
