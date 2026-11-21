import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backendTarget =
  process.env.GAMBIT_BACKEND_URL || `http://127.0.0.1:${process.env.BACKEND_PORT || '8000'}`

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': backendTarget },
    // W1 can load the canonical fixture from the sibling contracts directory.
    fs: { allow: [fileURLToPath(new URL('..', import.meta.url))] },
  },
})
