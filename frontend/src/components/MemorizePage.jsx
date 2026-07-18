import { useState } from 'react'

export default function MemorizePage({ userId }) {
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    const text = content.trim()
    if (!text || saving) return

    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const res = await fetch('/api/memorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, content: text }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Failed to memorize (${res.status})`)
      }
      setContent('')
      setSuccess('Memory saved successfully.')
    } catch (err) {
      setError(err.message || 'Failed to save memory')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="panel page-panel memorize-page">
      <div className="page-header">
        <h2 className="page-title">Memorize something</h2>
        <p className="page-subtitle">
          Add a fact directly to your memory — no AI processing required.
        </p>
      </div>

      <form className="page-form" onSubmit={handleSubmit}>
        <label className="auth-label">
          What should I remember?
          <textarea
            className="page-textarea"
            value={content}
            onChange={(e) => {
              setSuccess('')
              setContent(e.target.value)
            }}
            rows={6}
            placeholder="e.g. My favorite coffee shop is Blue Bottle on Main St."
            required
          />
        </label>

        <button className="btn" type="submit" disabled={saving || !content.trim()}>
          {saving ? (
            <span className="btn-loading">
              <span className="spinner" aria-hidden="true" />
              Saving…
            </span>
          ) : (
            'Memorize'
          )}
        </button>
      </form>

      {success && <div className="success">{success}</div>}
      {error && <div className="error">{error}</div>}
    </div>
  )
}
