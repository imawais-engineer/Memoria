import { useEffect, useState } from 'react'
import ModelDropdown from './ModelDropdown.jsx'

const DEFAULT_PERSONA = {
  response_length: 'balanced',
  tone: 'professional',
  behavior: 'cautious',
  custom_tone: '',
  custom_behavior: '',
}

export default function SettingsPage({
  userId,
  globalMemoryEnabled,
  defaultChatModel,
  persona,
  onSaved,
}) {
  const [models, setModels] = useState([])
  const [model, setModel] = useState(defaultChatModel || 'qwen-plus')
  const [piEnabled, setPiEnabled] = useState(globalMemoryEnabled ?? true)
  const [form, setForm] = useState(DEFAULT_PERSONA)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    async function loadModels() {
      try {
        const res = await fetch('/api/models')
        if (!res.ok) return
        setModels(await res.json())
      } catch {
        // optional
      }
    }
    loadModels()
  }, [])

  useEffect(() => {
    setModel(defaultChatModel || 'qwen-plus')
    setPiEnabled(globalMemoryEnabled ?? true)
    if (persona) {
      setForm({
        response_length: persona.response_length || 'balanced',
        tone: persona.tone || 'professional',
        behavior: persona.behavior || 'cautious',
        custom_tone: persona.custom_tone || '',
        custom_behavior: persona.custom_behavior || '',
      })
    }
  }, [defaultChatModel, globalMemoryEnabled, persona])

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
      const res = await fetch('/auth/preferences', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          global_memory_enabled: piEnabled,
          default_chat_model: model,
          persona: {
            response_length: form.response_length,
            tone: form.tone,
            behavior: form.behavior,
            custom_tone: form.tone === 'custom' ? form.custom_tone.trim() : null,
            custom_behavior:
              form.behavior === 'custom' ? form.custom_behavior.trim() : null,
          },
        }),
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
      setSuccess('Settings saved successfully.')
    } catch (e) {
      setError(e.message || 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const modelOptions = models.length
    ? models
    : [{ id: 'qwen-plus', name: 'Qwen Plus (balanced)' }]

  return (
    <div className="panel page-panel settings-page">
      <div className="page-header">
        <h2 className="page-title">Settings</h2>
        <p className="page-subtitle">
          Configure your default model, Personal Intelligence, and persona.
        </p>
      </div>

      <form
        className="page-form settings-form"
        onSubmit={(e) => {
          e.preventDefault()
          save()
        }}
      >
        <div className="settings-section">
          <h3 className="settings-section-title">Chat</h3>
          <label className="auth-label">
            Default chat model
            <ModelDropdown
              options={modelOptions}
              value={model}
              onChange={setModel}
              disabled={saving}
            />
          </label>

          <label className="settings-toggle-row">
            <span>Personal Intelligence default</span>
            <button
              type="button"
              className={`pi-switch-track ${piEnabled ? 'on' : 'off'}`}
              onClick={() => {
                setSuccess('')
                setPiEnabled((v) => !v)
              }}
              aria-pressed={piEnabled}
            >
              {piEnabled ? 'ON' : 'OFF'}
            </button>
          </label>
        </div>

        <div className="settings-section">
          <h3 className="settings-section-title">Persona</h3>

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
        </div>

        <button className="btn" type="submit" disabled={saving}>
          {saving ? (
            <span className="btn-loading">
              <span className="spinner" aria-hidden="true" />
              Saving…
            </span>
          ) : (
            'Save'
          )}
        </button>
      </form>

      {success && <div className="success">{success}</div>}
      {error && <div className="error">{error}</div>}
    </div>
  )
}
