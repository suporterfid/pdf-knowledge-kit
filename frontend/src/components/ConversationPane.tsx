import React, { useEffect, useRef, useState } from 'react';
import ChatMessage from './Message';
import { Message } from '../chat';

interface Props {
  messages: Message[];
}

export default function ConversationPane({ messages }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onScroll = () => {
      const atBottom =
        el.scrollTop + el.clientHeight >= el.scrollHeight - 10;
      setAutoScroll(atBottom);
    };
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (autoScroll) {
      const el = containerRef.current;
      if (el) {
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
      }
    }
  }, [messages, autoScroll]);

  return (
    <div className="conversation" ref={containerRef} role="list">
      {messages.map((m, i) => (
        <ChatMessage key={i} message={m} />
      ))}
    </div>
  );
}
