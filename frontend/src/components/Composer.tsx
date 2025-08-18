import React, { useState } from 'react';

interface Props {
  onSend: (text: string) => void;
}

export default function Composer({ onSend }: Props) {
  const [input, setInput] = useState('');

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSend(input);
    setInput('');
  };

  return (
    <form onSubmit={submit} className="composer">
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Pergunte algo"
      />
      <button type="submit">Enviar</button>
    </form>
  );
}
