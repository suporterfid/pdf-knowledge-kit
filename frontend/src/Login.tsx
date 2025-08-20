import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApiKey } from './apiKey';

export default function Login() {
  const { setApiKey } = useApiKey();
  const [key, setKey] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setApiKey(key.trim());
    navigate('/');
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
    </div>
  );
}
