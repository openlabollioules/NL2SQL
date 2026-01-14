import path from "path"
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Split large dependencies into separate chunks
          'plotly': ['plotly.js-basic-dist-min'],
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
        }
      }
    },
    // Increase warning limit for heavy visualization libraries
    chunkSizeWarningLimit: 800,
  }
})
