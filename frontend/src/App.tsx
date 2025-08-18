import React from 'react';
import Header from './components/Header';
import ConversationPane from './components/ConversationPane';
import Composer from './components/Composer';
import SystemNotices from './components/SystemNotices';
import Footer from './components/Footer';
import { useChat } from './chat';

function App() {
  const { messages, notices, send } = useChat();

  return (
    <div className="app">
      <Header />
      <ConversationPane messages={messages} />
      <SystemNotices notices={notices} />
      <Composer onSend={send} />
      <Footer />
    </div>
  );
}

export default App;
