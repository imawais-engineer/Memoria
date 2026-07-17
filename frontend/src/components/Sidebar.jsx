import { useEffect, useRef, useState } from 'react'

function truncate(text, max = 42) {
  const value = (text || '').trim()
  if (!value) return 'Untitled'
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}

function mediaIcon(type) {
  if (type === 'image') return '🖼'
  if (type === 'video') return '▶'
  if (type === 'voice' || type === 'audio') return '🎙'
  return '●'
}

export default function Sidebar({
  userId,
  username,
  displayName,
  sessions,
  activeSessionId,
  activeView,
  loading,
  creatingChat,
  open,
  onSelect,
  onNewChat,
  onNavigate,
  onDelete,
  onRename,
  onOpenMedia,
  onLogout,
}) {
  const [pendingDelete, setPendingDelete] = useState(null)
  const [editingSessionId, setEditingSessionId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [savingTitle, setSavingTitle] = useState(false)
  const [menuSessionId, setMenuSessionId] = useState(null)
  const [mediaOpen, setMediaOpen] = useState(true)
  const [assets, setAssets] = useState([])
  const [assetsLoading, setAssetsLoading] = useState(false)
  const editInputRef = useRef(null)

  const recentSessions = sessions.filter((session) => !session.is_memoryless)
  const avatarLetter = (username || displayName || 'U').charAt(0).toUpperCase()

  useEffect(() => {
    if (editingSessionId && editInputRef.current) {
      editInputRef.current.focus()
      editInputRef.current.select()
    }
  }, [editingSessionId])

  useEffect(() => {
    if (!userId || !open) return undefined

    let cancelled = false
    async function loadAssets() {
      setAssetsLoading(true)
      try {
        const res = await fetch(
          `/api/generate/assets?user_id=${encodeURIComponent(userId)}`,
        )
        if (!res.ok) return
        const data = await res.json()
        if (!cancelled) setAssets(data.assets || [])
      } catch {
        // media list is optional
      } finally {
        if (!cancelled) setAssetsLoading(false)
      }
    }

    loadAssets()
    return () => {
      cancelled = true
    }
  }, [userId, open, sessions.length])

  useEffect(() => {
    function closeMenus(e) {
      if (!e.target.closest?.('.sidebar-chat-menu-wrap')) {
        setMenuSessionId(null)
      }
    }
    document.addEventListener('click', closeMenus)
    return () => document.removeEventListener('click', closeMenus)
  }, [])

  function confirmDelete() {
    if (pendingDelete) {
      onDelete(pendingDelete)
      setPendingDelete(null)
    }
  }

  function startEditing(session) {
    setMenuSessionId(null)
    setEditingSessionId(session.session_id)
    setEditTitle(session.title)
  }

  function cancelEditing() {
    setEditingSessionId(null)
    setEditTitle('')
  }

  async function saveTitle(sessionId) {
    const nextTitle = editTitle.trim()
    if (!nextTitle || savingTitle) {
      cancelEditing()
      return
    }
    setSavingTitle(true)
    try {
      const res = await fetch(
        `/sessions/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(userId)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: nextTitle }),
        },
      )
      if (!res.ok) throw new Error(`Rename failed (${res.status})`)
      const data = await res.json()
      onRename?.(sessionId, data.title)
      cancelEditing()
    } catch {
      cancelEditing()
    } finally {
      setSavingTitle(false)
    }
  }

  return (
    <aside className={`sidebar${open ? '' : ' sidebar--closed'}`} aria-hidden={!open}>
      <div className="sidebar-inner">
        <div className="sidebar-brand">
          <div className="sidebar-brand-name">Memoria</div>
          <div className="sidebar-brand-tagline">Personal AI with long-term memory</div>
        </div>

        <button
          type="button"
          className="sidebar-new-btn"
          onClick={onNewChat}
          disabled={creatingChat}
        >
          {creatingChat ? (
            <span className="btn-loading">
              <span className="spinner" aria-hidden="true" />
              Starting…
            </span>
          ) : (
            '+ New Chat'
          )}
        </button>

        <nav className="sidebar-nav" aria-label="Main">
          <button
            type="button"
            className={`sidebar-nav-link${activeView === 'memory' ? ' active' : ''}`}
            onClick={() => onNavigate('memory')}
          >
            Memories
          </button>
          <button
            type="button"
            className={`sidebar-nav-link${activeView === 'persona' ? ' active' : ''}`}
            onClick={() => onNavigate('persona')}
          >
            Persona
          </button>
        </nav>

        <div className="sidebar-section">
          <button
            type="button"
            className="sidebar-section-toggle"
            onClick={() => setMediaOpen((openState) => !openState)}
            aria-expanded={mediaOpen}
          >
            Media
            <span className="sidebar-section-chevron">{mediaOpen ? '▾' : '▸'}</span>
          </button>
          {mediaOpen && (
            <div className="sidebar-media-list">
              {assetsLoading && <div className="sidebar-empty">Loading…</div>}
              {!assetsLoading && assets.length === 0 && (
                <div className="sidebar-empty">No media yet</div>
              )}
              {!assetsLoading &&
                assets.slice(0, 12).map((asset) => (
                  <button
                    key={asset.id}
                    type="button"
                    className="sidebar-media-item"
                    onClick={() => onOpenMedia?.(asset)}
                    title={asset.prompt}
                  >
                    <span className="sidebar-media-thumb">
                      {asset.type === 'image' && asset.url ? (
                        <img src={asset.url} alt="" />
                      ) : (
                        mediaIcon(asset.type)
                      )}
                    </span>
                    <span className="sidebar-media-title">{truncate(asset.prompt, 36)}</span>
                  </button>
                ))}
            </div>
          )}
        </div>

        <div className="sidebar-section" style={{ flex: 1, minHeight: 0 }}>
          <div className="sidebar-section-toggle" style={{ cursor: 'default' }}>
            Recent Chats
          </div>
          <div className="sidebar-chat-list">
            {loading && (
              <div className="sidebar-empty">
                <span className="spinner spinner-inline" aria-hidden="true" /> Loading…
              </div>
            )}
            {!loading && recentSessions.length === 0 && (
              <div className="sidebar-empty">No chats yet</div>
            )}
            {!loading &&
              recentSessions.map((session) => (
                <div
                  key={session.session_id}
                  className={`sidebar-chat-item${
                    session.session_id === activeSessionId && activeView === 'chat'
                      ? ' active'
                      : ''
                  }${menuSessionId === session.session_id ? ' menu-open' : ''}`}
                >
                  {editingSessionId === session.session_id ? (
                    <input
                      ref={editInputRef}
                      className="sidebar-title-input"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          saveTitle(session.session_id)
                        }
                        if (e.key === 'Escape') {
                          e.preventDefault()
                          cancelEditing()
                        }
                      }}
                      onBlur={() => saveTitle(session.session_id)}
                      disabled={savingTitle}
                    />
                  ) : (
                    <>
                      <button
                        type="button"
                        className="sidebar-chat-btn"
                        onClick={() => onSelect(session.session_id)}
                        title={session.title}
                      >
                        <span className="sidebar-chat-title">{session.title}</span>
                      </button>
                      <div className="sidebar-chat-menu-wrap">
                        <button
                          type="button"
                          className="sidebar-chat-menu-btn"
                          aria-label="Chat options"
                          onClick={(e) => {
                            e.stopPropagation()
                            setMenuSessionId((current) =>
                              current === session.session_id ? null : session.session_id,
                            )
                          }}
                        >
                          …
                        </button>
                        {menuSessionId === session.session_id && (
                          <div className="sidebar-chat-menu">
                            <button type="button" onClick={() => startEditing(session)}>
                              Rename
                            </button>
                            <button
                              type="button"
                              className="danger"
                              onClick={() => {
                                setMenuSessionId(null)
                                setPendingDelete(session.session_id)
                              }}
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              ))}
          </div>
        </div>

        <div className="sidebar-profile">
          <div className="sidebar-avatar" aria-hidden="true">
            {avatarLetter}
          </div>
          <div className="sidebar-profile-meta">
            <div className="sidebar-profile-user">@{username}</div>
            <div className="sidebar-profile-name">{displayName || username}</div>
          </div>
          <button type="button" className="sidebar-logout" onClick={onLogout}>
            Logout
          </button>
        </div>
      </div>

      {pendingDelete && (
        <div className="modal-backdrop" onClick={() => setPendingDelete(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">Delete chat?</h3>
            <p className="modal-text">
              This will permanently delete the chat and all memories extracted from it.
            </p>
            <div className="modal-actions">
              <button
                type="button"
                className="modal-btn cancel"
                onClick={() => setPendingDelete(null)}
              >
                Cancel
              </button>
              <button type="button" className="modal-btn danger" onClick={confirmDelete}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
