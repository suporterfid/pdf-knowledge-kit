import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useConfig } from '../config';

export default function Header() {
  const { BRAND_NAME, LOGO_URL } = useConfig();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(
    localStorage.getItem('theme') || 'light'
  );
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  return (
    <header>
      <div className="brand">
        {LOGO_URL && <img src={LOGO_URL} alt={BRAND_NAME} className="logo" />}
        <h1>{BRAND_NAME}</h1>
      </div>
      <div className="header-actions">
        <button onClick={() => navigate('/chat/new')}>Novo Chat</button>
        <button className="icon-button" onClick={toggleTheme}>
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
        <div className="user-menu">
          <button
            className="icon-button"
            onClick={() => setMenuOpen((o) => !o)}
          >
            ☺
          </button>
          {menuOpen && (
            <div className="menu">
              <a href="#">Perfil</a>
              <a href="#">Sair</a>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
