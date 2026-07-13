import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'

const SCROLL_THRESHOLD_PX = 50

function normalizeAssistantMarkdown(content) {
  let text = content
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/&lt;br\s*\/?&gt;/gi, '\n')
    .replace(/,([dxyzdtuv])/g, ' \\,$1')

  // Qwen often uses LaTeX \( \) and \[ \] delimiters — convert for remark-math.
  text = text.replace(/\\\[([\s\S]+?)\\\]/g, (_, expr) => `$$\n${expr.trim()}\n$$`)
  text = text.replace(/\\\(([\s\S]+?)\\\)/g, (_, expr) => `$${expr.trim()}$`)

  // Qwen often wraps dollar math with spaces: "$ f(x) $" — remark-math needs tight delimiters.
  text = text.replace(/\$\$\s*([\s\S]+?)\s*\$\$/g, (_, expr) => `$$\n${expr.trim()}\n$$`)
  text = text.replace(
    /(^|[^$])\$\s+([^\n$]+?)\s+\$(?!\$)/g,
    (_, before, expr) => `${before}$${expr.trim()}$`,
  )

  return text
}

function isNearBottom(element) {
  return (
    element.scrollHeight - element.scrollTop - element.clientHeight <=
    SCROLL_THRESHOLD_PX
  )
}

export default function Chat({
  userId,
  sessionId,
  isPendingSession = false,
  isMemoryless = false,
  onSessionCreated,
}) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [error, setError] = useState('')
  const [showScrollDown, setShowScrollDown] = useState(false)
  const windowRef = useRef(null)
  const stickToBottomRef = useRef(true)

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    const element = windowRef.current
    if (!element) return
    element.scrollTo({ top: element.scrollHeight, behavior })
    stickToBottomRef.current = true
    setShowScrollDown(false)
  }, [])

  useEffect(() => {
    const element = windowRef.current
    if (!element) return undefined

    function handleScroll() {
      const atBottom = isNearBottom(element)
      stickToBottomRef.current = atBottom
      setShowScrollDown(!atBottom)
    }

    element.addEventListener('scroll', handleScroll, { passive: true })
    return () => element.removeEventListener('scroll', handleScroll)
  }, [])

  useEffect(() => {
    if (!sessionId || isPendingSession) {
      setMessages([])
      setLoadingHistory(false)
      stickToBottomRef.current = true
      setShowScrollDown(false)
      return
    }

    let cancelled = false
    async function loadHistory() {
      setLoadingHistory(true)
      setError('')
      stickToBottomRef.current = true
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
  }, [userId, sessionId, isPendingSession])

  useEffect(() => {
    if (!stickToBottomRef.current) return
    const element = windowRef.current
    if (!element) return
    element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' })
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
    stickToBottomRef.current = true
    setShowScrollDown(false)
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
          is_memoryless: isMemoryless,
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
      if (isPendingSession) {
        onSessionCreated?.(data.session_id, { isMemoryless })
      }
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
          MemoryLess Session – nothing will be remembered.
        </div>
      )}
      <div className="chat-window-wrap">
        <div className="chat-window" ref={windowRef}>
          {loadingHistory && (
            <div className="empty">
              <span className="spinner spinner-inline" aria-hidden="true" />
              Loading conversation…
            </div>
          )}
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
                      <ReactMarkdown
                        remarkPlugins={[
                          remarkGfm,
                          [
                            remarkMath,
                            {
                              inlineMath: [
                                ['$', '$'],
                                ['\\(', '\\)'],
                              ],
                              displayMath: [
                                ['$$', '$$'],
                                ['\\[', '\\]'],
                              ],
                            },
                          ],
                        ]}
                        rehypePlugins={[rehypeKatex]}
                      >
                        {normalizeAssistantMarkdown(m.content)}
                      </ReactMarkdown>
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
          {sending && (
            <div className="bubble assistant typing">
              <span className="spinner spinner-inline" aria-hidden="true" />
              Thinking…
            </div>
          )}
        </div>
        {showScrollDown && (
          <button
            type="button"
            className="scroll-to-bottom"
            onClick={() => scrollToBottom('smooth')}
            aria-label="Scroll to latest messages"
            title="Scroll to bottom"
          >
            ↓
          </button>
        )}
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
          {sending ? 'Sending…' : 'Send'}
        </button>
      </div>
      {error && <div className="error">{error}</div>}
    </div>
  )
}
