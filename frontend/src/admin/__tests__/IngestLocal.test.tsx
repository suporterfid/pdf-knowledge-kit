import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ApiKeyProvider } from '../../apiKey';
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

  localStorage.setItem('apiKey', 'test');
  render(
    <ApiKeyProvider>
      <IngestLocal />
    </ApiKeyProvider>
  );

  const pathInput = await screen.findByLabelText('Path');
  fireEvent.change(pathInput, { target: { value: '/data' } });

  fireEvent.submit(screen.getByRole('form', { name: 'Local ingestion form' }));

  await waitFor(() => {
    expect(screen.getByText('Started job 42')).not.toBeNull();
  });
});
