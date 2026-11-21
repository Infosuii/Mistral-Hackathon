import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
    // W1 can load the canonical fixture from the sibling contracts directory.
    fs: { allow: [fileURLToPath(new URL('..', import.meta.url))] },
  },
})
