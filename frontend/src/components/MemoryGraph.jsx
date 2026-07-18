import { useCallback, useEffect, useState } from 'react'
import { DEMO_TOKEN } from '../App.jsx'

const TYPE_ORDER = ['core', 'episodic', 'semantic', 'procedural']

const EMPTY_STATS = {
  total_memories: 0,
  consolidated_count: 0,
  summaries_count: 0,
  avg_importance: 0,
  last_consolidation: null,
  types: Object.fromEntries(TYPE_ORDER.map((type) => [type, 0])),
}

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function TypeBarChart({ types }) {
  const maxCount = Math.max(...TYPE_ORDER.map((type) => types[type] || 0), 1)

  return (
    <div className="type-chart">
      {TYPE_ORDER.map((type) => {
        const count = types[type] || 0
        const width = count === 0 ? 0 : Math.max((count / maxCount) * 100, 6)

        return (
          <div key={type} className="type-chart-row">
            <span className={`badge ${type}`}>{type}</span>
            <div className="type-chart-track" aria-hidden="true">
              <div
                className={`type-chart-bar bar-${type}`}
                style={{ width: `${width}%` }}
              />
            </div>
            <span className="type-chart-count">{count}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function MemoryGraph({ userId, username = null, sessionId = null }) {
  const [memories, setMemories] = useState([])
  const [stats, setStats] = useState(EMPTY_STATS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const userLabel = username ? `@${username}` : userId

  const sessionMemories = sessionId
    ? memories.filter(
        (memory) =>
          !memory.session_id || memory.session_id === sessionId || memory.type === 'core',
      )
    : memories

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const headers = { 'X-API-Token': DEMO_TOKEN }
      const [memoriesRes, statsRes] = await Promise.all([
        fetch(`/api/memories?user_id=${encodeURIComponent(userId)}`),
        fetch(`/api/memory-stats?user_id=${encodeURIComponent(userId)}`, { headers }),
      ])
      if (!memoriesRes.ok) throw new Error(`Memories request failed (${memoriesRes.status})`)
      if (!statsRes.ok) throw new Error(`Stats request failed (${statsRes.status})`)
      setMemories(await memoriesRes.json())
      setStats(await statsRes.json())
    } catch (e) {
      setError(e.message || 'Failed to load memories')
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    load()
  }, [load])

  async function forget(id) {
    setError('')
    try {
      const res = await fetch(
        `/api/memories/${id}?user_id=${encodeURIComponent(userId)}`,
        { method: 'DELETE', headers: { 'X-API-Token': DEMO_TOKEN } },
      )
      if (!res.ok) throw new Error(`Delete failed (${res.status})`)
      await load()
    } catch (e) {
      setError(e.message || 'Failed to delete memory')
    }
  }

  return (
    <div className="panel">
      <section className="stats-section">
        <div className="stats-header">
          <h2 className="stats-title">Stats</h2>
          <button className="refresh" onClick={load} disabled={loading}>
            Refresh
          </button>
        </div>

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Total Memories</div>
            <div className="stat-value">{stats.total_memories}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Consolidated</div>
            <div className="stat-value">{stats.consolidated_count}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Summaries</div>
            <div className="stat-value">{stats.summaries_count}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Avg Importance</div>
            <div className="stat-value">{stats.avg_importance.toFixed(2)}</div>
          </div>
          <div className="stat-card stat-card-wide">
            <div className="stat-label">Last Consolidation</div>
            <div className="stat-value stat-value-sm">
              {formatDate(stats.last_consolidation)}
            </div>
          </div>
        </div>

        <div className="type-chart-panel">
          <div className="stat-label">Memory Types</div>
          <TypeBarChart types={stats.types || EMPTY_STATS.types} />
        </div>
      </section>

      <div className="memory-content">
        <div className="table-tools">
          <div className="muted">
            {loading
              ? 'Loading…'
              : `${sessionMemories.length} memories for ${userLabel}`}
          </div>
        </div>

        <div className="memory-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Content</th>
                <th>Importance</th>
                <th>Created</th>
                <th>Decay</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sessionMemories.map((m) => (
                <tr key={m.id}>
                  <td>
                    <span className={`badge ${m.type}`}>{m.type}</span>
                  </td>
                  <td>{m.content}</td>
                  <td>{m.importance.toFixed(2)}</td>
                  <td className="muted">{formatDate(m.created_at)}</td>
                  <td className="muted">{m.decay_rate}</td>
                  <td>
                    <button className="forget" onClick={() => forget(m.id)}>
                      Forget
                    </button>
                  </td>
                </tr>
              ))}
              {!loading && sessionMemories.length === 0 && (
                <tr>
                  <td colSpan="6" className="muted empty-state-cell">
                    No memories in this chat yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
    </div>
  )
}
