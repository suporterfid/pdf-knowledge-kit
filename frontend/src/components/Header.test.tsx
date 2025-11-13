import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Header from './Header';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../auth/AuthProvider';
import { ConfigProvider } from '../config';
import { ThemeProvider } from '../theme';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import 'whatwg-fetch';
import { beforeAll, afterEach, afterAll, test, expect } from 'vitest';

const server = setupServer(
  http.get('/api/config', () => HttpResponse.json({}))
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
  roles: ['admin'],
  email: 'tester@example.com',
});
const testRefreshToken = 'refresh-token';

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());

function renderHeader() {
  return render(
    <MemoryRouter>
      <AuthProvider
        initialSession={{
          accessToken: testAccessToken,
          refreshToken: testRefreshToken,
          user: {
            email: 'tester@example.com',
            tenantId: 'tenant-1',
            roles: ['admin'],
          },
          tenants: [{ id: 'tenant-1', name: 'Tenant 1' }],
          activeTenantId: 'tenant-1',
        }}
      >
        <ConfigProvider>
          <ThemeProvider>
            <Header />
          </ThemeProvider>
        </ConfigProvider>
      </AuthProvider>
      <button data-testid="outside">outside</button>
    </MemoryRouter>
  );
}

test('closes user menu when clicking outside', async () => {
  renderHeader();
  const toggle = screen.getByRole('button', { name: 'Menu do usuário' });
  fireEvent.click(toggle);
  await screen.findByRole('menu');
  fireEvent.mouseDown(screen.getByTestId('outside'));
  await waitFor(() => {
    expect(screen.queryByRole('menu')).toBeNull();
  });
});
