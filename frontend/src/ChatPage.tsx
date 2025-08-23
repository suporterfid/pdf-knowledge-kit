import React from 'react';
import Header from './components/Header';
import ConversationPane from './components/ConversationPane';
import Composer from './components/Composer';
import Footer from './components/Footer';
import ErrorBanner from './components/ErrorBanner';
import { useChat } from './chat';

function ChatPage() {
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

export default ChatPage;
