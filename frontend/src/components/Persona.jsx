import { useEffect, useState } from 'react'

const DEFAULT_PERSONA = {
  response_length: 'balanced',
  tone: 'professional',
  behavior: 'cautious',
  custom_tone: '',
  custom_behavior: '',
}

export default function Persona({ userId, persona, onSaved }) {
  const [form, setForm] = useState(DEFAULT_PERSONA)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    if (persona) {
      setForm({
        response_length: persona.response_length || 'balanced',
        tone: persona.tone || 'professional',
        behavior: persona.behavior || 'cautious',
        custom_tone: persona.custom_tone || '',
        custom_behavior: persona.custom_behavior || '',
      })
    }
  }, [persona])

  function updateField(field) {
    return (e) => {
      setSuccess('')
      setForm((current) => ({ ...current, [field]: e.target.value }))
    }
  }

  async function save() {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const payload = {
        user_id: userId,
        persona: {
          response_length: form.response_length,
          tone: form.tone,
          behavior: form.behavior,
          custom_tone: form.tone === 'custom' ? form.custom_tone.trim() : null,
          custom_behavior:
            form.behavior === 'custom' ? form.custom_behavior.trim() : null,
        },
      }

      const res = await fetch('/auth/preferences', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        const detail = data.detail
        if (Array.isArray(detail)) {
          throw new Error(detail.map((item) => item.msg).join(', '))
        }
        throw new Error(detail || `Save failed (${res.status})`)
      }

      const data = await res.json()
      onSaved?.(data)
      setSuccess('Persona saved successfully.')
    } catch (e) {
      setError(e.message || 'Failed to save persona')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="panel persona-panel">
      <div className="persona-header">
        <h2 className="persona-title">Persona</h2>
        <p className="persona-subtitle">
          Customize how Memoria responds — tone, length, and style.
        </p>
      </div>

      <form
        className="persona-form"
        onSubmit={(e) => {
          e.preventDefault()
          save()
        }}
      >
        <label className="auth-label">
          Response Length
          <select value={form.response_length} onChange={updateField('response_length')}>
            <option value="concise">Concise</option>
            <option value="balanced">Balanced</option>
            <option value="detailed">Detailed</option>
          </select>
        </label>

        <label className="auth-label">
          Tone
          <select value={form.tone} onChange={updateField('tone')}>
            <option value="professional">Professional</option>
            <option value="friendly">Friendly</option>
            <option value="educational">Educational</option>
            <option value="witty">Witty</option>
            <option value="custom">Custom</option>
          </select>
        </label>

        {form.tone === 'custom' && (
          <label className="auth-label">
            Custom Tone
            <input
              value={form.custom_tone}
              onChange={updateField('custom_tone')}
              placeholder="Describe the tone you want"
              required
            />
          </label>
        )}

        <label className="auth-label">
          Behavior
          <select value={form.behavior} onChange={updateField('behavior')}>
            <option value="cautious">Cautious</option>
            <option value="encouraging">Encouraging</option>
            <option value="direct">Direct</option>
            <option value="custom">Custom</option>
          </select>
        </label>

        {form.behavior === 'custom' && (
          <label className="auth-label">
            Custom Behavior
            <input
              value={form.custom_behavior}
              onChange={updateField('custom_behavior')}
              placeholder="Describe how the AI should behave"
              required
            />
          </label>
        )}

        <button className="btn persona-save" type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </form>

      {success && <div className="success">{success}</div>}
      {error && <div className="error">{error}</div>}
    </div>
  )
}
