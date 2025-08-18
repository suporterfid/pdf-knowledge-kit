import React, { createContext, useContext, useEffect, useState } from 'react';

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
  send: (text: string) => void;
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

  const send = (text: string) => {
    setMessages((msgs) => [
      ...msgs,
      { role: 'user', content: text },
      { role: 'assistant', content: '', status: 'streaming' },
    ]);
    setIsStreaming(true);
    const es = new EventSource(`/api/chat?q=${encodeURIComponent(text)}&sessionId=${sessionId}`);
    es.addEventListener('token', (e) => {
      const token = (e as MessageEvent).data;
      setMessages((msgs) => {
        const updated = [...msgs];
        const last = updated[updated.length - 1];
        updated[updated.length - 1] = { ...last, content: last.content + token };
        return updated;
      });
    });
    es.addEventListener('sources', (e) => {
      setNotices(JSON.parse((e as MessageEvent).data));
    });
    es.addEventListener('done', () => {
      setIsStreaming(false);
      setMessages((msgs) => {
        const updated = [...msgs];
        const last = updated[updated.length - 1];
        updated[updated.length - 1] = { ...last, status: 'done' };
        return updated;
      });
      es.close();
    });
    es.addEventListener('error', () => {
      setIsStreaming(false);
      es.close();
    });
  };

  return (
    <ChatContext.Provider value={{ messages, notices, sessionId, isStreaming, send }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChat must be used within ChatProvider');
  return ctx;
}
