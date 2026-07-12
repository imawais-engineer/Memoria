import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function Chat({ userId, sessionId, isMemoryless = false, onSessionUpdated }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [error, setError] = useState('')
  const windowRef = useRef(null)

  useEffect(() => {
    if (!sessionId) {
      setMessages([])
      return
    }

    let cancelled = false
    async function loadHistory() {
      setLoadingHistory(true)
      setError('')
      try {
        const res = await fetch(
          `/sessions/${encodeURIComponent(sessionId)}/history?user_id=${encodeURIComponent(userId)}`,
        )
        if (!res.ok) throw new Error(`Failed to load history (${res.status})`)
        const data = await res.json()
        if (!cancelled) {
          setMessages(
            data.map((item) => ({
              role: item.role,
              content: item.content,
              memory_ids: [],
              feedback: null,
            })),
          )
        }
      } catch (e) {
        if (!cancelled) {
          setMessages([])
          setError(e.message || 'Failed to load chat history')
        }
      } finally {
        if (!cancelled) setLoadingHistory(false)
      }
    }

    loadHistory()
    return () => {
      cancelled = true
    }
  }, [userId, sessionId])

  useEffect(() => {
    if (windowRef.current) {
      windowRef.current.scrollTop = windowRef.current.scrollHeight
    }
  }, [messages, sending, loadingHistory])

  async function sendFeedback(messageIndex, rating) {
    const message = messages[messageIndex]
    if (!message?.memory_ids?.length || message.feedback) return

    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          memory_ids: message.memory_ids,
          rating,
        }),
      })
      if (!res.ok) throw new Error(`Feedback failed (${res.status})`)
      setMessages((current) =>
        current.map((item, index) =>
          index === messageIndex ? { ...item, feedback: rating } : item,
        ),
      )
    } catch (e) {
      setError(e.message || 'Failed to submit feedback')
    }
  }

  async function send() {
    const text = input.trim()
    if (!text || sending || !sessionId) return
    setError('')
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: text }])
    setSending(true)
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          message: text,
          session_id: sessionId,
        }),
      })
      if (!res.ok) throw new Error(`Backend returned ${res.status}`)
      const data = await res.json()
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: data.reply,
          memory_ids: data.memory_ids || [],
          feedback: null,
        },
      ])
      onSessionUpdated?.()
    } catch (e) {
      setError(e.message || 'Failed to send message')
    } finally {
      setSending(false)
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="panel">
      {isMemoryless && (
        <div className="memoryless-banner">
          MemoryLess Session — no memories are read or stored.
        </div>
      )}
      <div className="chat-window" ref={windowRef}>
        {loadingHistory && <div className="empty">Loading conversation…</div>}
        {!loadingHistory && messages.length === 0 && !sending && (
          <div className="empty">Say hello — I&apos;ll remember what matters.</div>
        )}
        {!loadingHistory &&
          messages.map((m, i) => (
            <div
              key={i}
              className={`bubble-row ${m.role === 'user' ? 'user-row' : 'assistant-row'}`}
            >
              <div className={`bubble ${m.role}`}>
                {m.role === 'assistant' ? (
                  <div className="markdown-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                  </div>
                ) : (
                  m.content
                )}
              </div>
              {m.role === 'assistant' && m.memory_ids?.length > 0 && (
                <div className="feedback-buttons">
                  <button
                    type="button"
                    className={`feedback-btn ${m.feedback === 'positive' ? 'selected positive' : ''}`}
                    onClick={() => sendFeedback(i, 'positive')}
                    disabled={Boolean(m.feedback)}
                    title="Helpful response"
                    aria-label="Thumbs up"
                  >
                    👍
                  </button>
                  <button
                    type="button"
                    className={`feedback-btn ${m.feedback === 'negative' ? 'selected negative' : ''}`}
                    onClick={() => sendFeedback(i, 'negative')}
                    disabled={Boolean(m.feedback)}
                    title="Unhelpful response"
                    aria-label="Thumbs down"
                  >
                    👎
                  </button>
                </div>
              )}
            </div>
          ))}
        {sending && <div className="bubble assistant typing">Thinking…</div>}
      </div>

      <div className="composer">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Type a message…"
          disabled={sending || !sessionId}
        />
        <button className="btn" onClick={send} disabled={sending || !input.trim() || !sessionId}>
          Send
        </button>
      </div>
      {error && <div className="error">{error}</div>}
    </div>
  )
}
