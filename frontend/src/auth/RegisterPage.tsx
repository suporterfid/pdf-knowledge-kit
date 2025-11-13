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
    <div className="flex h-full items-center justify-center bg-gray-950 text-gray-100">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md space-y-4 rounded-lg bg-gray-900 p-6 shadow-lg"
        aria-label="Formulário de cadastro"
      >
        <div>
          <h1 className="text-2xl font-semibold">Criar conta</h1>
          <p className="text-sm text-gray-400">
            Cadastre-se para começar a utilizar a plataforma.
          </p>
        </div>
        <label className="block">
          <span className="mb-1 block text-sm font-medium">Nome completo</span>
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full rounded border border-gray-700 bg-gray-800 p-2"
            autoComplete="name"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium">Organização</span>
          <input
            type="text"
            value={organization}
            onChange={(event) => setOrganization(event.target.value)}
            className="w-full rounded border border-gray-700 bg-gray-800 p-2"
            autoComplete="organization"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium">E-mail</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            className="w-full rounded border border-gray-700 bg-gray-800 p-2"
            autoComplete="email"
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
            autoComplete="new-password"
          />
        </label>
        <button
          type="submit"
          className="w-full rounded bg-blue-600 p-2 font-semibold hover:bg-blue-500"
          disabled={submitting}
        >
          {submitting ? 'Criando conta...' : 'Cadastrar'}
        </button>
        <p className="text-sm text-gray-400">
          Já possui cadastro?{' '}
          <Link to="/auth/login" className="text-blue-400 hover:underline">
            Acesse sua conta
          </Link>
        </p>
      </form>
    </div>
  );
}
