import React, { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { useAuth } from './AuthProvider';

interface LocationState {
  from?: { pathname: string };
}

export default function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
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
      await login({ email, password });
      const target = state.from?.pathname || '/chat/new';
      navigate(target, { replace: true });
      toast.success('Autenticação realizada com sucesso.');
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Não foi possível efetuar o login';
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
        aria-label="Formulário de login"
      >
        <div>
          <h1 className="font-heading text-4xl font-bold text-primary">Entrar</h1>
          <p className="mt-2 text-base text-text-secondary">
            Utilize suas credenciais para acessar o painel e o chat.
          </p>
        </div>
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-text-secondary">E-mail</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            className="w-full"
            autoComplete="username"
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
            autoComplete="current-password"
          />
        </label>
        <button
          type="submit"
          className="button w-full justify-center"
          disabled={submitting}
        >
          {submitting ? 'Entrando...' : 'Entrar'}
        </button>
        <p className="text-sm text-text-muted">
          Ainda não tem conta?{' '}
          <Link to="/auth/register" className="font-semibold text-link">
            Cadastre-se
          </Link>
        </p>
      </form>
    </div>
  );
}
