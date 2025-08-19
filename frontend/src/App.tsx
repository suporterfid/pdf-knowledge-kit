import React from 'react';
import Header from './components/Header';
import ConversationPane from './components/ConversationPane';
import Composer from './components/Composer';
import SystemNotices from './components/SystemNotices';
import Footer from './components/Footer';
import ErrorBanner from './components/ErrorBanner';
import { useChat } from './chat';

function App() {
  const {
    messages,
    notices,
    send,
    isStreaming,
    cancel,
    error,
    clearError,
    retry,
  } = useChat();

  return (
    <div className="app">
      <Header />
      {error && (
        <ErrorBanner message={error} onClose={clearError} onRetry={retry} />
      )}
      <ConversationPane messages={messages} />
      <SystemNotices notices={notices} />
      <Composer onSend={send} onCancel={cancel} isStreaming={isStreaming} />
      <Footer />
    </div>
  );
}

export default App;
