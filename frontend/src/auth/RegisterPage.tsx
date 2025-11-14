import React, { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { useAuth } from './AuthProvider';

interface LocationState {
  from?: { pathname: string };
}

export default function RegisterPage() {
  const { register, isAuthenticated, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [organization, setOrganization] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as LocationState) || {};

  if (!isLoading && isAuthenticated) {
    const target = state.from?.pathname || '/chat/new';
    return <Navigate to={target} replace />;
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await register({ email, password, name, organization });
      const target = state.from?.pathname || '/chat/new';
      navigate(target, { replace: true });
      toast.success('Cadastro concluído com sucesso.');
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Não foi possível concluir o cadastro';
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 text-text-primary">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md space-y-6 rounded-3xl border border-border bg-surface p-8 shadow-soft"
        aria-label="Formulário de cadastro"
      >
        <div>
          <h1 className="font-heading text-4xl font-bold text-primary">Criar conta</h1>
          <p className="mt-2 text-base text-text-secondary">
            Cadastre-se para começar a utilizar a plataforma.
          </p>
        </div>
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-text-secondary">
            Nome completo
          </span>
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full"
            autoComplete="name"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-text-secondary">
            Organização
          </span>
          <input
            type="text"
            value={organization}
            onChange={(event) => setOrganization(event.target.value)}
            className="w-full"
            autoComplete="organization"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-text-secondary">E-mail</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            className="w-full"
            autoComplete="email"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-text-secondary">Senha</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            className="w-full"
            autoComplete="new-password"
          />
        </label>
        <button
          type="submit"
          className="button w-full justify-center"
          disabled={submitting}
        >
          {submitting ? 'Criando conta...' : 'Cadastrar'}
        </button>
        <p className="text-sm text-text-muted">
          Já possui cadastro?{' '}
          <Link to="/auth/login" className="font-semibold text-link">
            Acesse sua conta
          </Link>
        </p>
      </form>
    </div>
  );
}
