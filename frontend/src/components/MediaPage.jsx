import { useCallback, useEffect, useState } from 'react'

function mediaIcon(type) {
  if (type === 'image') return '🖼'
  if (type === 'video') return '▶'
  if (type === 'voice' || type === 'audio') return '🎙'
  return '●'
}

export default function MediaPage({ userId }) {
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lightbox, setLightbox] = useState(null)

  const loadAssets = useCallback(async () => {
    if (!userId) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch(
        `/api/generate/assets?user_id=${encodeURIComponent(userId)}`,
      )
      if (!res.ok) throw new Error(`Failed to load media (${res.status})`)
      const data = await res.json()
      setAssets(data.assets || [])
    } catch (e) {
      setError(e.message || 'Failed to load media')
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    loadAssets()
  }, [loadAssets])

  return (
    <div className="panel page-panel media-page">
      <div className="page-header">
        <h2 className="page-title">Media</h2>
        <p className="page-subtitle">
          Your generated images, videos, and audio — newest first.
        </p>
      </div>

      {loading && (
        <div className="page-loading">
          <span className="spinner spinner-inline" aria-hidden="true" />
          Loading media…
        </div>
      )}

      {!loading && error && <div className="error">{error}</div>}

      {!loading && !error && assets.length === 0 && (
        <div className="page-empty">
          No media yet. Use /imagine, /gen_video, or /gen_voice in chat.
        </div>
      )}

      {!loading && assets.length > 0 && (
        <div className="media-grid">
          {assets.map((asset) => (
            <button
              key={asset.id}
              type="button"
              className="media-card"
              onClick={() => setLightbox(asset)}
            >
              <div className="media-card-thumb">
                {asset.type === 'image' && asset.url ? (
                  <img src={asset.url} alt="" />
                ) : (
                  <span className="media-card-icon">{mediaIcon(asset.type)}</span>
                )}
              </div>
              <div className="media-card-meta">
                <span className="media-card-type">{asset.type}</span>
                <span className="media-card-prompt">{asset.prompt}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      {lightbox && (
        <div className="lightbox-backdrop" onClick={() => setLightbox(null)}>
          <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="lightbox-close"
              onClick={() => setLightbox(null)}
              aria-label="Close"
            >
              ×
            </button>
            {lightbox.type === 'image' && (
              <img src={lightbox.url} alt={lightbox.prompt} className="lightbox-media" />
            )}
            {lightbox.type === 'video' && (
              <video src={lightbox.url} controls autoPlay className="lightbox-media" />
            )}
            {(lightbox.type === 'voice' || lightbox.type === 'audio') && (
              <div className="lightbox-audio-wrap">
                <p>{lightbox.prompt}</p>
                <audio src={lightbox.url} controls autoPlay className="lightbox-audio" />
              </div>
            )}
            <p className="lightbox-caption">{lightbox.prompt}</p>
          </div>
        </div>
      )}
    </div>
  )
}
