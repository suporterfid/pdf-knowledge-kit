import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useApiFetch } from '../apiKey';

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const apiFetch = useApiFetch();
  const [log, setLog] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      const res = await apiFetch(`/api/admin/ingest/jobs/${id}/logs`, {
        signal: controller.signal,
      });
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      if (!reader) return;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const chunk = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const lines = chunk.split('\n');
          const event = lines.find((l) => l.startsWith('event:'))?.replace('event:', '').trim();
          const data = lines.find((l) => l.startsWith('data:'))?.replace('data:', '').trim();
          if (event === 'end') {
            setStatus(data || '');
          } else if (data) {
            setLog((prev) => prev + data);
          }
        }
      }
    }
    load();
    return () => controller.abort();
  }, [id, apiFetch]);

  const cancelJob = () => {
    if (window.confirm('Cancel job?')) {
      apiFetch(`/api/admin/ingest/jobs/${id}/cancel`, { method: 'POST' })
        .then(() => setStatus('canceled'))
        .catch(() => {});
    }
  };

  return (
    <div>
      <h2>Job {id}</h2>
      <pre
        aria-label="Log output"
        tabIndex={0}
        style={{ background: '#fff', color: '#000', padding: '1em', maxHeight: '300px', overflow: 'auto' }}
      >
        {log}
      </pre>
      <p>Status: {status}</p>
      <button onClick={cancelJob}>Cancel</button>
    </div>
  );
}
