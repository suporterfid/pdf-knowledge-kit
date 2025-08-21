import React, { useEffect, useRef, useState } from 'react';
import ChatMessage from './Message';
import { Message, Source } from '../chat';

interface Props {
  messages: Message[];
  sources?: Source[] | null;
}

export default function ConversationPane({ messages, sources }: Props) {
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
      if (el) el.scrollTop = el.scrollHeight;
    }
  }, [messages, autoScroll]);

  return (
    <div className="conversation" ref={containerRef} role="list">
      {messages.map((m, i) => (
        <ChatMessage
          key={i}
          message={m}
          sources={
            i === messages.length - 1 && m.role === 'assistant'
              ? sources || undefined
              : undefined
          }
        />
      ))}
    </div>
  );
}
