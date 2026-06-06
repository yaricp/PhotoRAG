import { resolve } from 'path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
    root: '.',
    server: {
        host: '127.0.0.1',
        port: 5173,
    },
    resolve: {
        alias: {
            '@': resolve(__dirname, 'src'),
        },
    },
    plugins: [react()],
})
