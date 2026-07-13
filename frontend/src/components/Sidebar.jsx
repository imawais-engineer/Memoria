import { useState } from 'react'

const PI_TOOLTIP =
  'When enabled, I can access all your memories across chats. When disabled, I only see this session\'s context and essential facts.'

export default function Sidebar({
  sessions,
  activeSessionId,
  loading,
  globalMemoryEnabled,
  prefsSaving,
  isMemoryless,
  creatingChat,
  onSelect,
  onNewChat,
  onNewMemorylessChat,
  onDelete,
  onGlobalMemoryToggle,
}) {
  const [pendingDelete, setPendingDelete] = useState(null)
  const [pendingMemoryless, setPendingMemoryless] = useState(false)

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

  return (
    <aside className="sidebar">
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

      <label
        className={`pref-toggle sidebar-pi ${isMemoryless ? 'disabled' : ''}`}
        title={
          isMemoryless
            ? 'Personal Intelligence is unavailable during MemoryLess sessions'
            : PI_TOOLTIP
        }
      >
        <input
          type="checkbox"
          checked={globalMemoryEnabled}
          onChange={onGlobalMemoryToggle}
          disabled={prefsSaving || isMemoryless}
        />
        <span>Personal Intelligence</span>
      </label>

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
              <button
                type="button"
                className="sidebar-item-btn"
                onClick={() => onSelect(session.session_id)}
                title={session.title}
              >
                {session.is_memoryless && (
                  <span className="sidebar-icon" aria-hidden="true">
                    🕶️
                  </span>
                )}
                <span className="sidebar-item-title">{session.title}</span>
              </button>
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
