import React from 'react';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import { Message } from '../chat';

const md = new MarkdownIt();

interface Props {
  messages: Message[];
}

export default function ConversationPane({ messages }: Props) {
  return (
    <div className="conversation">
      {messages.map((m, i) => (
        <div key={i} className={`msg ${m.role}`}>
          <div
            dangerouslySetInnerHTML={{
              __html: DOMPurify.sanitize(md.render(m.content)),
            }}
          />
        </div>
      ))}
    </div>
  );
}
