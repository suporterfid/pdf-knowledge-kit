import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  status?: 'streaming' | 'done';
}

interface ChatContextValue {
  messages: Message[];
  notices: any;
  sessionId: string;
  isStreaming: boolean;
  send: (text: string, file?: File | null) => void;
  cancel: () => void;
  error: string | null;
  clearError: () => void;
  retry: () => void;
}

const ChatContext = createContext<ChatContextValue | undefined>(undefined);

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = useState<Message[]>(() => {
    const stored = localStorage.getItem('messages');
    return stored ? JSON.parse(stored) : [];
  });
  const [notices, setNotices] = useState<any>(null);
  const [sessionId, setSessionId] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const lastRequestRef = useRef<{ text: string; file?: File | null } | null>(null);

  useEffect(() => {
    let id = localStorage.getItem('sessionId');
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem('sessionId', id);
    }
    setSessionId(id);
  }, []);

  useEffect(() => {
    localStorage.setItem('messages', JSON.stringify(messages));
  }, [messages]);

  const send = async (text: string, file?: File | null) => {
    lastRequestRef.current = { text, file };
    setMessages((msgs) => [
      ...msgs,
      { role: 'user', content: text },
      { role: 'assistant', content: '', status: 'streaming' },
    ]);
    setIsStreaming(true);
    const attachments: { name: string; url?: string }[] = [];
    const formData = new FormData();
    formData.append('q', text);
    formData.append('k', '5');
    formData.append('sessionId', sessionId);
    const SMALL_FILE_LIMIT = 1024 * 1024; // 1MB
    try {
      if (file) {
        if (file.size <= SMALL_FILE_LIMIT) {
          formData.append('files', file);
          attachments.push({ name: file.name });
        } else {
          const up = new FormData();
          up.append('file', file);
          const resUp = await fetch('/api/upload', {
            method: 'POST',
            body: up,
          });
          const dataUp = await resUp.json();
          if (!resUp.ok) {
            throw new Error(dataUp.detail || 'Erro no upload');
          }
          attachments.push({ name: file.name, url: dataUp.url });
        }
      }
      formData.append('attachments', JSON.stringify(attachments));
      controllerRef.current = new AbortController();
      const res = await fetch('/api/chat', {
        method: 'POST',
        body: formData,
        signal: controllerRef.current.signal,
      });
      if (!res.ok) {
        if (res.status === 429) {
          throw new Error('Limite de taxa atingido. Tente novamente mais tarde.');
        }
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Erro na requisição');
      }
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error('No reader');
      let buffer = '';
      let doneReading = false;
      while (!doneReading) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const chunk = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const lines = chunk.split('\n');
          const eventLine = lines.find((l) => l.startsWith('event:')) || '';
          const dataLine = lines.find((l) => l.startsWith('data:')) || '';
          const event = eventLine.replace('event:', '').trim();
          const data = dataLine.replace('data:', '').trim();
          if (event === 'token') {
            setMessages((msgs) => {
              const updated = [...msgs];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = {
                ...last,
                content: last.content + data,
              };
              return updated;
            });
          } else if (event === 'sources') {
            setNotices(JSON.parse(data));
          } else if (event === 'done') {
            doneReading = true;
            setIsStreaming(false);
            setMessages((msgs) => {
              const updated = [...msgs];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, status: 'done' };
              return updated;
            });
            controllerRef.current = null;
          } else if (event === 'error') {
            doneReading = true;
            setError(data || 'Erro desconhecido');
            setIsStreaming(false);
            setMessages((msgs) => {
              const updated = [...msgs];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, status: 'done' };
              return updated;
            });
            controllerRef.current = null;
          }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setError(e.message || 'Falha de rede ou timeout');
        setMessages((msgs) => {
          const updated = [...msgs];
          const last = updated[updated.length - 1];
          if (last && last.status === 'streaming') {
            updated[updated.length - 1] = { ...last, status: 'done' };
          }
          return updated;
        });
      }
      setIsStreaming(false);
      controllerRef.current = null;
    }
  };

  const cancel = () => {
    if (controllerRef.current) {
      controllerRef.current.abort();
    }
    setIsStreaming(false);
    setMessages((msgs) => {
      const updated = [...msgs];
      const last = updated[updated.length - 1];
      if (last && last.status === 'streaming') {
        updated[updated.length - 1] = { ...last, status: 'done' };
      }
      return updated;
    });
  };

  const clearError = () => setError(null);

  const retry = () => {
    if (lastRequestRef.current) {
      const { text, file } = lastRequestRef.current;
      clearError();
      send(text, file || null);
    }
  };

  return (
    <ChatContext.Provider
      value={{
        messages,
        notices,
        sessionId,
        isStreaming,
        send,
        cancel,
        error,
        clearError,
        retry,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChat must be used within ChatProvider');
  return ctx;
}
