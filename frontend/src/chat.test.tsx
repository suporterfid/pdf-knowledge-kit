import React from 'react';
import { renderHook, act, waitFor } from '@testing-library/react';
import { ChatProvider, useChat } from './chat';
import { ConfigProvider } from './config';
import { ApiKeyProvider } from './apiKey';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import 'whatwg-fetch';
import { vi, beforeAll, afterEach, afterAll, test, expect } from 'vitest';

const server = setupServer(
  http.get('/api/config', () =>
    HttpResponse.json({ UPLOAD_MAX_SIZE: 5 * 1024 * 1024 })
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

test('tokens append correctly on success', async () => {
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
    http.post('/api/chat', () =>
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
    http.post('/api/chat', () => {
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
