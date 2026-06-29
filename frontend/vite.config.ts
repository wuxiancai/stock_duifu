import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import type { ProxyOptions } from 'vite'

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

const apiProxy: ProxyOptions = {
  target: apiProxyTarget,
  changeOrigin: true,
  timeout: 120000,
  proxyTimeout: 120000,
  configure(proxy) {
    proxy.on('error', (error, _request, response) => {
      if (!response || !('writeHead' in response) || response.headersSent) {
        return
      }
      response.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
      response.end(
        JSON.stringify({
          error: 'api_proxy_error',
          target: apiProxyTarget,
          message: error.message
        })
      )
    })
  }
}

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    allowedHosts,
    proxy: {
      '/api': apiProxy
    }
  },
  test: {
    environment: 'jsdom'
  }
})
