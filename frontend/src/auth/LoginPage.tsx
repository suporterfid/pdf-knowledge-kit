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
    <div className="flex h-full items-center justify-center bg-gray-950 text-gray-100">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md space-y-4 rounded-lg bg-gray-900 p-6 shadow-lg"
        aria-label="Formulário de login"
      >
        <div>
          <h1 className="text-2xl font-semibold">Entrar</h1>
          <p className="text-sm text-gray-400">
            Utilize suas credenciais para acessar o painel e o chat.
          </p>
        </div>
        <label className="block">
          <span className="mb-1 block text-sm font-medium">E-mail</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            className="w-full rounded border border-gray-700 bg-gray-800 p-2"
            autoComplete="username"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium">Senha</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            className="w-full rounded border border-gray-700 bg-gray-800 p-2"
            autoComplete="current-password"
          />
        </label>
        <button
          type="submit"
          className="w-full rounded bg-blue-600 p-2 font-semibold hover:bg-blue-500"
          disabled={submitting}
        >
          {submitting ? 'Entrando...' : 'Entrar'}
        </button>
        <p className="text-sm text-gray-400">
          Ainda não tem conta?{' '}
          <Link to="/auth/register" className="text-blue-400 hover:underline">
            Cadastre-se
          </Link>
        </p>
      </form>
    </div>
  );
}
