import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useApiFetch } from '../apiKey';

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const apiFetch = useApiFetch();
  const [log, setLog] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    let canceled = false;
    let offset = 0;
    async function poll() {
      while (!canceled) {
        const res = await apiFetch(
          `/api/admin/ingest/jobs/${id}/logs?offset=${offset}`,
        );
        const data = await res.json();
        if (data.text) {
          setLog((prev) => prev + data.text);
        }
        offset = data.next_offset;
        if (data.status) {
          setStatus(data.status);
          break;
        }
        await new Promise((r) => setTimeout(r, 500));
      }
    }
    poll();
    return () => {
      canceled = true;
    };
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
