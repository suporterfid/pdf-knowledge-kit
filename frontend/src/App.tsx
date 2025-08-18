import React, { useState } from 'react';
import Header from './components/Header';
import ConversationPane from './components/ConversationPane';
import Composer from './components/Composer';
import SystemNotices from './components/SystemNotices';
import Footer from './components/Footer';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [notices, setNotices] = useState<any>(null);

  const send = (text: string) => {
    setMessages((msgs) => [...msgs, { role: 'user', content: text }, { role: 'assistant', content: '' }]);
    const es = new EventSource(`/api/chat?q=${encodeURIComponent(text)}`);
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
      es.close();
    });
    es.addEventListener('error', () => {
      es.close();
    });
  };

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
