const BENCHMARK = {
  without: 0.64,
  withMemory: 0.92,
  improvement: 77.6,
}

const HIGHLIGHTS = [
  {
    title: 'Persistent memory',
    description:
      'Facts extracted from your conversations are embedded and stored for long-term recall.',
  },
  {
    title: 'Cross-session recall',
    description:
      'Personal Intelligence lets Memoria connect insights across separate chats.',
  },
  {
    title: 'Memory tiers',
    description:
      'Session memory, personal memories, context archive, and optional MemoryLess mode.',
  },
  {
    title: 'Proven impact',
    description: `Benchmark suite shows ${BENCHMARK.improvement}% higher response quality with memory.`,
  },
]

export default function Landing({ onLaunch }) {
  return (
    <div className="landing-wrapper">
      <div className="landing-hero">
        <div className="landing-brand">
          <div className="logo">M</div>
          <div>
            <h1 className="landing-title">Memoria</h1>
            <p className="landing-tagline">
              Personal AI with human-like memory — remembers, forgets, and reflects.
            </p>
          </div>
        </div>

        <button type="button" className="btn landing-cta" onClick={onLaunch}>
          Launch App
        </button>
      </div>

      <section className="landing-section">
        <h2 className="landing-section-title">Why Memoria?</h2>
        <div className="landing-grid">
          {HIGHLIGHTS.map((item) => (
            <article key={item.title} className="landing-card">
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <h2 className="landing-section-title">Benchmark results</h2>
        <p className="landing-section-lead">
          Average composite score (accuracy + safety + coherence) across 12 realistic
          scenarios — see{' '}
          <code className="landing-code">scripts/benchmark_results.json</code>.
        </p>
        <div className="landing-benchmark" role="img" aria-label="Benchmark bar chart">
          <div className="landing-benchmark-row">
            <span className="landing-benchmark-label">Without memory</span>
            <div className="landing-benchmark-track">
              <div
                className="landing-benchmark-bar bar-without"
                style={{ width: `${BENCHMARK.without * 100}%` }}
              />
            </div>
            <span className="landing-benchmark-value">{BENCHMARK.without.toFixed(2)}</span>
          </div>
          <div className="landing-benchmark-row">
            <span className="landing-benchmark-label">With memory</span>
            <div className="landing-benchmark-track">
              <div
                className="landing-benchmark-bar bar-with"
                style={{ width: `${BENCHMARK.withMemory * 100}%` }}
              />
            </div>
            <span className="landing-benchmark-value">{BENCHMARK.withMemory.toFixed(2)}</span>
          </div>
          <p className="landing-benchmark-foot">
            +{BENCHMARK.improvement}% average improvement with memory enabled
          </p>
        </div>
      </section>
    </div>
  )
}
