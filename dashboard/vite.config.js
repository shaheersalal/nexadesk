import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  optimizeDeps: {
    // @huggingface/transformers uses dynamic imports internally — exclude from
    // Vite's pre-bundling so it loads correctly in the WebWorker at runtime.
    exclude: ['@huggingface/transformers'],
  },
  worker: {
    format: 'es',
  },
})
