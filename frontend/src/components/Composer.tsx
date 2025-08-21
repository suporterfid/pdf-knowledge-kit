import React, { useRef, useState } from 'react';

interface Props {
  onSend: (text: string, files: File[]) => void;
  onCancel: () => void;
  isStreaming: boolean;
}

export default function Composer({ onSend, onCancel, isStreaming }: Props) {
  const [input, setInput] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim()) return;
    onSend(input, files);
    setInput('');
    setFiles([]);
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
        multiple
        onChange={(e) => {
          const newFiles = Array.from(e.target.files || []);
          setFiles((prev) => [...prev, ...newFiles]);
          e.target.value = '';
        }}
      />
      {files.length > 0 && (
        <div className="attachment-info">
          {files.map((f, idx) => (
            <div key={idx} className="attachment-item">
              <span>{f.name}</span>
              <button
                type="button"
                onClick={() =>
                  setFiles((prev) => prev.filter((_, i) => i !== idx))
                }
              >
                Remover
              </button>
            </div>
          ))}
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
