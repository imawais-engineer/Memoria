// Generates WebP screenshots, icons and the OG image from the repo's original files.
// Originals are only read. Outputs are committed so Vercel needs no files outside website/.
import sharp from 'sharp';
import pngToIco from 'png-to-ico';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repo = path.resolve(root, '..');
const pub = path.join(root, 'public');
const img = path.join(pub, 'img');
await mkdir(img, { recursive: true });

const sources = {
  dashboard: ['Submission Files/Dashboard.png', 1600],
  commands: ['Submission Files/Commands.png', 1600],
  'about-01': ['Submission Files/About - 01.png', 1600],
  'about-02': ['Submission Files/About - 02.png', 1600],
  'about-03': ['Submission Files/About - 03.png', 1600],
  'about-04': ['Submission Files/About - 04.png', 1600],
  architecture: ['Submission Files/architecture.png', 1680],
  benchmark: ['scripts/benchmark_results.png', 1200],
};
const dims = {};
for (const [name, [file, width]] of Object.entries(sources)) {
  const src = sharp(path.join(repo, file));
  const meta = await src.metadata();
  const w = Math.min(width, meta.width);
  const out = await src.resize({ width: w }).webp({ quality: 82 }).toFile(path.join(img, `${name}.webp`));
  dims[name] = { width: out.width, height: out.height };
}
await writeFile(path.join(root, 'src/images.json'), JSON.stringify(dims, null, 2) + '\n');

// Icon: rounded square with blue-to-green gradient and an "M".
const iconSvg = (s) => `<svg xmlns="http://www.w3.org/2000/svg" width="${s}" height="${s}" viewBox="0 0 100 100">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6c8cff"/><stop offset="1" stop-color="#48d597"/></linearGradient></defs>
<rect width="100" height="100" rx="22" fill="url(#g)"/>
<path d="M24 74V28h9l17 27 17-27h9v46h-9V45L50 71 33 45v29z" fill="#0f1220"/></svg>`;
const png = (s) => sharp(Buffer.from(iconSvg(s))).png().toBuffer();
await writeFile(path.join(pub, 'favicon-48.png'), await png(48));
await writeFile(path.join(pub, 'icon-192.png'), await png(192));
await writeFile(path.join(pub, 'icon-512.png'), await png(512));
await writeFile(path.join(pub, 'apple-touch-icon.png'), await sharp(Buffer.from(iconSvg(180))).flatten({ background: '#0f1220' }).png().toBuffer());
await writeFile(path.join(pub, 'favicon.ico'), await pngToIco([await png(48), await png(96)]));
await writeFile(path.join(pub, 'favicon.svg'), iconSvg(64));

// OG image 1200x630.
const og = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6c8cff"/><stop offset="1" stop-color="#48d597"/></linearGradient></defs>
<rect width="1200" height="630" fill="#0f1220"/>
<rect x="0" y="0" width="1200" height="12" fill="url(#g)"/>
<g transform="translate(80,90)"><rect width="96" height="96" rx="22" fill="url(#g)"/>
<path d="M23 71V27h9l16 26 16-26h9v44h-9V43L48 68 32 43v28z" fill="#0f1220" transform="scale(1.0)"/></g>
<text x="80" y="330" font-family="DejaVu Sans, Arial, sans-serif" font-weight="700" font-size="104" fill="#f4f6fc">Memoria</text>
<text x="80" y="410" font-family="DejaVu Sans, Arial, sans-serif" font-size="44" fill="#f4f6fc">Self-evolving personal AI</text>
<text x="80" y="465" font-family="DejaVu Sans, Arial, sans-serif" font-size="44" fill="#f4f6fc">with human-like memory</text>
<text x="80" y="570" font-family="DejaVu Sans, Arial, sans-serif" font-size="30" fill="#48d597">Open source · Apache 2.0 · memoria.imawais.engineer</text>
</svg>`;
await sharp(Buffer.from(og)).png().toFile(path.join(pub, 'og-image.png'));
console.log('assets generated');
