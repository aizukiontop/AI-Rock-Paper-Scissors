import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// Vite config for rps.club's frontend.
//
// This builds into ../static/app so Flask (see src/routes.py) can serve the
// compiled single-page app directly from its existing static folder, with
// no separate frontend server needed in production. All /api/* calls go to
// the same Flask origin (see src/api.ts), so no CORS/proxy config is needed
// either in dev (via the server.proxy block below) or in production (same
// origin by construction).
export default defineConfig({
  base: '/static/app/',
  build: {
    outDir: '../static/app',
    emptyOutDir: true,
  },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5000',
    },
  },
})
