import React, { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react';
import { toast } from 'react-toastify';
import { useAuthenticatedFetch } from '../auth/AuthProvider';
import useAuth from '../hooks/useAuth';

interface Job {
  id: string;
  status: string;
  created_at: string;
}

interface JobList {
  items: Job[];
}

interface AgentSummary {
  id: number;
  name: string;
  slug: string;
}

interface AgentListResponse {
  items: AgentSummary[];
}

interface ChannelConfig {
  channel: string;
  is_enabled: boolean;
  webhook_secret?: string | null;
  credentials: Record<string, unknown>;
  settings: Record<string, unknown>;
}

interface ChannelConfigList {
  items: ChannelConfig[];
}

interface ConversationSummary {
  id: number;
  agent_id: number;
  channel: string;
  external_conversation_id: string;
  status: string;
  is_escalated: boolean;
  escalation_reason?: string | null;
  follow_up_at?: string | null;
  follow_up_note?: string | null;
  last_message_at?: string | null;
}

interface ConversationAnalytics {
  open_conversations: number;
  escalated_conversations: number;
  pending_follow_ups: number;
}

interface ChannelAnalytics {
  channel: string;
  conversations: number;
  escalations: number;
  last_activity?: string | null;
}

interface ConversationDashboardPayload {
  summary: ConversationAnalytics;
  channels: ChannelAnalytics[];
  recent_conversations: ConversationSummary[];
}

export default function Dashboard() {
  const apiFetch = useAuthenticatedFetch();
  const { roles, tenantId } = useAuth();
  const canOperate = roles.includes('operator') || roles.includes('admin');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [channelConfigs, setChannelConfigs] = useState<ChannelConfig[]>([]);
  const [channelDrafts, setChannelDrafts] = useState<Record<string, ChannelConfig>>({});
  const [dashboard, setDashboard] = useState<ConversationDashboardPayload | null>(null);
  const [loadingDashboard, setLoadingDashboard] = useState(false);
  const [newChannelName, setNewChannelName] = useState('whatsapp');

  useEffect(() => {
    const loadJobs = () => {
      const url = tenantId
        ? `/api/admin/ingest/jobs?tenantId=${tenantId}`
        : '/api/admin/ingest/jobs';
      apiFetch(url)
        .then((r) => r.json() as Promise<JobList>)
        .then((d) => setJobs(d.items))
        .catch(() => {});
    };
    loadJobs();
    const id = setInterval(loadJobs, 3000);
    return () => clearInterval(id);
  }, [apiFetch, tenantId]);

  useEffect(() => {
    const url = tenantId ? `/api/agents?tenantId=${tenantId}` : '/api/agents';
    apiFetch(url)
      .then((r) => (r.ok ? (r.json() as Promise<AgentListResponse>) : Promise.reject()))
      .then((data) => {
        setAgents(data.items);
        if (!selectedAgentId && data.items.length > 0) {
          setSelectedAgentId(data.items[0].id);
        }
      })
      .catch(() => setAgents([]));
  }, [apiFetch, tenantId]);

  useEffect(() => {
    if (!selectedAgentId) return;
    loadChannelConfigs(selectedAgentId);
    loadConversationDashboard(selectedAgentId);
  }, [selectedAgentId, tenantId]);

  const loadChannelConfigs = (agentId: number) => {
    const url = tenantId
      ? `/api/agents/${agentId}/channels?tenantId=${tenantId}`
      : `/api/agents/${agentId}/channels`;
    apiFetch(url)
      .then((r) => (r.ok ? (r.json() as Promise<ChannelConfigList>) : Promise.reject()))
      .then((data) => {
        setChannelConfigs(data.items);
        const draft: Record<string, ChannelConfig> = {};
        data.items.forEach((item) => {
          draft[item.channel] = { ...item };
        });
        setChannelDrafts(draft);
      })
      .catch(() => {
        setChannelConfigs([]);
        setChannelDrafts({});
      });
  };

  const loadConversationDashboard = (agentId: number) => {
    setLoadingDashboard(true);
    const url = tenantId
      ? `/api/agents/${agentId}/conversations/dashboard?tenantId=${tenantId}`
      : `/api/agents/${agentId}/conversations/dashboard`;
    apiFetch(url)
      .then((r) => (r.ok ? (r.json() as Promise<ConversationDashboardPayload>) : Promise.reject()))
      .then((payload) => setDashboard(payload))
      .catch(() => setDashboard(null))
      .finally(() => setLoadingDashboard(false));
  };

  const handleAgentChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const next = Number(event.target.value);
    setSelectedAgentId(Number.isNaN(next) ? null : next);
  };

  const updateChannelDraft = (channel: string, updates: Partial<ChannelConfig>) => {
    setChannelDrafts((prev) => ({
      ...prev,
      [channel]: { ...prev[channel], ...updates } as ChannelConfig,
    }));
  };

  const handleChannelToggle = (channel: string) => {
    const existing = channelDrafts[channel];
    if (!existing) return;
    updateChannelDraft(channel, { is_enabled: !existing.is_enabled });
  };

  const saveChannel = async (channel: string) => {
    if (!selectedAgentId) return;
    const draft = channelDrafts[channel];
    if (!draft) return;
    try {
      await apiFetch(`/api/agents/${selectedAgentId}/channels/${channel}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          is_enabled: draft.is_enabled,
          webhook_secret: draft.webhook_secret,
          credentials: draft.credentials,
          settings: draft.settings,
        }),
      });
      toast.success(`Saved ${channel} settings`);
      loadChannelConfigs(selectedAgentId);
    } catch {
      toast.error(`Unable to save ${channel} settings`);
    }
  };

  const resetChannel = (channel: string) => {
    const original = channelConfigs.find((c) => c.channel === channel);
    if (original) {
      setChannelDrafts((prev) => ({ ...prev, [channel]: { ...original } }));
    }
  };

  const handleCreateChannel = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedAgentId || !newChannelName.trim()) return;
    const channel = newChannelName.trim().toLowerCase();
    apiFetch(`/api/agents/${selectedAgentId}/channels/${channel}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_enabled: true, settings: {}, credentials: {} }),
    })
      .then(() => {
        toast.success(`Channel ${channel} created`);
        setNewChannelName('');
        loadChannelConfigs(selectedAgentId);
      })
      .catch(() => toast.error(`Could not create ${channel}`));
  };

  const handleFollowUp = async (conversation: ConversationSummary) => {
    if (!canOperate) return;
    const followUpAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
    try {
      await apiFetch(`/api/conversations/${conversation.id}/follow-up`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ follow_up_at: followUpAt, note: 'Scheduled from dashboard' }),
      });
      toast.info('Follow-up scheduled');
      if (selectedAgentId) loadConversationDashboard(selectedAgentId);
    } catch {
      toast.error('Unable to schedule follow-up');
    }
  };

  const handleEscalation = async (conversation: ConversationSummary) => {
    if (!canOperate) return;
    const resolve = conversation.is_escalated;
    const suffix = resolve ? '?resolve=true' : '';
    try {
      await apiFetch(`/api/conversations/${conversation.id}/escalate${suffix}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: resolve ? JSON.stringify({}) : JSON.stringify({ reason: 'manual_escalation' }),
      });
      toast.success(resolve ? 'Escalation resolved' : 'Conversation escalated');
      if (selectedAgentId) loadConversationDashboard(selectedAgentId);
    } catch {
      toast.error('Unable to update escalation');
    }
  };

  const conversationRows = useMemo(() => dashboard?.recent_conversations ?? [], [dashboard]);

  return (
    <div className="dashboard">
      <h2>Operations Dashboard</h2>

      <section aria-label="Agent selection">
        <label htmlFor="agent-select">Agent</label>
        <select id="agent-select" value={selectedAgentId ?? ''} onChange={handleAgentChange}>
          <option value="" disabled>
            Choose an agent
          </option>
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
            </option>
          ))}
        </select>
      </section>

      <section aria-label="Ingestion jobs">
        <h3>Recent Ingestion Jobs</h3>
        <table aria-label="Recent jobs">
          <thead>
            <tr>
              <th>Job</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {jobs.slice(0, 10).map((job) => (
              <tr key={job.id}>
                <td>{job.id}</td>
                <td>{job.status}</td>
                <td>{new Date(job.created_at).toLocaleString()}</td>
                <td>
                  <button
                    aria-label={`Cancel job ${job.id}`}
                    onClick={() =>
                      apiFetch(`/api/admin/ingest/jobs/${job.id}/cancel`, { method: 'POST' }).then(() => {
                        setJobs((prev) => prev.filter((j) => j.id !== job.id));
                      })
                    }
                    disabled={!canOperate}
                  >
                    Cancel
                  </button>
                  <button
                    aria-label={`Re-run job ${job.id}`}
                    onClick={() =>
                      apiFetch(`/api/admin/ingest/jobs/${job.id}/rerun`, { method: 'POST' }).then(() => {
                        toast.info('Job re-run requested');
                      })
                    }
                    disabled={!canOperate}
                  >
                    Re-run
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {selectedAgentId && (
        <>
          <section aria-label="Channel settings">
            <h3>Channel Settings</h3>
            <form onSubmit={handleCreateChannel} className="channel-create">
              <label htmlFor="new-channel">Add channel</label>
              <input
                id="new-channel"
                value={newChannelName}
                onChange={(e) => setNewChannelName(e.target.value)}
                placeholder="whatsapp"
              />
              <button type="submit" disabled={!canOperate}>
                Add
              </button>
            </form>
            {Object.keys(channelDrafts).length === 0 && <p>No channels configured yet.</p>}
            {Object.entries(channelDrafts).map(([channel, draft]) => (
              <div key={channel} className="channel-card">
                <header>
                  <h4>{channel}</h4>
                  <span>{draft.is_enabled ? 'Enabled' : 'Disabled'}</span>
                </header>
                <label>
                  <input
                    type="checkbox"
                    checked={draft.is_enabled}
                    onChange={() => handleChannelToggle(channel)}
                    disabled={!canOperate}
                  />
                  Enabled
                </label>
                <label>
                  Webhook secret
                  <input
                    type="text"
                    value={draft.webhook_secret ?? ''}
                    onChange={(e) => updateChannelDraft(channel, { webhook_secret: e.target.value })}
                    disabled={!canOperate}
                  />
                </label>
                <div className="channel-actions">
                  <button type="button" onClick={() => saveChannel(channel)} disabled={!canOperate}>
                    Save
                  </button>
                  <button type="button" onClick={() => resetChannel(channel)} disabled={!canOperate}>
                    Reset
                  </button>
                </div>
              </div>
            ))}
          </section>

          <section aria-label="Conversation insights">
            <div className="conversation-header">
              <h3>Conversation Insights</h3>
              <button type="button" onClick={() => loadConversationDashboard(selectedAgentId)} disabled={loadingDashboard}>
                Refresh
              </button>
            </div>
            {loadingDashboard && <p>Loading conversation analytics…</p>}
            {dashboard && (
              <>
                <div className="conversation-summary">
                  <div>
                    <strong>Open</strong>
                    <span>{dashboard.summary.open_conversations}</span>
                  </div>
                  <div>
                    <strong>Escalated</strong>
                    <span>{dashboard.summary.escalated_conversations}</span>
                  </div>
                  <div>
                    <strong>Follow-ups</strong>
                    <span>{dashboard.summary.pending_follow_ups}</span>
                  </div>
                </div>
                <table aria-label="Channel analytics">
                  <thead>
                    <tr>
                      <th>Channel</th>
                      <th>Conversations</th>
                      <th>Escalations</th>
                      <th>Last activity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.channels.map((chan) => (
                      <tr key={chan.channel}>
                        <td>{chan.channel}</td>
                        <td>{chan.conversations}</td>
                        <td>{chan.escalations}</td>
                        <td>{chan.last_activity ? new Date(chan.last_activity).toLocaleString() : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <h4>Recent conversations</h4>
                <table aria-label="Recent conversations">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Channel</th>
                      <th>Status</th>
                      <th>Escalation</th>
                      <th>Follow-up</th>
                      <th>Last activity</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {conversationRows.map((conversation) => (
                      <tr key={conversation.id}>
                        <td>{conversation.external_conversation_id}</td>
                        <td>{conversation.channel}</td>
                        <td>{conversation.status}</td>
                        <td>{conversation.is_escalated ? conversation.escalation_reason || 'Escalated' : '—'}</td>
                        <td>
                          {conversation.follow_up_at
                            ? new Date(conversation.follow_up_at).toLocaleString()
                            : '—'}
                        </td>
                        <td>
                          {conversation.last_message_at
                            ? new Date(conversation.last_message_at).toLocaleString()
                            : '—'}
                        </td>
                        <td>
                          <button
                            type="button"
                            onClick={() => handleFollowUp(conversation)}
                            disabled={!canOperate}
                          >
                            Schedule follow-up
                          </button>
                          <button
                            type="button"
                            onClick={() => handleEscalation(conversation)}
                            disabled={!canOperate}
                          >
                            {conversation.is_escalated ? 'Resolve escalation' : 'Escalate'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </section>
        </>
      )}
    </div>
  );
}
