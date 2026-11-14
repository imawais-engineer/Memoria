import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://memoria.imawais.engineer',
  trailingSlash: 'never',
  build: { format: 'file' },
  vite: { plugins: [tailwindcss()] },
});
