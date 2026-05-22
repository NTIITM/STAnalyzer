import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: '/STAnalyzer/',
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor': ['vue', 'vue-router', 'vue-i18n', 'pinia', 'element-plus', '@element-plus/icons-vue'],
          'markdown': ['marked', 'dompurify'],
        }
      }
    }
  },
  test: {
    environment: 'jsdom',
    globals: true
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      // 前端统一以 /STA-MAS/api 为前缀发请求
      '/STAnalyzer/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:18000',
        // target: 'http://sdu-205:8000',
        changeOrigin: true,
        secure: false,
        ws: true,
        // 开发环境下去掉 /STAnalyzer 前缀，保留 /api，转发为 http://127.0.0.1:8000/api/xxx
        rewrite: (path) => path.replace(/^\/STAnalyzer/, ''),
        configure: (proxy, options) => {
          proxy.on('error', (err, req, res) => {
            console.log('代理错误:', err);
          });
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log('发送请求:', req.method, req.url);
          });
        }
        // 注意：不删除 /api 前缀，STA-MAS server 的端点都是 /api/xxx
      }
    }
  }
})
