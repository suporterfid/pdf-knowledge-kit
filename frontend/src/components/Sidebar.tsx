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

export default function Sidebar({ currentId }: { currentId: string }) {
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

  return (
    <div className="w-64 bg-gray-800 p-4 flex flex-col">
      <button
        className="mb-4 rounded bg-blue-600 px-3 py-2 text-sm"
        onClick={createNew}
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
          >
            <div className="flex justify-between items-center">
              <span onClick={() => navigate(`/chat/${c.id}`)}>{c.title}</span>
              <div className="space-x-1">
                <button onClick={() => rename(c.id)}>✏️</button>
                <button onClick={() => remove(c.id)}>🗑️</button>
              </div>
            </div>
            <div className="text-xs text-gray-400">
              {new Date(c.createdAt).toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
