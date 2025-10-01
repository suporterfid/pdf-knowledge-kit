import React from 'react';
import { Link, Routes, Route } from 'react-router-dom';
import Dashboard from './Dashboard';
import IngestLocal from './IngestLocal';
import IngestUrl from './IngestUrl';
import IngestUrls from './IngestUrls';
import JobDetail from './JobDetail';
import Sources from './Sources';
import AgentBuilder from './AgentBuilder';

export default function AdminApp() {
  return (
    <div className="admin">
      <nav aria-label="Admin navigation">
        <ul>
          <li><Link to="/admin">Dashboard</Link></li>
          <li><Link to="/admin/ingest/local">Local Folder</Link></li>
          <li><Link to="/admin/ingest/url">Single URL</Link></li>
          <li><Link to="/admin/ingest/urls">Multiple URLs</Link></li>
          <li><Link to="/admin/sources">Sources</Link></li>
          <li><Link to="/admin/agents">Agents</Link></li>
        </ul>
      </nav>
      <Routes>
        <Route index element={<Dashboard />} />
        <Route path="ingest/local" element={<IngestLocal />} />
        <Route path="ingest/url" element={<IngestUrl />} />
        <Route path="ingest/urls" element={<IngestUrls />} />
        <Route path="jobs/:id" element={<JobDetail />} />
        <Route path="sources" element={<Sources />} />
        <Route path="agents" element={<AgentBuilder />} />
      </Routes>
    </div>
  );
}
