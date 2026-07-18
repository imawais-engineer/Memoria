import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy API calls to the FastAPI backend so the frontend can use relative URLs
// (avoids CORS during development).
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          markdown: ['react-markdown', 'remark-gfm', 'remark-math', 'rehype-katex'],
          charts: ['chart.js', 'react-chartjs-2'],
        },
      },
    },
  },
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
