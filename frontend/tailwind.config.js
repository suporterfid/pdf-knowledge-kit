/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--color-background)",
        surface: "var(--color-surface)",
        "surface-alt": "var(--color-surface-alt)",
        primary: "var(--color-primary)",
        secondary: "var(--color-secondary)",
        accent: "var(--color-accent)",
        border: "var(--color-border)",
        success: "var(--color-success)",
        warning: "var(--color-warning)",
        danger: "var(--color-danger)",
        link: "var(--color-link)",
        text: {
          primary: "var(--color-text-primary)",
          secondary: "var(--color-text-secondary)",
          muted: "var(--color-text-muted)",
        },
        "on-primary": "var(--color-on-primary)",
        "on-accent": "var(--color-on-accent)",
      },
      fontFamily: {
        sans: [
          "Arial",
          "Helvetica",
          "helvetica-w01-bold",
          "-apple-system",
          "BlinkMacSystemFont",
          'Segoe UI',
          "Roboto",
          'Helvetica Neue',
          "sans-serif",
        ],
        heading: [
          "Arial",
          "Helvetica",
          "helvetica-w01-bold",
          "sans-serif",
        ],
      },
      boxShadow: {
        soft: "var(--shadow-soft)",
      },
    },
  },
  plugins: [],
};

