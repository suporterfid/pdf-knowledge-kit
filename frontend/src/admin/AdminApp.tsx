import React from 'react';
import { Link, Routes, Route } from 'react-router-dom';
import useAuth from '../hooks/useAuth';
import Dashboard from './Dashboard';
import IngestLocal from './IngestLocal';
import IngestUrl from './IngestUrl';
import IngestUrls from './IngestUrls';
import JobDetail from './JobDetail';
import Sources from './Sources';
import AgentBuilder from './AgentBuilder';

export default function AdminApp() {
  const { tenants, tenantId, setActiveTenant, user } = useAuth();
  const activeTenant = tenants.find((tenant) => tenant.id === tenantId) || null;

  const handleTenantChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setActiveTenant(event.target.value);
  };

  return (
    <div className="admin flex h-full flex-col md:flex-row">
      <aside className="w-full bg-surface p-6 md:w-72 md:border-r md:border-border">
        <nav aria-label="Admin navigation">
          <ul className="space-y-2">
            <li>
              <Link to="/admin" className="hover:underline">
                Dashboard
              </Link>
            </li>
            <li>
              <Link to="/admin/ingest/local" className="hover:underline">
                Local Folder
              </Link>
            </li>
            <li>
              <Link to="/admin/ingest/url" className="hover:underline">
                Single URL
              </Link>
            </li>
            <li>
              <Link to="/admin/ingest/urls" className="hover:underline">
                Multiple URLs
              </Link>
            </li>
            <li>
              <Link to="/admin/sources" className="hover:underline">
                Sources
              </Link>
            </li>
            <li>
              <Link to="/admin/agents" className="hover:underline">
                Agents
              </Link>
            </li>
          </ul>
        </nav>
      </aside>
      <section className="flex-1 overflow-y-auto p-6">
        <div className="admin-card mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-widest text-text-muted">
              Organização ativa
            </p>
            <h2 className="font-heading text-2xl font-semibold text-primary">
              {activeTenant?.name || activeTenant?.slug || tenantId || 'Padrão'}
            </h2>
            {user?.email && (
              <p className="text-sm text-text-secondary">Usuário: {user.email}</p>
            )}
          </div>
          {tenants.length > 0 && (
            <label className="flex flex-col gap-2 text-sm text-text-secondary md:flex-row md:items-center">
              <span className="font-semibold">Alterar organização:</span>
              <select
                value={tenantId ?? tenants[0].id}
                onChange={handleTenantChange}
                className="w-full md:w-auto"
              >
                {tenants.map((tenant) => (
                  <option key={tenant.id} value={tenant.id}>
                    {tenant.name || tenant.slug || tenant.id}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        <Routes>
          <Route index element={<Dashboard />} />
          <Route path="ingest/local" element={<IngestLocal />} />
          <Route path="ingest/url" element={<IngestUrl />} />
          <Route path="ingest/urls" element={<IngestUrls />} />
          <Route path="jobs/:id" element={<JobDetail />} />
          <Route path="sources" element={<Sources />} />
          <Route path="agents" element={<AgentBuilder />} />
        </Routes>
      </section>
    </div>
  );
}
