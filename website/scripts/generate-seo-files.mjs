// Generates sitemap.xml and robots.txt in dist/ from the built HTML.
// A page is listed only if it has no noindex robots meta.
import { readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'dist');
const SITE = 'https://memoria.imawais.engineer';

const urls = [];
for (const f of (await readdir(dist)).filter((n) => n.endsWith('.html')).sort()) {
  const html = await readFile(path.join(dist, f), 'utf8');
  if (/<meta name="robots" content="[^"]*noindex/.test(html)) continue;
  const m = html.match(/<link rel="canonical" href="([^"]+)"/);
  if (m) urls.push(m[1]);
}
urls.sort();
const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls
  .map((u) => `  <url><loc>${u}</loc></url>`)
  .join('\n')}\n</urlset>\n`;
await writeFile(path.join(dist, 'sitemap.xml'), xml);
await writeFile(path.join(dist, 'robots.txt'), `User-agent: *\nAllow: /\n\nSitemap: ${SITE}/sitemap.xml\n`);
console.log(`sitemap.xml: ${urls.length} urls; robots.txt written`);
