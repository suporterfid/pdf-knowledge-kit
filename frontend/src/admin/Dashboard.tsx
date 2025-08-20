import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useApiFetch } from '../apiKey';

interface Job {
  id: string;
  status: string;
  created_at: string;
}

export default function Dashboard() {
  const apiFetch = useApiFetch();
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    apiFetch('/api/admin/ingest/jobs')
      .then((r) => r.json())
      .then(setJobs)
      .catch(() => {});
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
          </tr>
        </thead>
        <tbody>
          {jobs.slice(0, 10).map((job) => (
            <tr key={job.id}>
              <td><Link to={`/admin/jobs/${job.id}`}>{job.id}</Link></td>
              <td>{job.status}</td>
              <td>{new Date(job.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
