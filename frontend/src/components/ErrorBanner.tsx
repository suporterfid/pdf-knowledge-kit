import React from 'react';

interface Props {
  message: string;
  onClose: () => void;
}

export default function ErrorBanner({ message, onClose }: Props) {
  return (
    <div className="error-banner">
      <span>{message}</span>
      <button onClick={onClose}>Fechar</button>
    </div>
  );
}
