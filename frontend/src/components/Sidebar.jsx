import { useEffect, useRef, useState } from 'react'

export default function Sidebar({
  userId,
  sessions,
  activeSessionId,
  loading,
  creatingChat,
  open,
  onSelect,
  onNewChat,
  onNewMemorylessChat,
  onDelete,
  onRename,
}) {
  const [pendingDelete, setPendingDelete] = useState(null)
  const [pendingMemoryless, setPendingMemoryless] = useState(false)
  const [editingSessionId, setEditingSessionId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [savingTitle, setSavingTitle] = useState(false)
  const editInputRef = useRef(null)

  useEffect(() => {
    if (editingSessionId && editInputRef.current) {
      editInputRef.current.focus()
      editInputRef.current.select()
    }
  }, [editingSessionId])

  function confirmDelete() {
    if (pendingDelete) {
      onDelete(pendingDelete)
      setPendingDelete(null)
    }
  }

  function confirmMemoryless() {
    setPendingMemoryless(false)
    onNewMemorylessChat()
  }

  function startEditing(session) {
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
        <div className="sidebar-new-row">
          <button
            type="button"
            className="btn sidebar-new"
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
          <button
            type="button"
            className="btn sidebar-new sidebar-memoryless-btn"
            onClick={() => setPendingMemoryless(true)}
            disabled={creatingChat}
            title="Start a private chat with no memory storage"
          >
            🕶️ Memoryless
          </button>
        </div>

        <div className="sidebar-list">
          {loading && (
            <div className="sidebar-empty">
              <span className="spinner spinner-inline" aria-hidden="true" />
              Loading chats…
            </div>
          )}
          {!loading && sessions.length === 0 && (
            <div className="sidebar-empty">No chats yet</div>
          )}
          {!loading &&
            sessions.map((session) => (
              <div
                key={session.session_id}
                className={`sidebar-item ${session.session_id === activeSessionId ? 'active' : ''} ${session.is_memoryless ? 'memoryless' : ''}`}
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
                  <button
                    type="button"
                    className="sidebar-item-btn"
                    onClick={() => onSelect(session.session_id)}
                    onDoubleClick={() => startEditing(session)}
                    title={`${session.title} (double-click to rename)`}
                  >
                    {session.is_memoryless && (
                      <span className="sidebar-icon" aria-hidden="true">
                        🕶️
                      </span>
                    )}
                    <span className="sidebar-item-title">{session.title}</span>
                  </button>
                )}
                <button
                  type="button"
                  className="sidebar-delete"
                  onClick={() => setPendingDelete(session.session_id)}
                  aria-label={`Delete ${session.title}`}
                  title="Delete chat"
                >
                  ×
                </button>
              </div>
            ))}
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

      {pendingMemoryless && (
        <div className="modal-backdrop" onClick={() => setPendingMemoryless(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">Start MemoryLess session?</h3>
            <p className="modal-text">
              This session will not use or store any memories. Your conversation will be
              completely private and won&apos;t be remembered.
            </p>
            <div className="modal-actions">
              <button
                type="button"
                className="modal-btn cancel"
                onClick={() => setPendingMemoryless(false)}
              >
                Cancel
              </button>
              <button type="button" className="modal-btn danger" onClick={confirmMemoryless}>
                Start private chat
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
