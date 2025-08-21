import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ApiKeyProvider } from '../../apiKey';
import Sources from '../Sources';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import 'whatwg-fetch';
import { beforeAll, afterEach, afterAll, test, expect } from 'vitest';

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
    const body = await request.json();
    const id = String(sources.length + 1);
    sources.push({ id, type: body.type, label: body.label, path: body.path, active: body.active });
    return HttpResponse.json({ id });
  })
);

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());

test('loads and adds sources', async () => {
  localStorage.setItem('apiKey', 'test');
  render(
    <ApiKeyProvider>
      <Sources />
    </ApiKeyProvider>
  );

  await screen.findByDisplayValue('/data');

  fireEvent.change(screen.getByLabelText('Path'), { target: { value: '/new' } });
  fireEvent.click(screen.getByText('Add'));

  await screen.findByDisplayValue('/new');
  expect(sources).toHaveLength(2);
});
