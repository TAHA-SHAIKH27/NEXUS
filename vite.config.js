import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ['react', 'react-dom'],
  },

  server: {
    port: 5173,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        timeout: 120000, // 120 seconds for LLM responses
        proxyTimeout: 120000, // 120 seconds for proxy response
      },
    },
    // FIX: Exclude backend runtime-written files from Vite's file watcher.
    // Without this, when the FastAPI backend writes to backend/data/*.json
    // (e.g. agri_conversation_context.json, session_memory.json) during AI
    // query processing, Vite detects the change and triggers a full-page
    // reload — interrupting the conversation and resetting the dashboard.
    watch: {
      ignored: [
        '**/backend/data/**',
        '**/backend/cache/**',
        '**/backend/**/*.json',
        '**/backend/**/*.log',
        '**/.git/**',
        '**/node_modules/**',
      ],
    },
  },

  publicDir: 'public',

  build: {
    rollupOptions: {
      input: {
        main: 'index.html',
      },
      output: {
        manualChunks: {
          vendor_react: ['react', 'react-dom'],
          vendor_charts: ['recharts'],
          vendor_motion: ['framer-motion'],
          vendor_icons: ['lucide-react'],
          vendor_three: ['three'],
        },
      },
    },
  },

  worker: {
    format: 'es',
    plugins: () => [],
  },
})
