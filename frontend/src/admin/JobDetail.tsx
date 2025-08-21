import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useApiFetch } from '../apiKey';
import LogViewer from './LogViewer';
import useAuth from '../hooks/useAuth';

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const apiFetch = useApiFetch();
  const { roles } = useAuth();
  const canOperate = roles.includes('operator') || roles.includes('admin');
  const [status, setStatus] = useState('');

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
      <LogViewer jobId={id!} onStatus={setStatus} />
      <div>
        <button
          aria-label="Cancel job"
          onClick={cancelJob}
          disabled={!canOperate || (!!status && status !== 'queued' && status !== 'running')}
        >
          Cancel
        </button>
        <button
          aria-label="Re-run job"
          onClick={() =>
            apiFetch(`/api/admin/ingest/jobs/${id}/rerun`, { method: 'POST' }).then(() => {})
          }
          disabled={!canOperate}
        >
          Re-run
        </button>
      </div>
    </div>
  );
}
