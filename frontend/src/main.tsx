import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { ConfigProvider } from "./config";
import { ApiKeyProvider } from "./apiKey";
import { ThemeProvider } from "./theme";
import "./theme.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider>
      <ApiKeyProvider>
        <ConfigProvider>
          <App />
        </ConfigProvider>
      </ApiKeyProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
