import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { Line, Pie } from 'react-chartjs-2'
import MemoriaLogo from './MemoriaLogo.jsx'
import { APP_TAGLINE_SUFFIX } from '../constants/branding.js'
import {
  BUILD_MILESTONES,
  DAILY_LABELS,
  DAILY_REQUESTS,
  DAILY_TOKENS,
  MODEL_BREAKDOWN,
  PIE_COLORS,
  TECH_STACK,
  USAGE_SUMMARY,
} from '../data/analyticsData.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
)

const CHART_FONT = "'Segoe UI', system-ui, sans-serif"
const GRID_COLOR = 'rgba(154, 160, 184, 0.12)'
const TEXT_COLOR = '#9aa0b8'

const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: TEXT_COLOR, font: { family: CHART_FONT, size: 12 } },
    },
    tooltip: {
      backgroundColor: '#171a2b',
      borderColor: 'rgba(108, 140, 255, 0.35)',
      borderWidth: 1,
      titleFont: { family: CHART_FONT },
      bodyFont: { family: CHART_FONT },
    },
  },
}

function StatCard({ label, value, change }) {
  return (
    <div className="about-stat-card">
      <span className="about-stat-label">{label}</span>
      <span className="about-stat-value">{value}</span>
      {change ? <span className="about-stat-change">{change}</span> : null}
    </div>
  )
}

export default function About() {
  const requestsChartData = {
    labels: DAILY_LABELS,
    datasets: [
      {
        label: 'qwen-plus',
        data: DAILY_REQUESTS['qwen-plus'],
        borderColor: '#6c8cff',
        backgroundColor: 'rgba(108, 140, 255, 0.12)',
        fill: true,
        tension: 0.35,
      },
      {
        label: 'text-embedding-v3',
        data: DAILY_REQUESTS['text-embedding-v3'],
        borderColor: '#48d597',
        backgroundColor: 'rgba(72, 213, 151, 0.1)',
        fill: true,
        tension: 0.35,
      },
      {
        label: 'wan2.1-t2i-plus',
        data: DAILY_REQUESTS['wan2.1-t2i-plus'],
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        fill: true,
        tension: 0.35,
      },
    ],
  }

  const tokensChartData = {
    labels: DAILY_LABELS,
    datasets: [
      {
        label: 'qwen-plus (K tokens)',
        data: DAILY_TOKENS['qwen-plus'],
        borderColor: '#6c8cff',
        backgroundColor: 'rgba(108, 140, 255, 0.15)',
        fill: true,
        tension: 0.35,
      },
      {
        label: 'text-embedding-v3 (K tokens)',
        data: DAILY_TOKENS['text-embedding-v3'],
        borderColor: '#48d597',
        backgroundColor: 'rgba(72, 213, 151, 0.12)',
        fill: true,
        tension: 0.35,
      },
      {
        label: 'wan2.1-t2i-plus (K tokens)',
        data: DAILY_TOKENS['wan2.1-t2i-plus'],
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        fill: true,
        tension: 0.35,
      },
    ],
  }

  const pieData = {
    labels: MODEL_BREAKDOWN.map((row) => row.model),
    datasets: [
      {
        data: MODEL_BREAKDOWN.map((row) => row.requests),
        backgroundColor: PIE_COLORS,
        borderColor: '#121528',
        borderWidth: 2,
      },
    ],
  }

  const axisOptions = {
    scales: {
      x: {
        ticks: { color: TEXT_COLOR, font: { family: CHART_FONT, size: 11 } },
        grid: { color: GRID_COLOR },
      },
      y: {
        ticks: { color: TEXT_COLOR, font: { family: CHART_FONT, size: 11 } },
        grid: { color: GRID_COLOR },
        beginAtZero: true,
      },
    },
  }

  return (
    <div className="panel page-panel about-page">
      <div className="about-hero">
        <MemoriaLogo size="lg" showName tagline={APP_TAGLINE_SUFFIX} layout="stacked" />
      </div>

      <section className="about-section">
        <h2 className="about-section-title">Who Built This</h2>
        <p className="about-text">
          Built by <strong>Muhammad Awais</strong> for the Qwen Cloud Hackathon,
          Track 1 – MemoryAgent.
        </p>
      </section>

      <section className="about-section">
        <h2 className="about-section-title">Purpose</h2>
        <p className="about-text">
          Memoria is a self-evolving personal AI that remembers user preferences,
          learns from feedback, and optimises memory for better decisions.
        </p>
      </section>

      <section className="about-section">
        <h2 className="about-section-title">Tech Stack &amp; Tools</h2>
        <div className="about-tech-grid">
          {TECH_STACK.map((item) => (
            <span key={item} className="about-tech-chip">
              {item}
            </span>
          ))}
        </div>
      </section>

      <section className="about-section">
        <h2 className="about-section-title">Build Timeline</h2>
        <p className="about-text about-timeline-range">9 July – 19 July 2026</p>
        <div className="about-timeline">
          {BUILD_MILESTONES.map((milestone, index) => (
            <div key={milestone.title} className="about-timeline-item">
              <div className="about-timeline-marker">
                <span className="about-timeline-dot" />
                {index < BUILD_MILESTONES.length - 1 && (
                  <span className="about-timeline-line" aria-hidden="true" />
                )}
              </div>
              <div className="about-timeline-content">
                <span className="about-timeline-dates">{milestone.dates}</span>
                <h3>{milestone.title}</h3>
                <p>{milestone.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="about-section">
        <h2 className="about-section-title">Qwen API Usage Analytics</h2>
        <p className="about-text">
          DashScope usage across development and testing (Jul 12 – Jul 18, 2026).
        </p>

        <div className="about-stats-grid">
          <StatCard
            label="Total tokens consumed"
            value={USAGE_SUMMARY.totalTokens}
            change={USAGE_SUMMARY.tokensChange}
          />
          <StatCard
            label="Total requests"
            value={USAGE_SUMMARY.totalRequests}
            change={USAGE_SUMMARY.requestsChange}
          />
          <StatCard label="Avg latency" value={USAGE_SUMMARY.avgLatency} />
          <StatCard label="Avg TTFT" value={USAGE_SUMMARY.avgTtft} />
          <StatCard label="Success rate" value={USAGE_SUMMARY.successRate} />
        </div>

        <div className="about-charts-grid">
          <div className="about-chart-card">
            <h3>Requests per day (top models)</h3>
            <div className="about-chart-wrap">
              <Line
                data={requestsChartData}
                options={{ ...chartDefaults, ...axisOptions }}
              />
            </div>
          </div>
          <div className="about-chart-card">
            <h3>Tokens per day (K, top models)</h3>
            <div className="about-chart-wrap">
              <Line
                data={tokensChartData}
                options={{ ...chartDefaults, ...axisOptions }}
              />
            </div>
          </div>
          <div className="about-chart-card about-chart-card--pie">
            <h3>Request distribution by model</h3>
            <div className="about-chart-wrap about-chart-wrap--pie">
              <Pie
                data={pieData}
                options={{
                  ...chartDefaults,
                  plugins: {
                    ...chartDefaults.plugins,
                    legend: { position: 'right', labels: { color: TEXT_COLOR, boxWidth: 12 } },
                  },
                }}
              />
            </div>
          </div>
        </div>

        <div className="about-table-wrap">
          <table className="about-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Requests</th>
                <th>Success rate</th>
                <th>Avg latency</th>
                <th>Tokens</th>
              </tr>
            </thead>
            <tbody>
              {MODEL_BREAKDOWN.map((row) => (
                <tr key={row.model}>
                  <td><code>{row.model}</code></td>
                  <td>{row.requests}</td>
                  <td>{row.successRate}</td>
                  <td>{row.latency}</td>
                  <td>{row.tokens}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
