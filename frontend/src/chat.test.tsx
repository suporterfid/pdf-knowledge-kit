import React from 'react';
import {
  renderHook,
  act,
  waitFor,
  render,
  screen,
  fireEvent,
  cleanup,
} from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { ChatProvider, useChat } from './chat';
import ChatPage from './ChatPage';
import { ConfigProvider } from './config';
import { AuthProvider } from './auth/AuthProvider';
import RequireAuth from './auth/RequireAuth';
import LoginPage from './auth/LoginPage';
import { ThemeProvider } from './theme';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import 'whatwg-fetch';
import { vi, beforeAll, afterEach, afterAll, test, expect } from 'vitest';

const server = setupServer(
  http.get('/api/config', () =>
    HttpResponse.json({
      UPLOAD_MAX_SIZE: 5 * 1024 * 1024,
      UPLOAD_MAX_FILES: 5,
    })
  )
);

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
  cleanup();
});
afterAll(() => server.close());

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

const baseAccessToken = createJwt({
  exp: Math.floor(Date.now() / 1000) + 60 * 60,
  tenant_id: 'tenant-1',
  roles: ['admin'],
  email: 'tester@example.com',
});
const baseRefreshToken = 'refresh-token';

function renderChat() {
  return renderHook(() => useChat(), {
    wrapper: ({ children }) => (
      <AuthProvider
        initialSession={{
          accessToken: baseAccessToken,
          refreshToken: baseRefreshToken,
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
          <ChatProvider>{children}</ChatProvider>
        </ConfigProvider>
      </AuthProvider>
    ),
  });
}

test('tokens append correctly on success via POST', async () => {
  server.use(
    http.post('/api/chat', () => {
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: token\ndata: Hel\n\n'));
          controller.enqueue(encoder.encode('event: token\ndata: lo\n\n'));
          controller.enqueue(encoder.encode('event: done\ndata:\n\n'));
          controller.close();
        },
      });
      return new HttpResponse(stream, {
        headers: { 'Content-Type': 'text/event-stream' },
      });
    })
  );

  const smallFile = new File(['hi'], 'a.txt');
  const { result } = renderChat();
  await act(async () => {
    await result.current.send('Hello', [smallFile]);
  });

  await waitFor(() => {
    expect(result.current.messages[1].content).toBe('Hello');
    expect(result.current.messages[1].status).toBe('done');
  });
});

test('tokens append correctly on success via GET', async () => {
  server.use(
    http.get('/api/chat', () => {
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: token\ndata: Hel\n\n'));
          controller.enqueue(encoder.encode('event: token\ndata: lo\n\n'));
          controller.enqueue(encoder.encode('event: done\ndata:\n\n'));
          controller.close();
        },
      });
      return new HttpResponse(stream, {
        headers: { 'Content-Type': 'text/event-stream' },
      });
    })
  );

  const { result } = renderChat();
  await act(async () => {
    await result.current.send('Hello');
  });

  await waitFor(() => {
    expect(result.current.messages[1].content).toBe('Hello');
    expect(result.current.messages[1].status).toBe('done');
  });
});

test('rate-limit message appears on 429', async () => {
  server.use(
    http.get('/api/chat', () =>
      HttpResponse.json({ detail: 'Too Many Requests' }, { status: 429 })
    )
  );
  const { result } = renderChat();
  await act(async () => {
    await result.current.send('Hi');
  });
  await waitFor(() => {
    expect(result.current.error).toBe(
      'Limite de taxa atingido. Tente novamente mais tarde.'
    );
  });
});

test('upload errors surface', async () => {
  server.use(
    http.post('/api/upload', () =>
      HttpResponse.json({ detail: 'Upload failed' }, { status: 400 })
    )
  );
  const bigFile = new File([new Uint8Array(1024 * 1024 + 1)], 'big.txt');
  const { result } = renderChat();
  await act(async () => {
    await result.current.send('Hi', [bigFile]);
  });
  await waitFor(() => {
    expect(result.current.error).toBe('Upload failed');
  });
});

test('SSE error event stops streaming and shows message', async () => {
  server.use(
    http.get('/api/chat', () => {
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: error\ndata: boom\n\n'));
          controller.close();
        },
      });
      return new HttpResponse(stream, {
        headers: { 'Content-Type': 'text/event-stream' },
      });
    })
  );
  const { result } = renderChat();
  await act(async () => {
    await result.current.send('Hi');
  });
  await waitFor(() => {
    expect(result.current.error).toBe('boom');
    expect(result.current.messages[1].status).toBe('done');
  });
});

test('oversized client messages trigger validation without network calls', async () => {
  const fetchSpy = vi.spyOn(global, 'fetch');
  const { result } = renderChat();
  await waitFor(() => fetchSpy.mock.calls.length > 0).catch(() => {});
  fetchSpy.mockClear();
  await act(async () => {
    await result.current.send('a'.repeat(5001));
  });
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(result.current.error).toBe('Mensagem muito longa');
  fetchSpy.mockRestore();
});

test('oversized file triggers local validation without network calls', async () => {
  const fetchSpy = vi.spyOn(global, 'fetch');
  const { result } = renderChat();
  await waitFor(() => fetchSpy.mock.calls.length > 0).catch(() => {});
  fetchSpy.mockClear();
  const hugeFile = new File(
    [new Uint8Array(5 * 1024 * 1024 + 1)],
    'huge.pdf',
    { type: 'application/pdf' }
  );
  await act(async () => {
    await result.current.send('Hi', [hugeFile]);
  });
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(result.current.error).toBe('Arquivo muito grande');
  fetchSpy.mockRestore();
});

test('regenerate resends last request', async () => {
  let calls = 0;
  server.use(
    http.get('/api/chat', () => {
      calls++;
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('event: token\ndata: Hi\n\n'));
          controller.enqueue(encoder.encode('event: done\ndata:\n\n'));
          controller.close();
        },
      });
      return new HttpResponse(stream, {
        headers: { 'Content-Type': 'text/event-stream' },
      });
    })
  );
  const { result } = renderChat();
  await act(async () => {
    await result.current.send('Hi');
  });
  await waitFor(() => result.current.messages[1].status === 'done');
  await act(async () => {
    await result.current.regenerate();
  });
  await waitFor(() => result.current.messages[3].status === 'done');
  expect(calls).toBe(2);
  expect(result.current.messages.length).toBe(4);

});

test('too many files trigger local validation', async () => {
  const fetchSpy = vi.spyOn(global, 'fetch');
  const { result } = renderChat();
  await waitFor(() => fetchSpy.mock.calls.length > 0).catch(() => {});
  fetchSpy.mockClear();
  const files = Array.from({ length: 6 }, (_, i) =>
    new File(['hi'], `${i}.pdf`, { type: 'application/pdf' })
  );
  await act(async () => {
    await result.current.send('Hi', files);
  });
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(result.current.error).toBe('Muitos arquivos');
  fetchSpy.mockRestore();

});

test('Novo Chat button creates a new conversation ID', async () => {
  // mock scrollTo for jsdom
  window.HTMLElement.prototype.scrollTo = vi.fn();
  const LocationDisplay = () => {
    const location = useLocation();
    return <span data-testid="location">{location.pathname}</span>;
  };

  render(
    <AuthProvider
      initialSession={{
        accessToken: baseAccessToken,
        refreshToken: baseRefreshToken,
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
          <MemoryRouter initialEntries={['/chat/first']}>
            <LocationDisplay />
            <Routes>
              <Route path="/chat/:id" element={<ChatPage />} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      </ConfigProvider>
    </AuthProvider>
  );

  await waitFor(() => {
    const convs = JSON.parse(localStorage.getItem('conversations') || '[]');
    return convs.length === 1;
  });
  expect(screen.getByTestId('location').textContent).toBe('/chat/first');

  fireEvent.click(screen.getByRole('button', { name: 'Novo chat' }));

  await waitFor(() => screen.getByTestId('location').textContent !== '/chat/first');

  await waitFor(() => {
    const convs = JSON.parse(localStorage.getItem('conversations') || '[]');
    return convs.length === 2;
  });

  const convs = JSON.parse(localStorage.getItem('conversations') || '[]');
  const newId = convs[1].id;
  expect(convs[0].id).toBe('first');
  expect(newId).not.toBe('first');
  expect(screen.getByTestId('location').textContent).toBe(`/chat/${newId}`);
});

test('RequireAuth redirects to login when no session is present', async () => {
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route
            path="/protected"
            element={
              <RequireAuth>
                <div>Área protegida</div>
              </RequireAuth>
            }
          />
          <Route path="/auth/login" element={<LoginPage />} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>
  );

  const heading = await screen.findByRole('heading', {
    name: /entrar/i,
  });
  expect(heading).toBeTruthy();
});

test('LoginPage autentica e redireciona para o chat', async () => {
  const loginAccessToken = createJwt({
    exp: Math.floor(Date.now() / 1000) + 3600,
    tenant_id: 'tenant-1',
    roles: ['admin'],
    email: 'tester@example.com',
  });
  server.use(
    http.post('/api/tenant/accounts/login', async () =>
      HttpResponse.json({
        accessToken: loginAccessToken,
        refreshToken: 'refresh-123',
        user: { email: 'tester@example.com', tenant_id: 'tenant-1', roles: ['admin'] },
        tenants: [{ id: 'tenant-1', name: 'Tenant 1' }],
      })
    )
  );

  render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/auth/login']}>
        <Routes>
          <Route path="/auth/login" element={<LoginPage />} />
          <Route path="/chat/new" element={<div>Chat carregado</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>
  );

  const [emailInput] = screen.getAllByLabelText(/e-mail/i);
  const [passwordInput] = screen.getAllByLabelText(/senha/i);
  fireEvent.change(emailInput, {
    target: { value: 'tester@example.com' },
  });
  fireEvent.change(passwordInput, {
    target: { value: 'super-secret' },
  });
  const [submitButton] = screen.getAllByRole('button', { name: /entrar/i });
  fireEvent.click(submitButton);

  const chatScreen = await screen.findByText('Chat carregado');
  expect(chatScreen).toBeTruthy();
});
