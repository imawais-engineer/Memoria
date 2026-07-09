import { useCallback, useEffect, useState } from 'react'
import { DEMO_TOKEN } from '../App.jsx'

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export default function MemoryGraph({ userId }) {
  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`/api/memories?user_id=${encodeURIComponent(userId)}`)
      if (!res.ok) throw new Error(`Backend returned ${res.status}`)
      setMemories(await res.json())
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
      setMemories((list) => list.filter((m) => m.id !== id))
    } catch (e) {
      setError(e.message || 'Failed to delete memory')
    }
  }

  return (
    <div className="panel">
      <div className="table-tools">
        <div className="muted">
          {loading ? 'Loading…' : `${memories.length} memories for ${userId}`}
        </div>
        <button className="refresh" onClick={load}>
          Refresh
        </button>
      </div>

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
          {memories.map((m) => (
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
          {!loading && memories.length === 0 && (
            <tr>
              <td colSpan="6" className="muted">
                No memories yet for this user.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {error && <div className="error">{error}</div>}
    </div>
  )
}
