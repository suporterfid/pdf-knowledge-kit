import React, { createContext, useContext, useEffect, useState } from "react";

export type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const themeVariables: Record<Theme, Record<string, string>> = {
  light: {
    "--color-background": "#f4f5f0",
    "--color-surface": "#ffffff",
    "--color-surface-alt": "#eef0eb",
    "--color-primary": "#5f6360",
    "--color-secondary": "#8a908c",
    "--color-accent": "#2f8f62",
    "--color-text-primary": "#2b2d2a",
    "--color-text-secondary": "#4d534f",
    "--color-text-muted": "#6b706c",
    "--color-border": "#cfd3cf",
    "--color-success": "#2f8f62",
    "--color-warning": "#c87f2c",
    "--color-danger": "#c75d52",
    "--color-link": "#2f8f62",
    "--color-on-primary": "#ffffff",
    "--color-on-accent": "#ffffff",
    "--shadow-soft": "0 18px 32px rgba(47, 143, 98, 0.15)",
  },
  dark: {
    "--color-background": "#1f2120",
    "--color-surface": "#2b2e2c",
    "--color-surface-alt": "#353a36",
    "--color-primary": "#6c706d",
    "--color-secondary": "#949b96",
    "--color-accent": "#5cc397",
    "--color-text-primary": "#f2f4f1",
    "--color-text-secondary": "#c9cfca",
    "--color-text-muted": "#9aa29c",
    "--color-border": "#3a3f3b",
    "--color-success": "#5cc397",
    "--color-warning": "#e29b44",
    "--color-danger": "#d97c72",
    "--color-link": "#5cc397",
    "--color-on-primary": "#ffffff",
    "--color-on-accent": "#0f221a",
    "--shadow-soft": "0 18px 32px rgba(0, 0, 0, 0.45)",
  },
};

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  const vars = themeVariables[theme];
  Object.entries(vars).forEach(([key, value]) => {
    root.style.setProperty(key, value);
  });
  document.body.classList.remove("light", "dark");
  document.body.classList.add(theme);
  localStorage.setItem("theme", theme);
  localStorage.setItem("theme-vars", JSON.stringify(vars));
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem("theme") as Theme | null;
    return stored || "light";
  });

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "light" ? "dark" : "light"));

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
