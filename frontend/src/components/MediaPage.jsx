import { useCallback, useEffect, useState } from 'react'
import { DEMO_TOKEN } from '../App.jsx'
import { MediaTypeIcon } from './Icons.jsx'

function extensionForAsset(asset) {
  if (asset.url?.startsWith('data:')) {
    const mime = asset.url.slice(5, asset.url.indexOf(';'))
    if (mime.includes('png')) return 'png'
    if (mime.includes('jpeg') || mime.includes('jpg')) return 'jpg'
    if (mime.includes('webp')) return 'webp'
    if (mime.includes('mp4')) return 'mp4'
    if (mime.includes('mpeg') || mime.includes('mp3')) return 'mp3'
    if (mime.includes('wav')) return 'wav'
    return 'bin'
  }
  try {
    const pathname = new URL(asset.url).pathname
    const dot = pathname.lastIndexOf('.')
    if (dot !== -1) return pathname.slice(dot + 1).split('?')[0] || 'bin'
  } catch {
    // ignore invalid URLs
  }
  if (asset.type === 'video') return 'mp4'
  if (asset.type === 'voice' || asset.type === 'audio') return 'mp3'
  return 'png'
}

async function downloadAsset(asset) {
  const ext = extensionForAsset(asset)
  const filename = `memoria-${asset.type}-${asset.id.slice(0, 8)}.${ext}`

  if (asset.url?.startsWith('data:')) {
    const link = document.createElement('a')
    link.href = asset.url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    return
  }

  const res = await fetch(asset.url)
  if (!res.ok) throw new Error(`Download failed (${res.status})`)
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}

export default function MediaPage({ userId }) {
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lightbox, setLightbox] = useState(null)
  const [menuAssetId, setMenuAssetId] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)

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

  useEffect(() => {
    function closeMenus(e) {
      if (!e.target.closest?.('.media-card-menu-wrap')) {
        setMenuAssetId(null)
      }
    }
    document.addEventListener('click', closeMenus)
    return () => document.removeEventListener('click', closeMenus)
  }, [])

  async function handleDownload(asset) {
    setMenuAssetId(null)
    setError('')
    setActionLoading(true)
    try {
      await downloadAsset(asset)
    } catch (e) {
      setError(e.message || 'Failed to download media')
    } finally {
      setActionLoading(false)
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return
    setActionLoading(true)
    setError('')
    try {
      const res = await fetch(
        `/api/generate/assets/${encodeURIComponent(pendingDelete.id)}?user_id=${encodeURIComponent(userId)}`,
        {
          method: 'DELETE',
          headers: { 'X-API-Token': DEMO_TOKEN },
        },
      )
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Delete failed (${res.status})`)
      }
      setAssets((current) => current.filter((item) => item.id !== pendingDelete.id))
      if (lightbox?.id === pendingDelete.id) setLightbox(null)
      setPendingDelete(null)
    } catch (e) {
      setError(e.message || 'Failed to delete media')
    } finally {
      setActionLoading(false)
    }
  }

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
            <div key={asset.id} className="media-card-wrap">
              <button
                type="button"
                className="media-card"
                onClick={() => setLightbox(asset)}
              >
                <div className="media-card-thumb">
                  {asset.type === 'image' && asset.url ? (
                    <img src={asset.url} alt="" />
                  ) : (asset.type === 'voice' || asset.type === 'audio') && asset.url ? (
                    <audio
                      src={asset.url}
                      controls
                      className="media-card-audio"
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : asset.type === 'video' && asset.url ? (
                    <video src={asset.url} muted playsInline className="media-card-video" />
                  ) : (
                    <span className="media-card-icon">
                      <MediaTypeIcon type={asset.type} />
                    </span>
                  )}
                </div>
                <div className="media-card-meta">
                  <span className="media-card-type">{asset.type}</span>
                  <span className="media-card-prompt">{asset.prompt}</span>
                </div>
              </button>

              <div className="media-card-menu-wrap">
                <button
                  type="button"
                  className="media-card-menu-btn"
                  aria-label="Media options"
                  disabled={actionLoading}
                  onClick={(e) => {
                    e.stopPropagation()
                    setMenuAssetId((current) => (current === asset.id ? null : asset.id))
                  }}
                >
                  …
                </button>
                {menuAssetId === asset.id && (
                  <div className="media-card-menu">
                    <button type="button" onClick={() => handleDownload(asset)}>
                      Download
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        setMenuAssetId(null)
                        setPendingDelete(asset)
                      }}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
            </div>
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

      {pendingDelete && (
        <div className="modal-backdrop" onClick={() => setPendingDelete(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">Delete media?</h3>
            <p className="modal-text">
              This will permanently remove this {pendingDelete.type} from your profile
              and app storage. This change is irreversible.
            </p>
            <div className="modal-actions">
              <button
                type="button"
                className="modal-btn cancel"
                onClick={() => setPendingDelete(null)}
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button
                type="button"
                className="modal-btn danger"
                onClick={confirmDelete}
                disabled={actionLoading}
              >
                {actionLoading ? 'Deleting…' : 'Delete permanently'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
