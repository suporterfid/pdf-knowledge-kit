import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useConfig } from "../config";
import { useTheme } from "../theme";
import useAuth from "../hooks/useAuth";

interface Props {
  onMenuClick?: () => void;
}

export default function Header({ onMenuClick }: Props) {
  const { BRAND_NAME, LOGO_URL } = useConfig();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { theme, toggleTheme } = useTheme();
  const { user, tenantId, tenants, logout } = useAuth();
  const currentTenant = tenants.find((tenant) => tenant.id === tenantId) || null;

  const handleLogout = async () => {
    setMenuOpen(false);
    await logout();
    navigate("/auth/login");
  };

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        menuOpen &&
        menuRef.current &&
        !menuRef.current.contains(e.target as Node)
      ) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

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
          {LOGO_URL && <img src={LOGO_URL} alt={BRAND_NAME} className="logo" />}
          <h1>{BRAND_NAME}</h1>
        </div>
      </div>
      <div className="header-actions flex items-center space-x-2">
        <button onClick={() => navigate("/chat/new")} aria-label="Novo chat">
          Novo Chat
        </button>
        <button
          className="icon-button"
          onClick={toggleTheme}
          aria-label="Alternar tema"
        >
          {theme === "light" ? "🌙" : "☀️"}
        </button>
        <div className="user-menu relative" ref={menuRef}>
          <button
            className="icon-button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="Menu do usuário"
            aria-haspopup="true"
            aria-expanded={menuOpen}
          >
            {user?.email ? user.email.charAt(0).toUpperCase() : "☺"}
          </button>
          {menuOpen && (
            <div className="menu" role="menu">
              {currentTenant && (
                <div className="px-3 py-2 text-sm text-gray-400">
                  <p className="font-semibold text-gray-200">{user?.fullName || user?.email}</p>
                  <p>Tenant: {currentTenant.name || currentTenant.slug || currentTenant.id}</p>
                </div>
              )}
              <button type="button" onClick={handleLogout} role="menuitem">
                Sair
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
