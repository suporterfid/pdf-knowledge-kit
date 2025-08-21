import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useApiFetch } from '../apiKey';
import useAuth from '../hooks/useAuth';

interface Job {
  id: string;
  status: string;
  created_at: string;
}

interface JobList {
  items: Job[];
}

export default function Dashboard() {
  const apiFetch = useApiFetch();
  const { roles } = useAuth();
  const canOperate = roles.includes('operator') || roles.includes('admin');
  const [jobs, setJobs] = useState<Job[]>([]);

  const load = () => {
    apiFetch('/api/admin/ingest/jobs')
      .then((r) => r.json() as Promise<JobList>)
      .then((d) => setJobs(d.items))
      .catch(() => {});
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [apiFetch]);

  const counts = jobs.reduce<Record<string, number>>((acc, j) => {
    acc[j.status] = (acc[j.status] || 0) + 1;
    return acc;
    }, {});

  return (
    <div>
      <h2>Dashboard</h2>
      <div role="status" aria-label="Job status counts">
        {Object.entries(counts).map(([status, count]) => (
          <div key={status}>{status}: {count}</div>
        ))}
      </div>
      <table aria-label="Recent jobs">
        <thead>
          <tr>
            <th>Job</th>
            <th>Status</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.slice(0, 10).map((job) => (
            <tr key={job.id}>
              <td><Link to={`/admin/jobs/${job.id}`}>{job.id}</Link></td>
              <td>{job.status}</td>
              <td>{new Date(job.created_at).toLocaleString()}</td>
              <td>
                <button
                  aria-label={`Cancel job ${job.id}`}
                  onClick={() =>
                    apiFetch(`/api/admin/ingest/jobs/${job.id}/cancel`, { method: 'POST' }).then(load)
                  }
                  disabled={!canOperate}
                >
                  Cancel
                </button>
                <button
                  aria-label={`Re-run job ${job.id}`}
                  onClick={() =>
                    apiFetch(`/api/admin/ingest/jobs/${job.id}/rerun`, { method: 'POST' }).then(load)
                  }
                  disabled={!canOperate}
                >
                  Re-run
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
