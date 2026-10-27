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
      },
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
