import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../app/static',
    emptyOutDir: true,
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://api:8000',
        changeOrigin: true,
        secure: false,
        ws: true,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, res) => {
            console.log('[vite] Proxy error (API may still be starting up):', err.message);
            if (!res.writableEnded) {
              res.writeHead(503, {
                'Content-Type': 'application/json',
              });
              res.end(JSON.stringify({ 
                error: 'Service temporarily unavailable',
                message: 'Backend API is starting up. Please retry in a moment.'
              }));
            }
          });
          proxy.on('proxyReq', (_proxyReq, req, _res) => {
            console.log('[vite] Proxying:', req.method, req.url);
          });
        },
      },
      '/uploads': {
        target: process.env.VITE_API_URL || 'http://api:8000',
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, res) => {
            console.log('[vite] Proxy error (API may still be starting up):', err.message);
            if (!res.writableEnded) {
              res.writeHead(503, {
                'Content-Type': 'application/json',
              });
              res.end(JSON.stringify({ 
                error: 'Service temporarily unavailable',
                message: 'Backend API is starting up. Please retry in a moment.'
              }));
            }
          });
        },
      }
    }
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
  },
});
