import { resolve } from 'path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
    main: {
        plugins: [externalizeDepsPlugin()]
    },

    preload: {
        plugins: [externalizeDepsPlugin()],
        build: {
            lib: {
                entry: resolve(__dirname, 'electron/preload/index.ts')
            }
        }
    },

    renderer: {
        root: '.', // 🔥 важно
        server: {
            host: '127.0.0.1',
            port: 5173
        },
        resolve: {
            alias: {
                '@': resolve(__dirname, 'src')
            }
        },
        plugins: [react()],
        build: {
            rollupOptions: {
                input: resolve(__dirname, 'index.html')
            }
        }
    }
})