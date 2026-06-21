import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const apiProxyTarget =
  process.env.VITE_DEV_API_PROXY_TARGET || process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true
      }
    }
  },
  test: {
    environment: 'jsdom'
  }
})
