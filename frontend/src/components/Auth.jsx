import { useState } from 'react'

export default function Auth({ onAuth, embedded = false }) {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    username: '',
    favorite_book: '',
  })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function updateField(field) {
    return (e) => setForm((current) => ({ ...current, [field]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)

    const endpoint = mode === 'signup' ? '/auth/signup' : '/auth/login'
    const body =
      mode === 'signup'
        ? {
            first_name: form.first_name.trim(),
            last_name: form.last_name.trim(),
            username: form.username.trim(),
            favorite_book: form.favorite_book.trim(),
          }
        : {
            username: form.username.trim(),
            favorite_book: form.favorite_book.trim(),
          }

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        if (res.status === 409) {
          setError('That username is already taken.')
        } else if (res.status === 401) {
          setError('Invalid username or favorite book.')
        } else {
          setError(data.detail || `Request failed (${res.status})`)
        }
        return
      }

      const data = await res.json()
      onAuth({
        user_id: data.user_id,
        username: data.username,
        global_memory_enabled: data.global_memory_enabled ?? true,
        persona: data.persona ?? null,
      })
    } catch {
      setError('Could not reach the server. Is the backend running?')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={`auth-wrapper${embedded ? ' auth-wrapper--embedded' : ''}`}>
      <div className="auth-card">
        {!embedded && (
          <div className="auth-header">
            <div className="logo">M</div>
            <div>
              <div className="title">Memoria</div>
              <div className="subtitle">Personal AI with long-term memory</div>
            </div>
          </div>
        )}

        <div className="auth-tabs">
          <button
            type="button"
            className={`tab ${mode === 'login' ? 'active' : ''}`}
            onClick={() => {
              setMode('login')
              setError('')
            }}
          >
            Login
          </button>
          <button
            type="button"
            className={`tab ${mode === 'signup' ? 'active' : ''}`}
            onClick={() => {
              setMode('signup')
              setError('')
            }}
          >
            Signup
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {mode === 'signup' && (
            <>
              <label className="auth-label">
                First Name
                <input
                  value={form.first_name}
                  onChange={updateField('first_name')}
                  placeholder="Jane"
                  required
                  autoComplete="given-name"
                />
              </label>
              <label className="auth-label">
                Last Name
                <input
                  value={form.last_name}
                  onChange={updateField('last_name')}
                  placeholder="Doe"
                  required
                  autoComplete="family-name"
                />
              </label>
            </>
          )}

          <label className="auth-label">
            Username
            <input
              value={form.username}
              onChange={updateField('username')}
              placeholder="janedoe"
              required
              autoComplete="username"
            />
          </label>

          <label className="auth-label">
            Favorite Book
            <input
              value={form.favorite_book}
              onChange={updateField('favorite_book')}
              placeholder="Your soft password"
              required
              autoComplete={mode === 'signup' ? 'off' : 'current-password'}
            />
          </label>

          <button className="btn auth-submit" type="submit" disabled={submitting}>
            {submitting ? (
              <span className="btn-loading">
                <span className="spinner" aria-hidden="true" />
                Please wait…
              </span>
            ) : mode === 'signup' ? (
              'Create account'
            ) : (
              'Log in'
            )}
          </button>
        </form>

        {error && <div className="error auth-error">{error}</div>}
      </div>
    </div>
  )
}
