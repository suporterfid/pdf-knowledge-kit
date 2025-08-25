import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Header from './components/Header';
import ConversationPane from './components/ConversationPane';
import Composer from './components/Composer';
import Footer from './components/Footer';
import Disclaimer from './components/Disclaimer';
import ErrorBanner from './components/ErrorBanner';
import Sidebar from './components/Sidebar';
import { ChatProvider, useChat } from './chat';
import { generateUUID } from './utils/uuid';

interface ConversationMeta {
  id: string;
  title: string;
  createdAt: string;
}

function ChatContent({ onMenuClick }: { onMenuClick: () => void }) {
  const {
    messages,
    send,
    isStreaming,
    cancel,
    error,
    clearError,
    retry,
    sources,
  } = useChat();

  return (
    <div className="flex flex-1 flex-col">
      <Header onMenuClick={onMenuClick} />
      {error && (
        <ErrorBanner message={error} onClose={clearError} onRetry={retry} />
      )}
      <ConversationPane messages={messages} sources={sources ?? undefined} />
      <Composer onSend={send} onCancel={cancel} isStreaming={isStreaming} />
      <Disclaimer />
      <Footer />
    </div>
  );
}

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [convId, setConvId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const stored: ConversationMeta[] = JSON.parse(
      localStorage.getItem('conversations') || '[]'
    );
    if (!id || id === 'new') {
      const newId = generateUUID();
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
      <div className="flex flex-1 relative">
        <Sidebar
          currentId={convId}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/50 md:hidden z-10"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}
        <ChatContent onMenuClick={() => setSidebarOpen(true)} />
      </div>
    </ChatProvider>
  );
}
