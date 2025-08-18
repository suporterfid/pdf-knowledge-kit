import React, { useState } from 'react';

interface Props {
  onSend: (text: string, file?: File | null) => void;
}

export default function Composer({ onSend }: Props) {
  const [input, setInput] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSend(input, file);
    setInput('');
    setFile(null);
  };

  return (
    <form onSubmit={submit} className="composer">
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Pergunte algo"
      />
      <input
        type="file"
        accept="application/pdf"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
      />
      {file && (
        <div className="attachment-info">
          <span>{file.name}</span>
          <button type="button" onClick={() => setFile(null)}>
            Remover
          </button>
        </div>
      )}
      <button type="submit">Enviar</button>
    </form>
  );
}
