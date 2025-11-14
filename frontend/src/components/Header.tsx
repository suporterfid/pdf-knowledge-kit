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
    <header className="px-6 py-4">
      <div className="flex items-center">
        {onMenuClick && (
          <button
            className="icon-button md:hidden"
            onClick={onMenuClick}
            aria-label="Abrir menu"
            >
            ☰
          </button>
        )}
        <div className="brand flex items-center">
          {LOGO_URL && <img src={LOGO_URL} alt={BRAND_NAME} className="logo" />}
          <h1 className="font-heading text-2xl font-bold text-primary">{BRAND_NAME}</h1>
        </div>
      </div>
      <div className="header-actions flex items-center">
        <button
          type="button"
          onClick={() => navigate("/chat/new")}
          aria-label="Novo chat"
        >
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
                <div className="px-3 py-2 text-sm text-text-muted">
                  <p className="font-semibold text-text-primary">
                    {user?.fullName || user?.email}
                  </p>
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
