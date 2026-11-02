import { fileURLToPath } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vitest/config';

export default defineConfig({
    plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    define: { 'import.meta.env.KONOMITV_VERSION': JSON.stringify('test') },
    test: {
        server: { deps: { inline: ['vuetify'] } },
        environment: 'jsdom',
        environmentOptions: { jsdom: { url: 'https://my.local.konomi.tv:7200/' } },
        include: ['tests/program-reminders*.test.ts'],
    },
});
