import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { ChatProvider } from './chat';
import { ConfigProvider } from './config';
import { ApiKeyProvider } from './apiKey';
import './theme.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ApiKeyProvider>
      <ConfigProvider>
        <ChatProvider>
          <App />
        </ChatProvider>
      </ConfigProvider>
    </ApiKeyProvider>
  </React.StrictMode>,
);
