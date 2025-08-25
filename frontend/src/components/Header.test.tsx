import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Header from './Header';
import { MemoryRouter } from 'react-router-dom';
import { ApiKeyProvider } from '../apiKey';
import { ConfigProvider } from '../config';
import { ThemeProvider } from '../theme';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import 'whatwg-fetch';
import { beforeAll, afterEach, afterAll, test, expect } from 'vitest';

const server = setupServer(
  http.get('/api/config', () => HttpResponse.json({}))
);

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());

function renderHeader() {
  return render(
    <MemoryRouter>
      <ApiKeyProvider>
        <ConfigProvider>
          <ThemeProvider>
            <Header />
          </ThemeProvider>
        </ConfigProvider>
      </ApiKeyProvider>
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
