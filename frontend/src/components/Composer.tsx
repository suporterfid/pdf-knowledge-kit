import React, { useRef, useState } from 'react';

interface Props {
  onSend: (text: string, file?: File | null) => void;
  onCancel: () => void;
  isStreaming: boolean;
}

export default function Composer({ onSend, onCancel, isStreaming }: Props) {
  const [input, setInput] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim()) return;
    onSend(input, file);
    setInput('');
    setFile(null);
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <form onSubmit={submit} className="composer">
      <label htmlFor="composer-text">Mensagem</label>
      <textarea
        id="composer-text"
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Pergunte algo"
        onKeyDown={handleKeyDown}
        maxLength={5000}
      />
      <label htmlFor="composer-file">Arquivo PDF</label>
      <input
        id="composer-file"
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
      {!isStreaming ? (
        <button type="submit">Enviar</button>
      ) : (
        <button
          type="button"
          onClick={() => {
            onCancel();
            textareaRef.current?.focus();
          }}
        >
          Cancelar
        </button>
      )}
    </form>
  );
}
