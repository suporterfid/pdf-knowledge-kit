import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AuthProvider } from '../../auth/AuthProvider';
import IngestLocal from '../IngestLocal';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import 'whatwg-fetch';
import { beforeAll, afterEach, afterAll, test, expect } from 'vitest';

const server = setupServer(
  http.get('/api/auth/roles', () =>
    HttpResponse.json({ roles: ['operator'] })
  )
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

test('starts local ingestion job and shows job id', async () => {
  server.use(
    http.post('/api/admin/ingest/local', async () =>
      HttpResponse.json({ job_id: '42' })
    )
  );

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
      <IngestLocal />
    </AuthProvider>
  );

  const pathInput = await screen.findByLabelText('Path');
  fireEvent.change(pathInput, { target: { value: '/data' } });

  fireEvent.submit(screen.getByRole('form', { name: 'Local ingestion form' }));

  await waitFor(() => {
    expect(screen.getByText('Started job 42')).not.toBeNull();
  });
});
