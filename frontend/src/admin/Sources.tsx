import React, { useEffect, useState } from 'react';
import { useApiFetch } from '../apiKey';

interface Source {
  id: string;
  type: string;
  path?: string;
  url?: string;
}

export default function Sources() {
  const apiFetch = useApiFetch();
  const [sources, setSources] = useState<Source[]>([]);
  const [type, setType] = useState('local_dir');
  const [path, setPath] = useState('');
  const [url, setUrl] = useState('');

  interface SourceList { items: Source[] }

  const load = () => {
    apiFetch('/api/admin/ingest/sources')
      .then((r) => r.json() as Promise<SourceList>)
      .then((d) => setSources(d.items))
      .catch(() => {});
  };

  useEffect(() => {
    load();
  }, [apiFetch]);

  const create = (e: React.FormEvent) => {
    e.preventDefault();
    apiFetch('/api/admin/ingest/sources', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, path: path || undefined, url: url || undefined }),
    })
      .then(() => {
        setPath('');
        setUrl('');
        load();
      })
      .catch(() => {});
  };

  const save = (s: Source) => {
    apiFetch(`/api/admin/ingest/sources/${s.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: s.path, url: s.url }),
    }).then(load);
  };

  const del = (id: string) => {
    if (window.confirm('Delete source?')) {
      apiFetch(`/api/admin/ingest/sources/${id}`, { method: 'DELETE' }).then(load);
    }
  };

  const reindex = (id: string) => {
    apiFetch(`/api/admin/ingest/sources/${id}/reindex`, { method: 'POST' }).then(() => {});
  };

  return (
    <div>
      <h2>Sources</h2>
      <form onSubmit={create} aria-label="Create source form">
        <label htmlFor="type">Type</label>
        <select id="type" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="local_dir">Local</option>
          <option value="url">URL</option>
        </select>
        <label htmlFor="path">Path</label>
        <input id="path" value={path} onChange={(e) => setPath(e.target.value)} />
        <label htmlFor="url">URL</label>
        <input id="url" value={url} onChange={(e) => setUrl(e.target.value)} />
        <button type="submit">Add</button>
      </form>
      <table aria-label="Sources">
        <thead>
          <tr>
            <th>ID</th>
            <th>Type</th>
            <th>Path</th>
            <th>URL</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr key={s.id}>
              <td>{s.id}</td>
              <td>{s.type}</td>
              <td>
                {s.type === 'local_dir' && (
                  <input
                    aria-label="path"
                    value={s.path || ''}
                    onChange={(e) =>
                      setSources((prev) =>
                        prev.map((p) => (p.id === s.id ? { ...p, path: e.target.value } : p))
                      )
                    }
                  />
                )}
              </td>
              <td>
                {s.type === 'url' && (
                  <input
                    aria-label="url"
                    value={s.url || ''}
                    onChange={(e) =>
                      setSources((prev) =>
                        prev.map((p) => (p.id === s.id ? { ...p, url: e.target.value } : p))
                      )
                    }
                  />
                )}
              </td>
              <td>
                <button aria-label={`Save source ${s.id}`} onClick={() => save(s)}>Save</button>
                <button aria-label={`Delete source ${s.id}`} onClick={() => del(s.id)}>Delete</button>
                <button aria-label={`Reindex source ${s.id}`} onClick={() => reindex(s.id)}>Reindex</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
