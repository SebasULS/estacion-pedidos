import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// En desarrollo, Vite sirve el frontend en http://localhost:5173 y hace proxy
// de /api al backend Flask en http://localhost:8000.
// En producción, configura VITE_API_URL con la URL pública del backend.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
