export const SITE_URL = 'https://memoria.imawais.engineer';
export const SITE_NAME = 'Memoria';
export const GITHUB_URL = 'https://github.com/imawais-engineer/Memoria';
export const GITHUB_PROFILE_URL = 'https://github.com/imawais-engineer';
export const GITHUB_BLOB = `${GITHUB_URL}/blob/main`;
// Hosted demo URL. Keep null while the hosted demo is offline; the site then shows
// "Watch demo video" instead of "Live demo". Set to the new URL to bring the button back.
export const DEMO_URL: string | null = null;
export const VIDEO_URL = 'https://youtu.be/ANFAl6bwjjI';
export const AUTHOR = 'Muhammad Awais';
export const DEFAULT_DESCRIPTION =
  'Memoria is an open-source personal AI that remembers, forgets, resolves conflicts and reflects on what you tell it. Built on FastAPI, PostgreSQL with pgvector, Redis, Celery and Qwen Cloud.';

export const NAV = [
  { href: '/how-it-works', label: 'How it works' },
  { href: '/features', label: 'Features' },
  { href: '/get-started', label: 'Get started' },
  { href: '/docs', label: 'Docs' },
  { href: '/benchmark', label: 'Benchmark' },
  { href: '/about', label: 'About' },
];

/** Build absolute canonical URL: no trailing slash, home is the bare origin. */
export function canonical(path: string): string {
  const clean = path.replace(/\/+$/, '');
  return `${SITE_URL}${clean}`;
}
