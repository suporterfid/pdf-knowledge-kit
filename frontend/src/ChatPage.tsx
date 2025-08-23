import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Header from './components/Header';
import ConversationPane from './components/ConversationPane';
import Composer from './components/Composer';
import Footer from './components/Footer';
import ErrorBanner from './components/ErrorBanner';
import Sidebar from './components/Sidebar';
import { ChatProvider, useChat } from './chat';

interface ConversationMeta {
  id: string;
  title: string;
  createdAt: string;
}

function ChatContent() {
  const {
    messages,
    sources,
    send,
    isStreaming,
    cancel,
    error,
    clearError,
    retry,
  } = useChat();

  return (
    <div className="flex flex-1 flex-col">
      <Header />
      {error && (
        <ErrorBanner message={error} onClose={clearError} onRetry={retry} />
      )}
      <ConversationPane messages={messages} sources={sources ?? undefined} />
      <Composer onSend={send} onCancel={cancel} isStreaming={isStreaming} />
      <Footer />
    </div>
  );
}

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [convId, setConvId] = useState<string | null>(null);

  useEffect(() => {
    const stored: ConversationMeta[] = JSON.parse(
      localStorage.getItem('conversations') || '[]'
    );
    if (!id || id === 'new') {
      const newId = crypto.randomUUID();
      const conv: ConversationMeta = {
        id: newId,
        title: 'Novo chat',
        createdAt: new Date().toISOString(),
      };
      localStorage.setItem('conversations', JSON.stringify([...stored, conv]));
      navigate(`/chat/${newId}`, { replace: true });
    } else {
      if (!stored.find((c) => c.id === id)) {
        const conv: ConversationMeta = {
          id,
          title: 'Novo chat',
          createdAt: new Date().toISOString(),
        };
        localStorage.setItem('conversations', JSON.stringify([...stored, conv]));
      }
      setConvId(id);
    }
  }, [id, navigate]);

  if (!convId) return null;

  return (
    <ChatProvider conversationId={convId}>
      <div className="flex flex-1">
        <Sidebar currentId={convId} />
        <ChatContent />
      </div>
    </ChatProvider>
  );
}
