import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // W Dockerze na Windowsie zmiany plików z bind mounta nie generują zdarzeń,
    // więc hot reload wymaga odpytywania (ustawiane w docker-compose.yml).
    watch: { usePolling: process.env.VITE_USE_POLLING === 'true' },
  },
})
