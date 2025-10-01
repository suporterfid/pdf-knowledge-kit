import React, { useEffect, useMemo, useState } from 'react';
import { useApiFetch } from '../apiKey';
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
  const apiFetch = useApiFetch();
  const { roles } = useAuth();
  const canOperate = roles.includes('operator') || roles.includes('admin');

  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [providers, setProviders] = useState<string[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentDetail | null>(null);
  const [form, setForm] = useState<AgentFormState>(defaultForm);
  const [loading, setLoading] = useState(false);
  const [testInput, setTestInput] = useState('Hello! How can you help me today?');
  const [testResult, setTestResult] = useState<AgentTestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const environments = useMemo(() => {
    return (
      (selectedAgent?.deployment_metadata?.environments as Record<string, any>) || {}
    );
  }, [selectedAgent]);

  useEffect(() => {
    loadProviders();
    loadAgents();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadAgents = async () => {
    try {
      const res = await apiFetch('/api/agents');
      if (!res.ok) throw new Error('Failed to load agents');
      const data = (await res.json()) as AgentListResponse;
      setAgents(data.items || []);
    } catch {
      setAgents([]);
    }
  };

  const loadProviders = async () => {
    try {
      const res = await apiFetch('/api/agents/providers');
      if (!res.ok) throw new Error('Failed to load providers');
      const data = (await res.json()) as Record<string, string | null>;
      setProviders(Object.keys(data));
    } catch {
      setProviders(['openai', 'anthropic', 'google', 'meta']);
    }
  };

  const resetForm = () => {
    setSelectedAgent(null);
    setForm(defaultForm);
    setTestResult(null);
  };

  const selectAgent = async (agentId: number) => {
    setError(null);
    try {
      const res = await apiFetch(`/api/agents/${agentId}`);
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
      const res = selectedAgent
        ? await apiFetch(`/api/agents/${selectedAgent.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(basePayload),
          })
        : await apiFetch('/api/agents', {
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
      const res = await apiFetch(`/api/agents/${selectedAgent.id}/test`, {
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
      const res = await apiFetch(`/api/agents/${selectedAgent.id}/deploy`, {
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
    <div className="agent-builder">
      <div className="agent-grid">
        <section aria-label="Agent list">
          <header className="agent-grid__header">
            <h2>Agents</h2>
            <button type="button" onClick={resetForm} aria-label="Create new agent">
              New Agent
            </button>
          </header>
          {agents.length === 0 ? (
            <p>No agents created yet.</p>
          ) : (
            <ul>
              {agents.map((agent) => (
                <li key={agent.id}>
                  <button
                    type="button"
                    onClick={() => selectAgent(agent.id)}
                    aria-label={`Edit ${agent.name}`}
                  >
                    <strong>{agent.name}</strong>
                    <div className="agent-meta">
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

        <section aria-label="Agent builder form">
          <h2>{selectedAgent ? `Edit ${selectedAgent.name}` : 'Create new agent'}</h2>
          {error && <p role="alert">{error}</p>}
          <form onSubmit={saveAgent} aria-label="Agent configuration form">
            <label htmlFor="agent-name">Name</label>
            <input
              id="agent-name"
              value={form.name}
              onChange={handleFieldChange('name')}
              required
            />

            <label htmlFor="agent-description">Description</label>
            <textarea
              id="agent-description"
              value={form.description}
              onChange={handleFieldChange('description')}
              rows={2}
            />

            <label htmlFor="agent-provider">Provider</label>
            <select
              id="agent-provider"
              value={form.provider}
              onChange={handleFieldChange('provider')}
            >
              {providers.map((provider) => (
                <option key={provider} value={provider}>
                  {provider}
                </option>
              ))}
            </select>

            <label htmlFor="agent-model">Model</label>
            <input
              id="agent-model"
              value={form.model}
              onChange={handleFieldChange('model')}
              required
            />

            <fieldset>
              <legend>Personality</legend>
              <label htmlFor="persona-type">Persona Type</label>
              <select
                id="persona-type"
                value={form.personaType}
                onChange={handleFieldChange('personaType')}
              >
                <option value="general">General</option>
                <option value="support">Support</option>
                <option value="sales">Sales</option>
                <option value="hr">HR</option>
              </select>

              <label htmlFor="persona-tone">Tone</label>
              <input
                id="persona-tone"
                value={form.personaTone}
                onChange={handleFieldChange('personaTone')}
              />

              <label htmlFor="persona-style">Style</label>
              <input
                id="persona-style"
                value={form.personaStyle}
                onChange={handleFieldChange('personaStyle')}
              />
            </fieldset>

            <label htmlFor="prompt-template">Prompt Template</label>
            <textarea
              id="prompt-template"
              value={form.promptTemplate}
              onChange={handleFieldChange('promptTemplate')}
              rows={4}
              placeholder="Provide custom system instructions or leave blank for defaults"
            />

            <label htmlFor="temperature">Temperature</label>
            <input
              id="temperature"
              type="number"
              step="0.1"
              min="0"
              max="1.5"
              value={form.temperature}
              onChange={handleFieldChange('temperature')}
            />

            <button type="submit" disabled={loading}>
              {selectedAgent ? 'Update agent' : 'Create agent'}
            </button>
          </form>

          {selectedAgent && (
            <div className="agent-status">
              <h3>Deployment</h3>
              <p>
                Provider credentials:{' '}
                {selectedAgent.deployment_metadata?.provider_credentials?.configured
                  ? 'configured'
                  : 'missing'}
              </p>
              {Object.keys(environments).length > 0 ? (
                <ul>
                  {Object.entries(environments).map(([env, info]) => (
                    <li key={env}>
                      <strong>{env}</strong>: {info.endpoint_url || 'no endpoint'}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No deployments yet.</p>
              )}
            </div>
          )}
        </section>

        <section aria-label="Sandbox tester">
          <h2>Sandbox tester</h2>
          <textarea
            aria-label="Test prompt"
            value={testInput}
            onChange={(e) => setTestInput(e.target.value)}
            rows={4}
          />
          <div className="sandbox-actions">
            <button type="button" onClick={runTest} disabled={!selectedAgent || loading}>
              Run test
            </button>
            <button type="button" onClick={deployAgent} disabled={!selectedAgent || loading}>
              Deploy to sandbox
            </button>
          </div>
          {testResult && (
            <div role="status" className="test-result">
              <h3>Latest test</h3>
              <p>{testResult.output}</p>
              <pre>{testResult.rendered_prompt}</pre>
            </div>
          )}
          {selectedAgent?.tests && selectedAgent.tests.length > 0 && (
            <div className="test-history">
              <h3>Test history</h3>
              <ul>
                {selectedAgent.tests.map((record) => (
                  <li key={record.id}>
                    {new Date(record.ran_at).toLocaleString()}: {record.status}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
