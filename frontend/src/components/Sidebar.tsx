import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import clsx from 'clsx';
import { generateUUID } from '../utils/uuid';

interface ConversationMeta {
  id: string;
  title: string;
  createdAt: string;
}

function loadConversations(): ConversationMeta[] {
  const stored = localStorage.getItem('conversations');
  return stored ? JSON.parse(stored) : [];
}

interface Props {
  currentId: string;
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ currentId, isOpen, onClose }: Props) {
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    setConversations(loadConversations());
  }, []);

  const persist = (list: ConversationMeta[]) => {
    setConversations(list);
    localStorage.setItem('conversations', JSON.stringify(list));
  };

  const createNew = () => {
    const id = generateUUID();
    const conv: ConversationMeta = {
      id,
      title: 'Novo chat',
      createdAt: new Date().toISOString(),
    };
    const list = [...conversations, conv];
    persist(list);
    navigate(`/chat/${id}`);
  };

  const rename = (id: string) => {
    const current = conversations.find((c) => c.id === id);
    const title = prompt('Novo título?', current?.title);
    if (!title) return;

    const updated = conversations.map((c) =>
      c.id === id ? { ...c, title } : c
    );
    persist(updated);
  };

  const remove = (id: string) => {
    if (!window.confirm('Excluir conversa?')) return;
    const updated = conversations.filter((c) => c.id !== id);
    persist(updated);
    localStorage.removeItem(`messages-${id}`);
    if (id === currentId) {
      const next = updated.at(-1);
      if (next) {
        navigate(`/chat/${next.id}`);
      } else {
        createNew();
      }
    }
  };

  const navigateTo = (id: string) => {
    navigate(`/chat/${id}`);
    onClose();
  };

  return (
    <nav
      className={clsx(
        'fixed inset-y-0 left-0 z-30 flex w-72 transform flex-col bg-surface p-6 text-text-primary shadow-soft transition-transform duration-200 md:static md:z-auto md:border-r md:border-border md:translate-x-0',
        isOpen
          ? 'translate-x-0 pointer-events-auto'
          : '-translate-x-full pointer-events-none md:pointer-events-auto'
      )}
      aria-label="Histórico de conversas"
    >
      <div className="flex justify-end md:hidden">
        <button
          type="button"
          className="icon-button"
          onClick={onClose}
          aria-label="Fechar menu"
        >
          ✕
        </button>
      </div>
      <button
        type="button"
        className="button w-full justify-center"
        onClick={createNew}
        aria-label="Iniciar novo chat"
      >
        Novo Chat
      </button>
      <div className="mt-6 flex-1 space-y-3 overflow-y-auto">
        {conversations.map((c) => (
          <div
            key={c.id}
            className={clsx(
              'cursor-pointer rounded-2xl border p-3 text-sm shadow-soft transition focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-surface',
              c.id === currentId
                ? 'border-transparent bg-primary text-on-primary'
                : 'border-border bg-surface-alt text-text-primary hover:border-primary hover:bg-surface'
            )}
            role="button"
            tabIndex={0}
            aria-pressed={c.id === currentId}
            onClick={() => navigateTo(c.id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') navigateTo(c.id);
            }}
          >
            <div className="flex justify-between items-center">
              <span>{c.title}</span>
              <div className="space-x-1">
                <button
                  type="button"
                  className="icon-button"
                  onClick={(e) => {
                    e.stopPropagation();
                    rename(c.id);
                  }}
                  aria-label="Renomear conversa"
                >
                  ✏️
                </button>
                <button
                  type="button"
                  className="icon-button"
                  onClick={(e) => {
                    e.stopPropagation();
                    remove(c.id);
                  }}
                  aria-label="Excluir conversa"
                >
                  🗑️
                </button>
              </div>
            </div>
            <div
              className={clsx(
                'text-xs',
                c.id === currentId ? 'text-on-primary' : 'text-text-muted'
              )}
            >
              {new Date(c.createdAt).toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </nav>
  );
}
