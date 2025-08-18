import React, { useEffect, useRef, useState } from 'react';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import { Message } from '../chat';

const md = new MarkdownIt();

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
      if (el) el.scrollTop = el.scrollHeight;
    }
  }, [messages, autoScroll]);

  return (
    <div className="conversation" ref={containerRef}>
      {messages.map((m, i) => (
        <div key={i} className={`msg ${m.role}`}>
          <div
            dangerouslySetInnerHTML={{
              __html: DOMPurify.sanitize(md.render(m.content)),
            }}
          />
          {m.status === 'streaming' && (
            <div className="typing-indicator">Digitando...</div>
          )}
        </div>
      ))}
    </div>
  );
}
