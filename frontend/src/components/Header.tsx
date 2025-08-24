import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useConfig } from '../config';

interface Props {
  onMenuClick?: () => void;
}

export default function Header({ onMenuClick }: Props) {
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
    <header className="flex items-center justify-between p-4">
      <div className="flex items-center">
        {onMenuClick && (
          <button
            className="mr-2 p-2 md:hidden"
            onClick={onMenuClick}
            aria-label="Abrir menu"
          >
            ☰
          </button>
        )}
        <div className="brand flex items-center">
          {LOGO_URL && (
            <img src={LOGO_URL} alt={BRAND_NAME} className="logo" />
          )}
          <h1>{BRAND_NAME}</h1>
        </div>
      </div>
      <div className="header-actions flex items-center space-x-2">
        <button
          onClick={() => navigate('/chat/new')}
          aria-label="Novo chat"
        >
          Novo Chat
        </button>
        <button
          className="icon-button"
          onClick={toggleTheme}
          aria-label="Alternar tema"
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
        <div className="user-menu relative">
          <button
            className="icon-button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="Menu do usuário"
            aria-haspopup="true"
            aria-expanded={menuOpen}
          >
            ☺
          </button>
          {menuOpen && (
            <div className="menu" role="menu">
              <a href="#" role="menuitem">
                Perfil
              </a>
              <a href="#" role="menuitem">
                Sair
              </a>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
