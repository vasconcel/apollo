import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            console.error(
              `\n  [VITE] Proxy error: cannot reach backend at http://127.0.0.1:8000\n` +
              `         Make sure uvicorn is running (python run.py or python run.py --dev).\n`
            );
          });
        },
      },
    },
  },
})
