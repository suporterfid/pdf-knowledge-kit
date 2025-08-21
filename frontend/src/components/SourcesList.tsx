import React from 'react';
import { Source } from '../chat';

interface Props {
  sources: Source[];
}

export default function SourcesList({ sources }: Props) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="sources-list">
      <h2 id="sources-heading">Sources</h2>
      <ol aria-labelledby="sources-heading">
        {sources.map((s, i) => {
          const isUrl = /^https?:\/\//i.test(s.path);
          const link = isUrl ? (
            <a href={s.path} target="_blank" rel="noopener noreferrer">
              {s.path}
            </a>
          ) : (
            <span>{s.path}</span>
          );
          return (
            <li key={i}>
              {link}
              <span className="source-meta">
                {' '}chunk {s.chunk_index}, distance {s.distance.toFixed(2)}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
