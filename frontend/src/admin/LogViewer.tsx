import React, { useEffect, useState } from 'react';
import { useAuthenticatedFetch } from '../auth/AuthProvider';
import useAuth from '../hooks/useAuth';

interface LogSlice {
  content: string;
  next_offset: number;
  status?: string | null;
}

export default function LogViewer({ jobId, onStatus }: { jobId: string; onStatus?: (s: string) => void }) {
  const apiFetch = useAuthenticatedFetch();
  const { tenantId } = useAuth();
  const [log, setLog] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    let canceled = false;
    let offset = 0;
    async function poll() {
      while (!canceled) {
        const tenantSuffix = tenantId ? `&tenantId=${tenantId}` : '';
        const res = await apiFetch(
          `/api/admin/ingest/jobs/${jobId}/logs?offset=${offset}${tenantSuffix}`
        );
        const data: LogSlice = await res.json();
        if (data.content) {
          setLog((prev) => prev + data.content);
        }
        offset = data.next_offset;
        if (data.status) {
          setStatus(data.status);
          onStatus?.(data.status);
          break;
        }
        await new Promise((r) => setTimeout(r, 500));
      }
    }
    poll();
    return () => {
      canceled = true;
    };
  }, [jobId, tenantId, apiFetch, onStatus]);

  return (
    <div>
      <pre
        aria-label="Log output"
        tabIndex={0}
        style={{ background: '#fff', color: '#000', padding: '1em', maxHeight: '300px', overflow: 'auto' }}
      >
        {log}
      </pre>
      {status && <p>Status: {status}</p>}
    </div>
  );
}
