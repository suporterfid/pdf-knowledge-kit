import React from 'react';
import {
  renderHook,
  act,
  waitFor,
  render,
  screen,
  fireEvent,
} from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { ChatProvider, useChat } from './chat';
import ChatPage from './ChatPage';
import { ConfigProvider } from './config';
import { ApiKeyProvider } from './apiKey';
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
});
afterAll(() => server.close());

function renderChat() {
  return renderHook(() => useChat(), {
    wrapper: ({ children }) => (
      <ApiKeyProvider>
        <ConfigProvider>
          <ChatProvider>{children}</ChatProvider>
        </ConfigProvider>
      </ApiKeyProvider>
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
    <ApiKeyProvider>
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
    </ApiKeyProvider>
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
