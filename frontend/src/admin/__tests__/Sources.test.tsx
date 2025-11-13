import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { AuthProvider } from '../../auth/AuthProvider';
import Sources from '../Sources';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import 'whatwg-fetch';
import { beforeAll, afterEach, afterAll, test, expect } from 'vitest';

interface SourcePayload {
  type: string;
  label: string;
  path: string;
  active: boolean;
}

const sources: any[] = [
  { id: '1', type: 'local_dir', label: 'Existing', path: '/data', active: true },
];

const server = setupServer(
  http.get('/api/auth/roles', () =>
    HttpResponse.json({ roles: ['operator'] })
  ),
  http.get('/api/admin/ingest/sources', () =>
    HttpResponse.json({ items: sources })
  ),
  http.post('/api/admin/ingest/sources', async ({ request }) => {
    const payload = (await request.json()) as SourcePayload;
    const id = String(sources.length + 1);
    sources.push({ id, type: payload.type, label: payload.label, path: payload.path, active: payload.active });
    return HttpResponse.json({ id });
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
  localStorage.clear();
});
afterAll(() => server.close());

test('loads and adds sources', async () => {
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
      <Sources />
    </AuthProvider>
  );

  await screen.findByDisplayValue('/data');

  fireEvent.change(screen.getByLabelText('Path'), { target: { value: '/new' } });
  fireEvent.click(screen.getByText('Add'));

  await screen.findByDisplayValue('/new');
  expect(sources).toHaveLength(2);
});
