import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy API calls to the FastAPI backend so the frontend can use relative URLs
// (avoids CORS during development).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/chat': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
    },
  },
})
