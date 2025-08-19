import React from 'react';

interface Props {
  message: string;
  onClose: () => void;
  onRetry?: () => void;
}

export default function ErrorBanner({ message, onClose, onRetry }: Props) {
  return (
    <div className="error-banner">
      <span>{message}</span>
      {onRetry && <button onClick={onRetry}>Tentar novamente</button>}
      <button onClick={onClose}>Fechar</button>
    </div>
  );
}
