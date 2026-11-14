// Checks internal links against dist/ and external links over the network.
// Usage: node scripts/check-links.mjs [--internal-only]
import { readdir, readFile, access } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'dist');
const internalOnly = process.argv.includes('--internal-only');
const SITE = 'https://memoria.imawais.engineer';
const htmlFiles = (await readdir(dist)).filter((f) => f.endsWith('.html'));
const ids = {}, internal = new Set(), external = new Set();
const dec = (s) => s.replace(/&amp;/g, '&');

for (const f of htmlFiles) {
  const h = await readFile(path.join(dist, f), 'utf8');
  ids[f] = new Set([...h.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));
  for (const m of h.matchAll(/<(?:a|link|img|script)\b[^>]*?(?:href|src)="([^"]+)"/g)) {
    const u = dec(m[1]);
    if (u.startsWith('mailto:') || u.startsWith('http://localhost')) continue;
    if (/^https?:\/\//.test(u)) {
      if (u.startsWith(SITE)) internal.add(`${f}|${u.slice(SITE.length) || '/'}`);
      else external.add(u);
    } else internal.add(`${f}|${u}`);
  }
}

let bad = 0;
const exists = (p) => access(p).then(() => true, () => false);
for (const entry of internal) {
  const [from, link] = entry.split('|');
  const [p, hash] = link.split('#');
  let file = p === '' ? from : p === '/' ? 'index.html' : p.replace(/^\//, '');
  const candidates = [file, `${file}.html`];
  let found = null;
  for (const c of candidates) if (await exists(path.join(dist, c))) { found = c; break; }
  if (!found) { console.log(`BROKEN internal (${from}): ${link}`); bad++; continue; }
  if (hash && found.endsWith('.html') && !ids[found]?.has(hash)) { console.log(`BROKEN anchor (${from}): ${link}`); bad++; }
}
console.log(`internal: ${internal.size} checked, ${bad} broken`);

let ebad = 0;
if (!internalOnly) {
  for (const u of external) {
    try {
      let r = await fetch(u, { method: 'HEAD', redirect: 'follow', signal: AbortSignal.timeout(15000) });
      if (r.status >= 400) r = await fetch(u, { redirect: 'follow', signal: AbortSignal.timeout(15000) });
      if (r.status >= 400) { console.log(`FAIL ${r.status}: ${u}`); ebad++; }
    } catch (e) { console.log(`FAIL (${e.message}): ${u}`); ebad++; }
  }
  console.log(`external: ${external.size} checked, ${ebad} failed`);
}
process.exit(bad ? 1 : 0);
