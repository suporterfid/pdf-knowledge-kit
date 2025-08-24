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
import { Message as MessageType, Source } from '../chat';
import SourcesList from './SourcesList';

const md = new MarkdownIt({
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
      <div className="bubble">
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
    </div>
  );
}
