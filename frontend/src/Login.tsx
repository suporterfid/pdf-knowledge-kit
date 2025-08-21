import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApiKey } from './apiKey';

export default function Login() {
  const { apiKey, setApiKey, clearApiKey } = useApiKey();
  const [key, setKey] = useState(apiKey);
  const navigate = useNavigate();

  useEffect(() => {
    setKey(apiKey);
  }, [apiKey]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setApiKey(key.trim());
    navigate('/');
  };

  const handleLogout = () => {
    clearApiKey();
    setKey('');
  };

  return (
    <div className="login">
      <h1>API Key</h1>
      <form onSubmit={handleSubmit} aria-label="API key form">
        <label htmlFor="apikey">Enter API Key</label>
        <input
          id="apikey"
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          required
        />
        <button type="submit">Save</button>
      </form>
      {apiKey && (
        <button type="button" onClick={handleLogout}>
          Logout
        </button>
      )}
    </div>
  );
}
