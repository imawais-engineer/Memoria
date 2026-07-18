import { useNavigate } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import MemoriaLogo from './MemoriaLogo.jsx'
import { FeatureIcon, StepIcon } from './Icons.jsx'
import { APP_NAME_DISPLAY, APP_TAGLINE_SUFFIX } from '../constants/branding.js'
import './Landing.css'

const GITHUB_URL = 'https://github.com/imawais-engineer/Memoria'
const DOCS_URL = 'https://github.com/imawais-engineer/Memoria/blob/main/docs/ARCHITECTURE.md'
const ARCHITECTURE_URL =
  'https://github.com/imawais-engineer/Memoria/blob/main/Submission%20Files/architecture.html'

const BENCHMARK = {
  without: 0.64,
  withMemory: 0.92,
  improvement: 78,
}

const HERO_STATS = [
  { value: '+77.6%', label: 'Benchmark uplift' },
  { value: '6', label: 'Memory types' },
  { value: 'MCP', label: 'External agent skills' },
]

const PRODUCT_HIGHLIGHTS = [
  { title: 'Streaming chat', desc: 'SSE token streaming with model switcher and Markdown + LaTeX replies.' },
  { title: 'Slash commands', desc: '/imagine, /tasks_list, /list_memory, and more — type / for the full table.' },
  { title: 'Tasks & media', desc: 'Create tasks in chat; browse, download, or delete generated assets.' },
  { title: 'Personal Intelligence', desc: 'Toggle global memory access or run MemoryLess incognito sessions.' },
]

const FEATURES = [
  {
    icon: 'memory',
    title: 'Persistent Cross-Session Memory',
    description:
      'Facts extracted from every conversation are embedded and recalled across separate chats and return visits.',
  },
  {
    icon: 'wave',
    title: 'Intelligent Forgetting & Consolidation',
    description:
      'Daily decay archives stale memories; weekly Qwen clustering merges related facts into concise summaries.',
  },
  {
    icon: 'link',
    title: 'Personal Intelligence (Global Memory Access)',
    description:
      'Connect insights across all your sessions with a toggleable global memory layer powered by hybrid vector search.',
  },
  {
    icon: 'shield',
    title: 'MemoryLess Incognito Mode',
    description:
      'Start private chats that never write to long-term storage — perfect for sensitive topics or one-off questions.',
  },
  {
    icon: 'bolt',
    title: 'MCP Skills Server (Interoperable)',
    description:
      'Expose memory tools via MCP so external agents can query, strengthen, or forget user knowledge programmatically.',
  },
  {
    icon: 'feedback',
    title: 'Real-time Learning from Feedback',
    description:
      'Thumbs-up and thumbs-down on replies strengthen or weaken the memories that informed them in real time.',
  },
]

const STEPS = [
  {
    icon: 'chat',
    title: 'Chat Naturally',
    description: 'Talk to Memoria like any assistant — or use /imagine, /gen_video, /gen_voice in chat.',
  },
  {
    icon: 'spark',
    title: 'Qwen Extracts Memories',
    description: 'Qwen function calling pulls structured facts from each turn and embeds them with text-embedding-v3.',
  },
  {
    icon: 'database',
    title: 'Smart Storage + Decay',
    description: 'PostgreSQL + pgvector stores vectors; Celery Beat handles decay and consolidation on schedule.',
  },
  {
    icon: 'target',
    title: 'Next Session — Already Knows You',
    description: 'Hybrid retrieval packs the most relevant memories into every reply, even days later.',
  },
]

function NeuralVisual() {
  return (
    <div className="landing-neural" aria-hidden="true">
      <div className="landing-neural-glow" />
      <svg className="landing-neural-svg" viewBox="0 0 320 320" fill="none">
        <circle className="landing-neural-orbit" cx="160" cy="160" r="120" />
        <circle className="landing-neural-orbit landing-neural-orbit--inner" cx="160" cy="160" r="72" />
        {[
          [160, 40],
          [260, 100],
          [280, 200],
          [200, 280],
          [80, 260],
          [40, 140],
          [100, 60],
        ].map(([cx, cy], i) => (
          <g key={i}>
            <line className="landing-neural-line" x1="160" y1="160" x2={cx} y2={cy} />
            <circle className="landing-neural-node" cx={cx} cy={cy} r="8" />
          </g>
        ))}
        <circle className="landing-neural-core" cx="160" cy="160" r="28" />
      </svg>
      <div className="landing-neural-logo">
        <MemoriaLogo size="md" />
      </div>
    </div>
  )
}

function useRevealOnScroll() {
  const rootRef = useRef(null)

  useEffect(() => {
    const root = rootRef.current
    if (!root) return undefined

    const targets = root.querySelectorAll('.landing-reveal')
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('landing-reveal--visible')
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    )

    targets.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])

  return rootRef
}

export default function Landing({ onGetStarted }) {
  const navigate = useNavigate()
  const pageRef = useRevealOnScroll()

  function goToAuth() {
    if (onGetStarted) {
      onGetStarted()
      return
    }
    navigate('/auth')
  }

  return (
    <div className="landing-page" ref={pageRef}>
      <div className="landing-bg">
        <div className="landing-bg-grid" />
        <div className="landing-bg-glow landing-bg-glow--purple" />
        <div className="landing-bg-glow landing-bg-glow--cyan" />
        {Array.from({ length: 18 }).map((_, i) => (
          <span
            key={i}
            className="landing-particle"
            style={{
              left: `${(i * 17 + 5) % 100}%`,
              top: `${(i * 23 + 11) % 100}%`,
              animationDelay: `${i * 0.7}s`,
              animationDuration: `${14 + (i % 5) * 3}s`,
            }}
          />
        ))}
      </div>

      <header className="landing-nav">
        <a href="#top" className="landing-nav-brand">
          <MemoriaLogo
            size="md"
            showName
            name={APP_NAME_DISPLAY}
            matchIconSize
            nameClassName="landing-nav-name"
          />
        </a>
        <nav className="landing-nav-links" aria-label="Primary">
          <a href="#product">Product</a>
          <a href="#features">Features</a>
          <a href="#how-it-works">How it Works</a>
          <a href="#benchmarks">Benchmarks</a>
        </nav>
        <button type="button" className="landing-btn landing-btn--primary landing-nav-cta" onClick={goToAuth}>
          Get Started
        </button>
      </header>

      <main id="top">
        <section className="landing-hero landing-reveal">
          <div className="landing-hero-content">
            <p className="landing-eyebrow">Qwen Cloud Hackathon · Track 1 — MemoryAgent</p>
            <h1 className="landing-hero-title">
              Meet <span className="landing-gradient-text">{APP_NAME_DISPLAY}</span> — The AI That{' '}
              <span className="landing-gradient-text">Remembers You</span>
            </h1>
            <p className="landing-hero-sub">{APP_TAGLINE_SUFFIX}. Built on Qwen Cloud with hybrid pgvector
              memory, autonomous forgetting, and a full React dashboard.</p>
            <div className="landing-hero-actions">
              <button type="button" className="landing-btn landing-btn--primary landing-btn--lg" onClick={goToAuth}>
                Get Started
              </button>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="landing-btn landing-btn--ghost landing-btn--lg"
              >
                View on GitHub
              </a>
            </div>
            <div className="landing-hero-stats">
              {HERO_STATS.map((stat) => (
                <div key={stat.label} className="landing-stat-pill">
                  <strong>{stat.value}</strong>
                  <span>{stat.label}</span>
                </div>
              ))}
            </div>
          </div>
          <NeuralVisual />
        </section>

        <section id="product" className="landing-section landing-reveal">
          <div className="landing-section-header">
            <h2 className="landing-section-title">One Dashboard, Full Control</h2>
            <p className="landing-section-lead">
              Chat, memories, persona, tasks, and media — unified under a single dark theme with
              high-contrast typography and accessible scroll surfaces.
            </p>
          </div>
          <div className="landing-product-grid">
            {PRODUCT_HIGHLIGHTS.map((item) => (
              <article key={item.title} className="landing-glass-card landing-product-card">
                <h3>{item.title}</h3>
                <p>{item.desc}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="features" className="landing-section landing-reveal">
          <div className="landing-section-header">
            <h2 className="landing-section-title">Built for Real Memory</h2>
            <p className="landing-section-lead">
              Not a bigger context window — a full memory lifecycle powered by Qwen extraction, pgvector search,
              and autonomous background workers.
            </p>
          </div>
          <div className="landing-features-grid">
            {FEATURES.map((feature) => (
              <article key={feature.title} className="landing-glass-card landing-feature-card">
                <span className="landing-feature-icon" aria-hidden="true">
                  <FeatureIcon name={feature.icon} />
                </span>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="how-it-works" className="landing-section landing-reveal">
          <div className="landing-section-header">
            <h2 className="landing-section-title">How It Works</h2>
            <p className="landing-section-lead">
              From natural conversation to durable knowledge — powered by{' '}
              <span className="landing-qwen-badge">Qwen Cloud</span>
            </p>
          </div>
          <ol className="landing-timeline">
            {STEPS.map((step, index) => (
              <li key={step.title} className="landing-timeline-step">
                <div className="landing-timeline-marker">
                  <span className="landing-timeline-icon" aria-hidden="true">
                    <StepIcon name={step.icon} />
                  </span>
                  <span className="landing-timeline-num">{index + 1}</span>
                </div>
                <div className="landing-timeline-body">
                  <h3>{step.title}</h3>
                  <p>{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section id="benchmarks" className="landing-section landing-reveal">
          <div className="landing-benchmark-block landing-glass-card">
            <div className="landing-benchmark-copy">
              <p className="landing-stat-label">Proven impact</p>
              <p className="landing-stat">
                Up to <span className="landing-gradient-text">{BENCHMARK.improvement}%</span> Better Decision
                Accuracy
              </p>
              <p className="landing-benchmark-note">
                Tested across 12 simulated user scenarios with qwen-plus. Composite score combines accuracy,
                safety, and coherence.
              </p>
              <div className="landing-benchmark-mini">
                <div className="landing-benchmark-mini-row">
                  <span>Without memory</span>
                  <div className="landing-benchmark-mini-track">
                    <div
                      className="landing-benchmark-mini-bar landing-benchmark-mini-bar--dim"
                      style={{ width: `${BENCHMARK.without * 100}%` }}
                    />
                  </div>
                  <strong>{BENCHMARK.without.toFixed(2)}</strong>
                </div>
                <div className="landing-benchmark-mini-row">
                  <span>With Memoria</span>
                  <div className="landing-benchmark-mini-track">
                    <div
                      className="landing-benchmark-mini-bar landing-benchmark-mini-bar--bright"
                      style={{ width: `${BENCHMARK.withMemory * 100}%` }}
                    />
                  </div>
                  <strong>{BENCHMARK.withMemory.toFixed(2)}</strong>
                </div>
              </div>
            </div>
            <div className="landing-benchmark-chart">
              <img
                src="/images/benchmark.svg"
                alt="Benchmark chart comparing decision accuracy with and without Memoria memory"
                width={640}
                height={320}
                loading="lazy"
              />
            </div>
          </div>
        </section>

        <section className="landing-section landing-cta-section landing-reveal">
          <div className="landing-section-header">
            <h2 className="landing-section-title">Start Building Your Personal Memory</h2>
            <p className="landing-section-lead">
              Create an account in seconds. Your memories persist across every session.
            </p>
            <button type="button" className="landing-btn landing-btn--primary landing-btn--lg" onClick={goToAuth}>
              Get Started
            </button>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-footer-links">
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
          <a href="https://devpost.com" target="_blank" rel="noopener noreferrer">
            Devpost
          </a>
          <a href={ARCHITECTURE_URL} target="_blank" rel="noopener noreferrer">
            Architecture
          </a>
          <a href={DOCS_URL} target="_blank" rel="noopener noreferrer">
            Docs
          </a>
        </div>
        <p className="landing-footer-tagline">
          Built on Alibaba Cloud &amp; Qwen Cloud · Track 1 – MemoryAgent
        </p>
      </footer>
    </div>
  )
}
