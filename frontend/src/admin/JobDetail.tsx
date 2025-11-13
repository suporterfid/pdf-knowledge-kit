import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useAuthenticatedFetch } from '../auth/AuthProvider';
import LogViewer from './LogViewer';
import useAuth from '../hooks/useAuth';

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const apiFetch = useAuthenticatedFetch();
  const { roles, tenantId } = useAuth();
  const canOperate = roles.includes('operator') || roles.includes('admin');
  const [status, setStatus] = useState('');

  const cancelJob = () => {
    if (window.confirm('Cancel job?')) {
      const tenantSuffix = tenantId ? `?tenantId=${tenantId}` : '';
      apiFetch(`/api/admin/ingest/jobs/${id}/cancel${tenantSuffix}`, { method: 'POST' })
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
          onClick={() => {
            const tenantSuffix = tenantId ? `?tenantId=${tenantId}` : '';
            apiFetch(`/api/admin/ingest/jobs/${id}/rerun${tenantSuffix}`, { method: 'POST' }).then(
              () => {}
            );
          }}
          disabled={!canOperate}
        >
          Re-run
        </button>
      </div>
    </div>
  );
}
