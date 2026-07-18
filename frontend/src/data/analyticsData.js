export const USAGE_SUMMARY = {
  totalTokens: '127.4K',
  tokensChange: '+113.4%',
  totalRequests: 469,
  requestsChange: '+28.5%',
  avgLatency: '4.5 s',
  avgTtft: '785 ms',
  successRate: '97.9%',
}

export const MODEL_BREAKDOWN = [
  {
    model: 'qwen-plus',
    requests: 248,
    successRate: '99.19%',
    latency: '2.9s',
    tokens: '68.2K',
  },
  {
    model: 'text-embedding-v3',
    requests: 196,
    successRate: '100%',
    latency: '0.1s',
    tokens: '42.1K',
  },
  {
    model: 'wan2.1-t2i-plus',
    requests: 13,
    successRate: '38.46%',
    latency: '37.4s',
    tokens: '8.4K',
  },
  {
    model: 'wan2.1-t2v-turbo',
    requests: 5,
    successRate: '100%',
    latency: '170.5s',
    tokens: '5.2K',
  },
  {
    model: 'qwen-turbo',
    requests: 3,
    successRate: '100%',
    latency: '2.6s',
    tokens: '1.8K',
  },
  {
    model: 'qwen3-tts-flash',
    requests: 3,
    successRate: '100%',
    latency: '0.8s',
    tokens: '0.9K',
  },
  {
    model: 'qwen3.7-max',
    requests: 1,
    successRate: '100%',
    latency: '51.6s',
    tokens: '0.8K',
  },
]

export const DAILY_LABELS = ['Jul 12', 'Jul 13', 'Jul 14', 'Jul 15', 'Jul 16', 'Jul 17', 'Jul 18']

export const DAILY_REQUESTS = {
  'qwen-plus': [18, 24, 28, 35, 42, 52, 49],
  'text-embedding-v3': [12, 18, 22, 28, 32, 42, 42],
  'wan2.1-t2i-plus': [0, 1, 2, 2, 3, 3, 2],
}

export const DAILY_TOKENS = {
  'qwen-plus': [4.2, 6.1, 7.8, 9.5, 11.2, 14.8, 14.6],
  'text-embedding-v3': [2.8, 4.2, 5.1, 6.8, 7.9, 9.4, 5.9],
  'wan2.1-t2i-plus': [0, 0.4, 0.8, 1.2, 2.1, 2.4, 1.5],
}

export const PIE_COLORS = [
  '#6c8cff',
  '#48d597',
  '#f59e0b',
  '#a855f7',
  '#38bdf8',
  '#f472b6',
  '#94a3b8',
]

export const BUILD_MILESTONES = [
  {
    dates: '9–10 Jul',
    title: 'Core memory pipeline + retrieval',
    detail: 'pgvector storage, hybrid retrieval, Celery ingestion',
  },
  {
    dates: '11–12 Jul',
    title: 'Consolidation, conflict detection, reflection',
    detail: 'Background workers, memory lifecycle automation',
  },
  {
    dates: '13–14 Jul',
    title: 'Auth, sessions, UI polish',
    detail: 'User accounts, chat sessions, dashboard shell',
  },
  {
    dates: '15–16 Jul',
    title: 'Multimodal generation, landing page',
    detail: 'Image/video/voice via DashScope, public marketing site',
  },
  {
    dates: '17–19 Jul',
    title: 'Streaming, tasks, branding, About page',
    detail: 'SSE chat, task management, analytics dashboard',
  },
]

export const TECH_STACK = [
  'FastAPI',
  'PostgreSQL + pgvector',
  'Redis',
  'Celery',
  'DashScope (Qwen models)',
  'React + Vite',
  'Docker',
  'Terraform',
  'Alibaba Cloud',
]
