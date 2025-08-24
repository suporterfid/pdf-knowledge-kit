import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

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
    const id = crypto.randomUUID();
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
    const title = prompt('Novo título?');
    if (title) {
      const list = conversations.map((c) =>
        c.id === id ? { ...c, title } : c
      );
      persist(list);
    }
  };

  const remove = (id: string) => {
    if (!confirm('Excluir conversa?')) return;
    const list = conversations.filter((c) => c.id !== id);
    persist(list);
    localStorage.removeItem(`messages-${id}`);
    if (id === currentId) {
      if (list.length > 0) {
        navigate(`/chat/${list[list.length - 1].id}`);
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
      className={
        `bg-gray-800 p-4 flex flex-col w-64 z-20 fixed inset-y-0 left-0 transform transition-transform duration-200 ` +
        `md:static md:translate-x-0 md:flex ${isOpen ? 'translate-x-0' : '-translate-x-full'}`
      }
      aria-label="Histórico de conversas"
    >
      <div className="flex justify-end md:hidden">
        <button onClick={onClose} aria-label="Fechar menu">
          ✕
        </button>
      </div>
      <button
        className="mb-4 rounded bg-blue-600 px-3 py-2 text-sm"
        onClick={createNew}
        aria-label="Iniciar novo chat"
      >
        Novo Chat
      </button>
      <div className="flex-1 overflow-y-auto space-y-2">
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`rounded p-2 text-sm cursor-pointer ${
              c.id === currentId ? 'bg-gray-700' : 'hover:bg-gray-700'
            }`}
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
                  onClick={(e) => {
                    e.stopPropagation();
                    rename(c.id);
                  }}
                  aria-label="Renomear conversa"
                >
                  ✏️
                </button>
                <button
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
            <div className="text-xs text-gray-400">
              {new Date(c.createdAt).toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </nav>
  );
}
