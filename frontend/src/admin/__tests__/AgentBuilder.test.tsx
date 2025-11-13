import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import 'whatwg-fetch';
import { beforeAll, afterAll, afterEach, test, expect } from 'vitest';

import { AuthProvider } from '../../auth/AuthProvider';
import AgentBuilder from '../AgentBuilder';

interface AgentSummary {
  id: number;
  name: string;
  provider: string;
  model: string;
  description?: string;
  latest_version?: { version: number } | null;
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
  versions?: any[];
  tests?: any[];
}

let agents: AgentSummary[] = [];
let agentDetail: AgentDetail | null = null;

const now = () => new Date().toISOString();

const server = setupServer(
  http.get('/api/auth/roles', () => HttpResponse.json({ roles: ['operator'] })),
  http.get('/api/agents/providers', () =>
    HttpResponse.json({ openai: 'key', anthropic: null })
  ),
  http.get('/api/agents', () => HttpResponse.json({ items: agents, total: agents.length })),
  http.post('/api/agents', async ({ request }) => {
    const payload = (await request.json()) as any;
    const id = 1;
    agentDetail = {
      id,
      slug: 'support-bot',
      name: payload.name,
      description: payload.description,
      provider: payload.provider,
      model: payload.model,
      persona: { ...(payload.persona || {}), type: payload.persona_type || 'general' },
      prompt_template:
        payload.prompt_template ||
        'You are a helpful support agent. Provide empathetic and actionable responses.',
      response_parameters: payload.response_parameters || { temperature: 0.7 },
      deployment_metadata: {
        provider_credentials: { configured: true },
        environments: {},
      },
      tags: [],
      is_active: true,
      created_at: now(),
      updated_at: now(),
      latest_version: { version: 1 },
      versions: [
        {
          id: 1,
          agent_id: id,
          version: 1,
          label: payload.initial_version_label || 'v1',
          created_by: 'tester',
          created_at: now(),
        },
      ],
      tests: [],
    };
    agents = [
      {
        id,
        name: payload.name,
        provider: payload.provider,
        model: payload.model,
        description: payload.description,
        latest_version: { version: 1 },
      },
    ];
    return HttpResponse.json(agentDetail, { status: 201 });
  }),
  http.get('/api/agents/:id', () => {
    if (!agentDetail) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(agentDetail);
  }),
  http.put('/api/agents/:id', async ({ request }) => {
    if (!agentDetail) return new HttpResponse(null, { status: 404 });
    const payload = (await request.json()) as any;
    agentDetail = {
      ...agentDetail,
      description: payload.description ?? agentDetail.description,
      model: payload.model ?? agentDetail.model,
      prompt_template: payload.prompt_template ?? agentDetail.prompt_template,
      response_parameters: payload.response_parameters || agentDetail.response_parameters,
      persona: { ...agentDetail.persona, ...(payload.persona || {}) },
      updated_at: now(),
    };
    agents = agents.map((item) =>
      item.id === agentDetail!.id
        ? {
            ...item,
            name: agentDetail!.name,
            description: agentDetail!.description,
            model: agentDetail!.model,
          }
        : item
    );
    return HttpResponse.json(agentDetail);
  }),
  http.post('/api/agents/:id/test', async ({ request }) => {
    if (!agentDetail) return new HttpResponse(null, { status: 404 });
    const payload = (await request.json()) as any;
    const record = {
      id: (agentDetail.tests?.length || 0) + 1,
      input_prompt: payload.input,
      status: 'success',
      ran_at: now(),
      response: { text: `Simulated: ${payload.input}` },
    };
    agentDetail = {
      ...agentDetail,
      tests: [record, ...(agentDetail.tests || [])],
    };
    return HttpResponse.json({
      status: 'success',
      output: record.response.text,
      rendered_prompt: `Rendered prompt for: ${payload.input}`,
      parameters: agentDetail.response_parameters,
      record,
    });
  }),
  http.post('/api/agents/:id/deploy', async () => {
    if (!agentDetail) return new HttpResponse(null, { status: 404 });
    const environments = {
      ...(agentDetail.deployment_metadata.environments || {}),
      sandbox: {
        endpoint_url: 'https://sandbox.example',
        deployed_at: now(),
        metadata: { triggered_from_ui: true },
      },
    };
    agentDetail = {
      ...agentDetail,
      deployment_metadata: {
        ...agentDetail.deployment_metadata,
        environments,
      },
      updated_at: now(),
    };
    return HttpResponse.json(agentDetail);
  })
);

function toBase64Url(value: string) {
  return Buffer.from(value)
    .toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

function createJwt(payload: Record<string, unknown>) {
  const header = toBase64Url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const body = toBase64Url(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

const testAccessToken = createJwt({
  exp: Math.floor(Date.now() / 1000) + 3600,
  tenant_id: 'tenant-1',
  roles: ['operator'],
  email: 'operator@example.com',
});
const testRefreshToken = 'refresh-token';

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  agents = [];
  agentDetail = null;
  localStorage.clear();
});
afterAll(() => server.close());

test('agent builder creates, tests and deploys agents', async () => {
  render(
    <AuthProvider
      initialSession={{
        accessToken: testAccessToken,
        refreshToken: testRefreshToken,
        user: {
          email: 'operator@example.com',
          tenantId: 'tenant-1',
          roles: ['operator'],
        },
        tenants: [{ id: 'tenant-1', name: 'Tenant 1' }],
        activeTenantId: 'tenant-1',
      }}
    >
      <AgentBuilder />
    </AuthProvider>
  );

  await screen.findByLabelText('Name');

  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Support Bot' } });
  fireEvent.change(screen.getByLabelText('Description'), {
    target: { value: 'Handles customer support questions.' },
  });
  fireEvent.change(screen.getByLabelText('Model'), { target: { value: 'gpt-4o' } });
  fireEvent.change(screen.getByLabelText('Persona Type'), { target: { value: 'support' } });
  fireEvent.change(screen.getByLabelText('Tone'), { target: { value: 'warm' } });
  fireEvent.change(screen.getByLabelText('Style'), { target: { value: 'detailed' } });
  fireEvent.change(screen.getByLabelText('Prompt Template'), {
    target: { value: 'Act as a support hero.' },
  });
  fireEvent.change(screen.getByLabelText('Temperature'), { target: { value: '0.4' } });

  fireEvent.click(screen.getByRole('button', { name: /create agent/i }));

  await screen.findByRole('button', { name: /edit support bot/i });

  fireEvent.change(screen.getByLabelText('Description'), {
    target: { value: 'Updated description for the agent.' },
  });
  fireEvent.click(screen.getByRole('button', { name: /update agent/i }));

  await waitFor(() => {
    const textarea = screen.getByLabelText('Description') as HTMLTextAreaElement;
    expect(textarea.value).toBe('Updated description for the agent.');
  });

  fireEvent.change(screen.getByLabelText('Test prompt'), {
    target: { value: 'Hello agent' },
  });
  fireEvent.click(screen.getByRole('button', { name: /run test/i }));

  await screen.findByText(/Simulated: Hello agent/);

  fireEvent.click(screen.getByRole('button', { name: /deploy to sandbox/i }));

  await waitFor(() => {
    const sandboxLabel = screen.getByText('sandbox', { selector: 'strong' });
    expect(sandboxLabel.parentElement?.textContent).toContain('https://sandbox.example');
  });
});
