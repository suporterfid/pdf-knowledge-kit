import React, { useEffect, useState } from 'react';
import { useApiFetch } from '../apiKey';

interface Source {
  id: string;
  type: string;
  label?: string;
  location?: string;
  path?: string;
  url?: string;
  active: boolean;
  params?: any;
}

export default function Sources() {
  const apiFetch = useApiFetch();
  const [sources, setSources] = useState<Source[]>([]);
  const [type, setType] = useState('local_dir');
  const [path, setPath] = useState('');
  const [url, setUrl] = useState('');
  const [urls, setUrls] = useState('');
  const [label, setLabel] = useState('');
  const [location, setLocation] = useState('');
  const [active, setActive] = useState(true);
  const [params, setParams] = useState('');

  const [filterActive, setFilterActive] = useState('true');
  const [filterType, setFilterType] = useState('');

  interface SourceList { items: Source[] }

  const load = () => {
    const query = new URLSearchParams();
    if (filterActive !== 'all') {
      query.append('active', filterActive);
    }
    if (filterType) {
      query.append('type', filterType);
    }
    apiFetch(`/api/admin/ingest/sources?${query.toString()}`)
      .then((r) => r.json() as Promise<SourceList>)
      .then((d) => setSources(d.items))
      .catch(() => {});
  };

  useEffect(() => {
    load();
  }, [apiFetch, filterActive, filterType]);

  const create = (e: React.FormEvent) => {
    e.preventDefault();
    const body: any = {
      type,
      path: path || undefined,
      url: url || undefined,
      label: label || undefined,
      location: location || undefined,
      active,
    };

    if (params.trim()) {
      try {
        body.params = JSON.parse(params);
      } catch {
        // ignore parse errors
      }
    }

    if (type === 'url_list') {
      const list = urls
        .split(/\s+/)
        .map((u) => u.trim())
        .filter(Boolean);
      if (list.length) {
        body.url = list[0];
        body.params = { ...(body.params || {}), urls: list };
      }
    }

    apiFetch('/api/admin/ingest/sources', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(() => {
        setPath('');
        setUrl('');
        setUrls('');
        setLabel('');
        setLocation('');
        setActive(true);
        setParams('');
        load();
      })
      .catch(() => {});
  };

  const save = (s: Source) => {
    const body: any = {
      path: s.path,
      url: s.url,
      label: s.label,
      location: s.location,
      active: s.active,
    };
    if (s.params) {
      if (typeof s.params === 'string') {
        try {
          body.params = JSON.parse(s.params);
        } catch {
          // ignore
        }
      } else {
        body.params = s.params;
      }
    }
    apiFetch(`/api/admin/ingest/sources/${s.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
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
          <option value="url_list">URL List</option>
        </select>
        <label htmlFor="label">Label</label>
        <input id="label" value={label} onChange={(e) => setLabel(e.target.value)} />
        <label htmlFor="location">Location</label>
        <input id="location" value={location} onChange={(e) => setLocation(e.target.value)} />
        <label htmlFor="active">Active</label>
        <input
          id="active"
          type="checkbox"
          checked={active}
          onChange={(e) => setActive(e.target.checked)}
        />
        <label htmlFor="params">Params</label>
        <input id="params" value={params} onChange={(e) => setParams(e.target.value)} />
        {type === 'local_dir' && (
          <>
            <label htmlFor="path">Path</label>
            <input id="path" value={path} onChange={(e) => setPath(e.target.value)} />
          </>
        )}
        {type === 'url' && (
          <>
            <label htmlFor="url">URL</label>
            <input id="url" value={url} onChange={(e) => setUrl(e.target.value)} />
          </>
        )}
        {type === 'url_list' && (
          <>
            <label htmlFor="urls">URLs</label>
            <textarea id="urls" value={urls} onChange={(e) => setUrls(e.target.value)} />
          </>
        )}
        <button type="submit">Add</button>
      </form>

      <div>
        <label htmlFor="filterActive">Filter Active</label>
        <select
          id="filterActive"
          value={filterActive}
          onChange={(e) => setFilterActive(e.target.value)}
        >
          <option value="all">All</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
        <label htmlFor="filterType">Filter Type</label>
        <select
          id="filterType"
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        >
          <option value="">All</option>
          <option value="local_dir">Local</option>
          <option value="url">URL</option>
          <option value="url_list">URL List</option>
        </select>
      </div>

      <table aria-label="Sources">
        <thead>
          <tr>
            <th>ID</th>
            <th>Type</th>
            <th>Label</th>
            <th>Location</th>
            <th>Path</th>
            <th>URL</th>
            <th>Active</th>
            <th>Params</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr key={s.id}>
              <td>{s.id}</td>
              <td>{s.type}</td>
              <td>
                <input
                  aria-label="label"
                  value={s.label || ''}
                  onChange={(e) =>
                    setSources((prev) =>
                      prev.map((p) => (p.id === s.id ? { ...p, label: e.target.value } : p))
                    )
                  }
                />
              </td>
              <td>
                <input
                  aria-label="location"
                  value={s.location || ''}
                  onChange={(e) =>
                    setSources((prev) =>
                      prev.map((p) => (p.id === s.id ? { ...p, location: e.target.value } : p))
                    )
                  }
                />
              </td>
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
                {(s.type === 'url' || s.type === 'url_list') && (
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
                <input
                  type="checkbox"
                  aria-label="active"
                  checked={s.active}
                  onChange={(e) =>
                    setSources((prev) =>
                      prev.map((p) => (p.id === s.id ? { ...p, active: e.target.checked } : p))
                    )
                  }
                />
              </td>
              <td>
                <input
                  aria-label="params"
                  value={
                    typeof s.params === 'string'
                      ? s.params
                      : s.params
                      ? JSON.stringify(s.params)
                      : ''
                  }
                  onChange={(e) =>
                    setSources((prev) =>
                      prev.map((p) => (p.id === s.id ? { ...p, params: e.target.value } : p))
                    )
                  }
                />
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
