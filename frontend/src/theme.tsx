import React, { createContext, useContext, useEffect, useState } from "react";

export type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const themeVariables: Record<Theme, Record<string, string>> = {
  light: {
    "--color-bg": "#f7f7f8",
    "--color-surface": "#ffffff",
    "--color-text": "#343541",
    "--color-accent": "#10a37f",
    "--color-border": "#e5e7eb",
  },
  dark: {
    "--color-bg": "#343541",
    "--color-surface": "#444654",
    "--color-text": "#ececf1",
    "--color-accent": "#10a37f",
    "--color-border": "#565869",
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
