import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useConfig } from './config';
import { useAuthenticatedFetch } from './auth/AuthProvider';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  status?: 'streaming' | 'done';
  sources?: Array<{
    path: string;
    chunk_index?: number;
    distance?: number;
  }>;
}

export interface Source {
  path: string;
  chunk_index: number;
  distance: number;
}

interface ChatContextValue {
  messages: Message[];
  sources: Source[] | null;
  sessionId: string;
  isStreaming: boolean;
  send: (text: string, files?: File[]) => void;
  cancel: () => void;
  error: string | null;
  clearError: () => void;
  retry: () => void;
  regenerate: () => Promise<void>;
}

const ChatContext = createContext<ChatContextValue | undefined>(undefined);

export function ChatProvider({
  children,
  conversationId = 'default',
}: {
  children: React.ReactNode;
  conversationId?: string;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sources, setSources] = useState<Source[] | null>(null);
  const sessionId = conversationId;
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingSession, setIsLoadingSession] = useState(true);
  const controllerRef = useRef<AbortController | null>(null);
  const lastRequestRef = useRef<{ text: string; files: File[] } | null>(null);
  const { UPLOAD_MAX_SIZE, UPLOAD_MAX_FILES } = useConfig();
  const apiFetch = useAuthenticatedFetch();

  // Load session from backend on mount or when sessionId changes
  useEffect(() => {
    const loadSession = async () => {
      try {
        setIsLoadingSession(true);
        const res = await apiFetch(`/api/chat-sessions/${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          // Convert backend format to frontend format
          const loadedMessages = data.messages.map((msg: any) => ({
            role: msg.role,
            content: msg.content,
            status: 'done' as const,
            sources: msg.sources,
          }));
          setMessages(loadedMessages);
        } else if (res.status === 404) {
          // Session doesn't exist yet, create it
          const createRes = await apiFetch('/api/chat-sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: `Chat ${new Date().toLocaleString()}` }),
          });
          if (createRes.ok) {
            setMessages([]);
          }
        }
      } catch (err) {
        console.error('Failed to load chat session:', err);
        // Fall back to empty messages if loading fails
        setMessages([]);
      } finally {
        setIsLoadingSession(false);
      }
    };

    loadSession();
  }, [sessionId, apiFetch]);

  // Save messages to backend whenever they change
  useEffect(() => {
    if (isLoadingSession || messages.length === 0) return;

    const saveSession = async () => {
      try {
        // We save messages individually as they're added via the add_message endpoint
        // This effect is mainly for syncing state
      } catch (err) {
        console.error('Failed to save chat session:', err);
      }
    };

    const timer = setTimeout(saveSession, 500);
    return () => clearTimeout(timer);
  }, [messages, isLoadingSession, apiFetch]);

  const send = async (text: string, files: File[] = []) => {
    if (text.length > 5000) {
      setError('Mensagem muito longa');
      return;
    }
    if (files.length > UPLOAD_MAX_FILES) {
      setError('Muitos arquivos');
      return;
    }
    for (const f of files) {
      if (f.size > UPLOAD_MAX_SIZE) {
        setError('Arquivo muito grande');
        return;
      }
    }
    lastRequestRef.current = { text, files };
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
      for (const file of files) {
        if (file.size <= SMALL_FILE_LIMIT) {
          formData.append('files', file);
          attachments.push({ name: file.name });
        } else {
          const up = new FormData();
          up.append('file', file);
          const resUp = await apiFetch('/api/upload', {
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
      controllerRef.current = new AbortController();
      let res: Response;
      if (files.length === 0 && attachments.length === 0) {
        const params = new URLSearchParams({
          q: text,
          k: '5',
          sessionId,
        });
        res = await apiFetch(`/api/chat?${params.toString()}`, {
          method: 'GET',
          signal: controllerRef.current.signal,
        });
      } else {
        formData.append('attachments', JSON.stringify(attachments));
        res = await apiFetch('/api/chat', {
          method: 'POST',
          body: formData,
          signal: controllerRef.current.signal,
        });
      }
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
      let assistantContent = '';
      let assistantSources: Source[] = [];

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
            assistantContent += data;
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
            assistantSources = JSON.parse(data);
            setSources(assistantSources);
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

            // Save messages to backend
            saveMessagesToBackend(text, assistantContent, assistantSources);
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

  const saveMessagesToBackend = async (
    userMessage: string,
    assistantMessage: string,
    assistantSources: Source[]
  ) => {
    try {
      // Save user message
      await apiFetch(`/api/chat-sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: 'user',
          content: userMessage,
        }),
      });

      // Save assistant message
      await apiFetch(`/api/chat-sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: 'assistant',
          content: assistantMessage,
          sources: assistantSources,
        }),
      });
    } catch (err) {
      console.error('Failed to save messages to backend:', err);
      // Don't interrupt user experience if saving fails
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
      const { text, files } = lastRequestRef.current;
      clearError();
      send(text, files);
    }
  };

  const regenerate = async () => {
    if (lastRequestRef.current) {
      const { text, files } = lastRequestRef.current;
      await send(text, files);
    }
  };

  return (
    <ChatContext.Provider
      value={{
        messages,
        sources,
        sessionId,
        isStreaming,
        send,
        cancel,
        error,
        clearError,
        retry,
        regenerate,
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
