import { useCallback, useEffect, useState } from 'react'

const IMAGE_SIZES = ['1024x1024', '768x768', '512x512']
const VIDEO_DURATIONS = [5, 8, 10]

export default function CreatePanel({ userId }) {
  const [mode, setMode] = useState('image')
  const [prompt, setPrompt] = useState('')
  const [size, setSize] = useState('1024x1024')
  const [duration, setDuration] = useState(5)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [latestResult, setLatestResult] = useState(null)
  const [usage, setUsage] = useState(null)
  const [assets, setAssets] = useState([])
  const [loadingGallery, setLoadingGallery] = useState(true)

  const loadAssets = useCallback(async () => {
    if (!userId) return
    setLoadingGallery(true)
    try {
      const res = await fetch(`/api/generate/assets?user_id=${encodeURIComponent(userId)}`)
      if (!res.ok) throw new Error(`Failed to load assets (${res.status})`)
      const data = await res.json()
      setUsage(data.usage)
      setAssets(data.assets || [])
    } catch (e) {
      setError(e.message || 'Could not load gallery')
    } finally {
      setLoadingGallery(false)
    }
  }, [userId])

  useEffect(() => {
    loadAssets()
  }, [loadAssets])

  async function handleGenerate(e) {
    e.preventDefault()
    const text = prompt.trim()
    if (!text || generating) return

    setError('')
    setGenerating(true)
    setLatestResult(null)

    const endpoint = mode === 'image' ? '/api/generate/image' : '/api/generate/video'
    const body =
      mode === 'image'
        ? { user_id: userId, prompt: text, size }
        : { user_id: userId, prompt: text, duration }

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (res.status === 429) {
        setError('Limit reached')
        await loadAssets()
        return
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Generation failed (${res.status})`)
      }

      const data = await res.json()
      setLatestResult({ type: mode, url: data.url, prompt: text })
      setPrompt('')
      await loadAssets()
    } catch (e) {
      setError(e.message || 'Generation failed')
    } finally {
      setGenerating(false)
    }
  }

  const imagesRemaining = usage ? usage.images_remaining : '—'
  const videosRemaining = usage ? usage.videos_remaining : '—'
  const maxImages = usage?.max_images ?? 5
  const maxVideos = usage?.max_videos ?? 2

  return (
    <div className="panel create-panel">
      <div className="create-header">
        <h2 className="create-title">Create with Qwen</h2>
        <p className="create-subtitle">
          Generate images and videos with DashScope — usage limits apply per account.
        </p>
      </div>

      <div className="create-subtabs">
        <button
          type="button"
          className={`tab ${mode === 'image' ? 'active' : ''}`}
          onClick={() => {
            setMode('image')
            setError('')
          }}
        >
          Image
        </button>
        <button
          type="button"
          className={`tab ${mode === 'video' ? 'active' : ''}`}
          onClick={() => {
            setMode('video')
            setError('')
          }}
        >
          Video
        </button>
      </div>

      <div className="create-quota">
        {mode === 'image' ? (
          <span>
            <strong>{imagesRemaining}</strong>/{maxImages} images left
          </span>
        ) : (
          <span>
            <strong>{videosRemaining}</strong>/{maxVideos} videos left
          </span>
        )}
      </div>

      <form className="create-form" onSubmit={handleGenerate}>
        <label className="auth-label">
          Prompt
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={
              mode === 'image'
                ? 'A futuristic neural network glowing in purple and cyan…'
                : 'A calm ocean at sunset with gentle waves…'
            }
            rows={3}
            required
          />
        </label>

        {mode === 'image' ? (
          <label className="auth-label">
            Size
            <select value={size} onChange={(e) => setSize(e.target.value)}>
              {IMAGE_SIZES.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label className="auth-label">
            Duration (seconds)
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            >
              {VIDEO_DURATIONS.map((option) => (
                <option key={option} value={option}>
                  {option}s
                </option>
              ))}
            </select>
          </label>
        )}

        <button className="btn create-submit" type="submit" disabled={generating || !prompt.trim()}>
          {generating ? (
            <span className="btn-loading">
              <span className="spinner" aria-hidden="true" />
              Generating…
            </span>
          ) : (
            `Generate ${mode === 'image' ? 'Image' : 'Video'}`
          )}
        </button>
      </form>

      {error && <div className="error create-error">{error}</div>}

      {latestResult && (
        <div className="create-result">
          <h3>Latest result</h3>
          <p className="create-result-prompt">{latestResult.prompt}</p>
          {latestResult.type === 'image' ? (
            <img src={latestResult.url} alt={latestResult.prompt} className="create-media" />
          ) : (
            <video src={latestResult.url} controls className="create-media" />
          )}
        </div>
      )}

      <div className="create-gallery">
        <div className="create-gallery-header">
          <h3>Your gallery</h3>
          <button type="button" className="btn btn-secondary" onClick={loadAssets} disabled={loadingGallery}>
            Refresh
          </button>
        </div>

        {loadingGallery && (
          <div className="empty">
            <span className="spinner spinner-inline" aria-hidden="true" />
            Loading gallery…
          </div>
        )}

        {!loadingGallery && assets.length === 0 && (
          <div className="empty">No generated assets yet — create your first one above.</div>
        )}

        {!loadingGallery && assets.length > 0 && (
          <div className="create-gallery-grid">
            {assets.map((asset) => (
              <article key={asset.id} className="create-gallery-item">
                {asset.type === 'image' ? (
                  <img src={asset.url} alt={asset.prompt} loading="lazy" />
                ) : (
                  <video src={asset.url} controls preload="metadata" />
                )}
                <div className="create-gallery-meta">
                  <span className="create-gallery-type">{asset.type}</span>
                  <p>{asset.prompt}</p>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
