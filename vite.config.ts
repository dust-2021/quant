import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import AutoImport from 'unplugin-auto-import/vite';
import Components from 'unplugin-vue-components/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
import { createSvgIconsPlugin } from 'vite-plugin-svg-icons'
import path from 'path'

export default defineConfig({
    plugins: [vue(),
    AutoImport({
        resolvers: [ElementPlusResolver()],
    }),
    Components({
        resolvers: [ElementPlusResolver()],
    }),
    createSvgIconsPlugin({
        iconDirs: [path.resolve(process.cwd(), 'static/pic')],
        symbolId: 'icon-[name]',
    }),
    ],
    resolve: {
        alias: {
        },
    },
    base: './', // 确保静态资源路径正确
    server: {
        port: 3001, // 开发服务器端口
        strictPort: true,
        host: '0.0.0.0',
        hmr: true,
        proxy: {
            '/api': {
                target: `http://localhost:5000`,
                changeOrigin: true,
            },
            '/static': {
                target: `http://localhost:5000`,
                changeOrigin: true,
            },
        },
    },
    build: {
        outDir: 'static/dist', // 构建输出目录
        emptyOutDir: true, // 构建前清空输出目录
    },
});