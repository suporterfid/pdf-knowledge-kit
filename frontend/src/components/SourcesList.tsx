import React from 'react';
import { Source } from '../chat';

interface Props {
  sources: Source[];
}

export default function SourcesList({ sources }: Props) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="sources-list">
      <h4>Fontes</h4>
      <ul>
        {sources.map((s, i) => (
          <li key={i}>
            {s.path} (chunk {s.chunk_index})
          </li>
        ))}
      </ul>
    </div>
  );
}
