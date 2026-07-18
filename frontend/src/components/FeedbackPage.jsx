import { useState } from 'react'

export default function FeedbackPage({ userId }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [feedback, setFeedback] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [submitted, setSubmitted] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (saving) return

    setSaving(true)
    setError('')
    try {
      const res = await fetch('/api/contact-feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          name: name.trim(),
          email: email.trim(),
          feedback: feedback.trim(),
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Submit failed (${res.status})`)
      }
      setSubmitted(true)
      setName('')
      setEmail('')
      setFeedback('')
    } catch (err) {
      setError(err.message || 'Failed to submit feedback')
    } finally {
      setSaving(false)
    }
  }

  if (submitted) {
    return (
      <div className="panel page-panel feedback-page">
        <div className="page-header">
          <h2 className="page-title">Thank you!</h2>
          <p className="page-subtitle">
            Your feedback has been received. We appreciate you helping us improve Memoria.
          </p>
        </div>
        <button type="button" className="btn" onClick={() => setSubmitted(false)}>
          Send more feedback
        </button>
      </div>
    )
  }

  return (
    <div className="panel page-panel feedback-page">
      <div className="page-header">
        <h2 className="page-title">Feedback</h2>
        <p className="page-subtitle">Tell us what you think — we read every message.</p>
      </div>

      <form className="page-form" onSubmit={handleSubmit}>
        <label className="auth-label">
          Name
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="Your name"
          />
        </label>

        <label className="auth-label">
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="you@example.com"
          />
        </label>

        <label className="auth-label">
          Feedback
          <textarea
            className="page-textarea"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            rows={6}
            required
            placeholder="What's working well? What could be better?"
          />
        </label>

        <button
          className="btn"
          type="submit"
          disabled={saving || !name.trim() || !email.trim() || !feedback.trim()}
        >
          {saving ? (
            <span className="btn-loading">
              <span className="spinner" aria-hidden="true" />
              Sending…
            </span>
          ) : (
            'Submit feedback'
          )}
        </button>
      </form>

      {error && <div className="error">{error}</div>}
    </div>
  )
}
