import React, { useEffect, useRef, useState } from 'react';
import { useConfig } from '../config';

interface Props {
  onSend: (text: string, files: File[]) => void;
  onCancel: () => void;
  isStreaming: boolean;
}

function SendIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
      <path d="M2 21l21-9L2 3v7l15 2-15 2z" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

function AttachIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21.44 11.05l-9.19 9.19a5 5 0 01-7.07-7.07l9.19-9.19a3 3 0 014.24 4.24l-9.2 9.19a1 1 0 01-1.41-1.41l9.2-9.19" />
    </svg>
  );
}

export default function Composer({ onSend, onCancel, isStreaming }: Props) {
  const { UPLOAD_MAX_SIZE, UPLOAD_MAX_FILES } = useConfig();
  const [input, setInput] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${ta.scrollHeight}px`;
  }, [input]);

  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => {
      urls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [files]);

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

  const handleFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    const updated = [...files];
    for (const file of selected) {
      if (file.size > UPLOAD_MAX_SIZE) {
        alert('Arquivo muito grande');
        continue;
      }
      if (updated.length >= UPLOAD_MAX_FILES) {
        alert('Muitos arquivos');
        break;
      }
      updated.push(file);
    }
    setFiles(updated);
    e.target.value = '';
  };

  return (
    <form onSubmit={submit} className="composer">
      <div className="composer-input">
        <textarea
          id="composer-text"
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pergunte algo"
          onKeyDown={handleKeyDown}
          maxLength={5000}
          aria-label="Mensagem"
        />
        <div className="composer-toolbar">
          <label
            htmlFor="composer-file"
            className="icon-button"
            aria-label="Anexar arquivo"
          >
            <AttachIcon />
          </label>
          {isStreaming ? (
            <button
              type="button"
              className="icon-button"
              onClick={() => {
                onCancel();
                textareaRef.current?.focus();
              }}
              aria-label="Interromper resposta"
            >
              <StopIcon />
            </button>
          ) : (
            <button
              type="submit"
              className="icon-button"
              aria-label="Enviar mensagem"
            >
              <SendIcon />
            </button>
          )}
        </div>
      </div>
      <input
        id="composer-file"
        type="file"
        accept="application/pdf"
        multiple
        onChange={handleFiles}
        style={{ display: 'none' }}
      />
      {previews.length > 0 && (
        <div className="attachment-preview">
          {previews.map((url, idx) => (
            <div key={idx} className="pdf-container">
              <embed src={url} type="application/pdf" className="pdf-preview" />
              <button
                type="button"
                className="remove-btn"
                onClick={() =>
                  setFiles((prev) => prev.filter((_, i) => i !== idx))
                }
                aria-label="Remover arquivo"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </form>
  );
}

