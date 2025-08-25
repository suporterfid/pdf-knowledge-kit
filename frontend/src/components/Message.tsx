import React from 'react';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';
import { Message as MessageType, Source, useChat } from '../chat';
import SourcesList from './SourcesList';

const md: MarkdownIt = new MarkdownIt();

md.set({
  highlight: function (str, lang) {
    if (lang && Prism.languages[lang]) {
      try {
        return `<pre class="language-${lang}"><code>${Prism.highlight(str, Prism.languages[lang], lang)}</code></pre>`;
      } catch (__) {}
    }
    return `<pre class="language-${lang}"><code>${md.utils.escapeHtml(str)}</code></pre>`;
  },
});

interface Props {
  message: MessageType;
  sources?: Source[];
}

export default function Message({ message, sources }: Props) {
  const avatar = message.role === 'assistant' ? '🤖' : '🧑';
  const { regenerate } = useChat();

  const handleCopy = async () => {
    try {
      await navigator.clipboard?.writeText(message.content);
    } catch (e) {
      console.log('copy failed', e);
    }
  };

  const handleRegenerate = () => {
    regenerate();
  };

  const handleFeedback = async (positive: boolean) => {
    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message.content, positive }),
      });
    } catch {
      console.log('feedback', { message: message.content, positive });
    }
  };

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
      <div className="avatar">{avatar}</div>
      <div>
        <div className="bubble">
          <div className="toolbar">
            <button onClick={handleCopy} aria-label="Copiar">📋</button>
            {message.role === 'assistant' && (
              <>
                <button
                  onClick={handleRegenerate}
                  aria-label="Regenerar"
                >
                  🔄
                </button>
                <button
                  onClick={() => handleFeedback(true)}
                  aria-label="Feedback positivo"
                >
                  👍
                </button>
                <button
                  onClick={() => handleFeedback(false)}
                  aria-label="Feedback negativo"
                >
                  👎
                </button>
              </>
            )}
          </div>
          <div
            dangerouslySetInnerHTML={{
              __html: DOMPurify.sanitize(md.render(message.content)),
            }}
          />
          {message.status === 'streaming' && (
            <div className="typing-indicator" aria-label="Digitando...">
              <span />
              <span />
              <span />
            </div>
          )}
        </div>
        {sources && <SourcesList sources={sources} />}
      </div>
    </div>
  );
}
