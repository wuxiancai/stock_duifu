import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const apiProxyTarget = process.env.VITE_DEV_API_PROXY_TARGET || 'http://127.0.0.1:8000'
const allowedHosts = Array.from(
  new Set([
    'fojing.art',
    ...(process.env.VITE_DEV_ALLOWED_HOSTS || '')
      .split(',')
      .map((host) => host.trim())
      .filter(Boolean)
  ])
)

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    allowedHosts,
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
