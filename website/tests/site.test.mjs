import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dist = path.join(root, 'dist');
const repo = path.resolve(root, '..');
const SITE = 'https://memoria.imawais.engineer';

const files = (await readdir(dist)).filter((f) => f.endsWith('.html')).sort();
const pages = {};
for (const f of files) pages[f] = await readFile(path.join(dist, f), 'utf8');
const urlPath = (f) => (f === 'index.html' ? '' : '/' + f.replace(/\.html$/, ''));
const meta = (h, attr, name) => h.match(new RegExp(`<meta ${attr}="${name}" content="([^"]*)"`))?.[1];
const jsonLd = (h) => [...h.matchAll(/<script type="application\/ld\+json">(.*?)<\/script>/gs)].map((m) => JSON.parse(m[1]));
const decode = (s) => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&#39;/g, "'").replace(/&quot;/g, '"');

test('expected routes exist', () => {
  for (const r of ['index', 'how-it-works', 'features', 'get-started', 'docs', 'benchmark', 'about', '404'])
    assert.ok(files.includes(`${r}.html`), r);
});

test('every page has one h1, a unique title and description, canonical and social tags', () => {
  const titles = new Set(), descs = new Set();
  for (const [f, h] of Object.entries(pages)) {
    assert.equal((h.match(/<h1[\s>]/g) || []).length, 1, `${f}: h1 count`);
    const title = h.match(/<title>([^<]+)<\/title>/)?.[1];
    const desc = meta(h, 'name', 'description');
    assert.ok(title && desc, `${f}: title/description`);
    assert.ok(!titles.has(title), `${f}: duplicate title`); titles.add(title);
    assert.ok(!descs.has(desc), `${f}: duplicate description`); descs.add(desc);
    const canon = h.match(/<link rel="canonical" href="([^"]+)"/)?.[1];
    assert.equal(canon, SITE + urlPath(f), `${f}: canonical`);
    assert.ok(!canon.endsWith('/') && !canon.includes('www.'), `${f}: canonical form`);
    assert.equal(meta(h, 'property', 'og:title'), title);
    assert.equal(meta(h, 'property', 'og:description'), desc);
    assert.ok(meta(h, 'property', 'og:image'), `${f}: og:image`);
    assert.equal(meta(h, 'property', 'og:image:width'), '1200');
    assert.equal(meta(h, 'property', 'og:image:height'), '630');
    assert.equal(meta(h, 'property', 'og:site_name'), 'Memoria');
    assert.equal(meta(h, 'name', 'application-name'), 'Memoria');
    assert.equal(meta(h, 'name', 'twitter:card'), 'summary_large_image');
    assert.ok(meta(h, 'name', 'twitter:image'), `${f}: twitter:image`);
    assert.ok(h.includes('<html lang="en"'), `${f}: lang`);
    assert.ok(h.includes('<main'), `${f}: main landmark`);
  }
});

test('home title is exact and JSON-LD is complete', () => {
  const h = pages['index.html'];
  assert.equal(decode(h.match(/<title>([^<]+)<\/title>/)[1]), 'Memoria – Self-Evolving Personal AI with Human-like Memory');
  const types = jsonLd(h).map((b) => b['@type']);
  for (const t of ['WebSite', 'SoftwareApplication', 'Person']) assert.ok(types.includes(t), t);
  const app = jsonLd(h).find((b) => b['@type'] === 'SoftwareApplication');
  for (const k of ['name', 'description', 'license', 'codeRepository', 'applicationCategory', 'author']) assert.ok(app[k], k);
  const site = jsonLd(h).find((b) => b['@type'] === 'WebSite');
  assert.equal(site.name, 'Memoria'); assert.ok(site.alternateName); assert.equal(site.url, SITE);
});

test('inner pages have BreadcrumbList', () => {
  for (const f of files.filter((f) => !['index.html', '404.html'].includes(f)))
    assert.ok(jsonLd(pages[f]).some((b) => b['@type'] === 'BreadcrumbList'), f);
});

test('404 is noindex and absent from sitemap; sitemap and robots are correct', async () => {
  assert.match(pages['404.html'], /<meta name="robots" content="noindex"/);
  const sm = await readFile(path.join(dist, 'sitemap.xml'), 'utf8');
  assert.ok(!sm.includes('404'));
  for (const f of files.filter((f) => f !== '404.html')) assert.ok(sm.includes(`<loc>${SITE}${urlPath(f)}</loc>`), f);
  const robots = await readFile(path.join(dist, 'robots.txt'), 'utf8');
  assert.match(robots, /User-agent: \*\nAllow: \//);
  assert.ok(robots.includes(`Sitemap: ${SITE}/sitemap.xml`));
  assert.ok(!/Disallow/i.test(robots));
});

test('images have alt, width and height', () => {
  for (const [f, h] of Object.entries(pages))
    for (const tag of h.match(/<img\b[^>]*>/g) || []) {
      assert.match(tag, /\balt="/, `${f}: alt in ${tag}`);
      assert.match(tag, /\bwidth="\d+"/, `${f}: width`);
      assert.match(tag, /\bheight="\d+"/, `${f}: height`);
    }
});

test('no em dashes or secret-like strings in page text', () => {
  for (const [f, h] of Object.entries(pages)) {
    const text = h.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<style[\s\S]*?<\/style>/g, '');
    assert.ok(!text.includes('\u2014'), `${f}: em dash`);
    assert.ok(!/sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}/.test(h), `${f}: secret-like`);
  }
});

test('every code block has a copy button', () => {
  for (const [f, h] of Object.entries(pages)) {
    const pre = (h.match(/<pre\b/g) || []).length;
    const btn = (h.match(/class="copy-btn/g) || []).length;
    assert.equal(btn, pre, `${f}: copy buttons`);
  }
});

test('favicon.ico has a 48x48 entry and og image is 1200x630', async () => {
  const ico = await readFile(path.join(dist, 'favicon.ico'));
  const n = ico.readUInt16LE(4);
  const sizes = Array.from({ length: n }, (_, i) => ico[6 + i * 16] || 256);
  assert.ok(sizes.includes(48), `sizes ${sizes}`);
  const png = await readFile(path.join(dist, 'og-image.png'));
  assert.equal(png.readUInt32BE(16), 1200); assert.equal(png.readUInt32BE(20), 630);
});

test('every get-started command appears verbatim in README.md', async () => {
  const readme = await readFile(path.join(repo, 'README.md'), 'utf8');
  const h = pages['get-started.html'];
  const blocks = [...h.matchAll(/<div class="codeblock[\s\S]*?<span>([^<]*)<\/span>[\s\S]*?<pre[^>]*><code>([\s\S]*?)<\/code><\/pre>/g)];
  assert.ok(blocks.length >= 5);
  let checked = 0;
  for (const [, label, code] of blocks) {
    if (label === '.env') continue; // placeholder variable names, not commands
    for (const raw of decode(code).split('\n')) {
      const line = raw.trimEnd();
      if (!line.trim() || line.trim().startsWith('#')) continue;
      assert.ok(readme.includes(line), `not in README: ${line}`);
      checked++;
    }
  }
  assert.ok(checked >= 12, `checked ${checked}`);
});

test('page titles are at most 60 characters except the exact home title', () => {
  for (const [f, h] of Object.entries(pages)) {
    if (f === 'index.html') continue;
    const title = decode(h.match(/<title>([^<]+)<\/title>/)[1]);
    assert.ok(title.length <= 60, `${f}: title is ${title.length} chars`);
    assert.ok(title.includes('Memoria'), `${f}: title has Memoria`);
  }
});

test('home shows the demo video link while DEMO_URL is null, and no live demo claims', async () => {
  const cfg = await readFile(path.join(root, 'src/config.ts'), 'utf8');
  const demoNull = /DEMO_URL: string \| null = null;/.test(cfg);
  const home = pages['index.html'];
  const about = pages['about.html'];
  if (demoNull) {
    assert.ok(/<a [^>]*href="https:\/\/youtu\.be\/ANFAl6bwjjI"[^>]*>Watch demo video<\/a>/.test(home));
    assert.ok(!home.includes('Live demo'));
    assert.ok(about.includes('hosted demo is currently offline'));
  } else {
    assert.ok(home.includes('Live demo'));
  }
  for (const [f, h] of Object.entries(pages)) {
    if (demoNull) assert.ok(!/live demo/i.test(h), `${f}: live demo claim`);
  }
});

test('website benchmark data equals scripts/benchmark_results.json', async () => {
  const a = JSON.parse(await readFile(path.join(root, 'src/data/benchmark_results.json'), 'utf8'));
  const b = JSON.parse(await readFile(path.join(repo, 'scripts/benchmark_results.json'), 'utf8'));
  assert.deepEqual(a, b);
});
