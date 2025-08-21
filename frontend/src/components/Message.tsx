import React from 'react';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import { Message as MessageType, Source } from '../chat';
import SourcesList from './SourcesList';

const md = new MarkdownIt();

interface Props {
  message: MessageType;
  sources?: Source[];
}

export default function Message({ message, sources }: Props) {
  return (
    <div
      className={`msg ${message.role}`}
      role="listitem"
      aria-live={
        message.role === 'assistant' && message.status === 'streaming'
          ? 'polite'
          : undefined
      }
    >
      <div
        dangerouslySetInnerHTML={{
          __html: DOMPurify.sanitize(md.render(message.content)),
        }}
      />
      {message.status === 'streaming' && (
        <div className="typing-indicator">Digitando...</div>
      )}
      {message.role === 'assistant' && sources && (
        <SourcesList sources={sources} />
      )}
    </div>
  );
}
