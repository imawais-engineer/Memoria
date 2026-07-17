import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'

const SCROLL_THRESHOLD_PX = 50

const VOICE_STATUS_MESSAGES = [
  '🔄 Running voice generation…',
  '🔍 Analyzing session context…',
  '📝 Creating text overview…',
  '🎙️ Synthesizing voice…',
]

const MEDIA_COMMANDS = [
  { prefix: '/imagine', type: 'image', endpoint: '/api/generate/image' },
  { prefix: '/gen_video', type: 'video', endpoint: '/api/generate/video' },
  { prefix: '/gen_voice', type: 'voice', endpoint: '/api/generate/voice' },
]

function parseMediaCommand(text) {
  const trimmed = text.trim()
  for (const command of MEDIA_COMMANDS) {
    if (trimmed.startsWith(command.prefix)) {
      const prompt = trimmed.slice(command.prefix.length).trim()
      if (!prompt) return null
      return { ...command, prompt }
    }
  }
  return null
}

function normalizeAssistantMarkdown(content) {
  let text = content
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/&lt;br\s*\/?&gt;/gi, '\n')
    .replace(/,([dxyzdtuv])/g, ' \\,$1')

  text = text.replace(/\\\[([\s\S]+?)\\\]/g, (_, expr) => `$$\n${expr.trim()}\n$$`)
  text = text.replace(/\\\(([\s\S]+?)\\\)/g, (_, expr) => `$${expr.trim()}$`)
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

function MessageBody({ message }) {
  if (message.kind === 'image' && message.mediaUrl) {
    return (
      <div className="chat-media-block">
        <img src={message.mediaUrl} alt={message.prompt || 'Generated image'} className="chat-media" />
      </div>
    )
  }

  if (message.kind === 'video' && message.mediaUrl) {
    return (
      <div className="chat-media-block">
        <video src={message.mediaUrl} controls className="chat-media" />
      </div>
    )
  }

  if (message.kind === 'voice') {
    return (
      <div className="chat-voice-block">
        <div className="chat-voice-overview">{message.voiceOverview}</div>
        {message.audioSrc && <audio controls src={message.audioSrc} className="chat-audio" />}
      </div>
    )
  }

  if (message.role === 'assistant') {
    return (
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
          {normalizeAssistantMarkdown(message.content)}
        </ReactMarkdown>
      </div>
    )
  }

  return message.content
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
  const [selectedModel, setSelectedModel] = useState('qwen-plus')
  const [models, setModels] = useState([])
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
    let cancelled = false
    async function loadModels() {
      try {
        const res = await fetch('/api/models')
        if (!res.ok) return
        const data = await res.json()
        if (!cancelled) setModels(data)
      } catch {
        // model list is optional on load failure
      }
    }
    loadModels()
    return () => {
      cancelled = true
    }
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
              kind: 'text',
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

  async function sendMediaCommand(command) {
    const { type, prompt, endpoint } = command
    setMessages((current) => [...current, { role: 'user', content: `${command.prefix} ${prompt}`, kind: 'text' }])

    if (type === 'voice') {
      const statusMessages = VOICE_STATUS_MESSAGES.map((content) => ({
        role: 'assistant',
        content,
        kind: 'voice-status',
      }))
      setMessages((current) => [...current, ...statusMessages])

      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            session_id: sessionId,
            prompt,
          }),
        })

        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || `Voice generation failed (${res.status})`)
        }

        const data = await res.json()
        setMessages((current) => {
          const withoutStatus = current.filter((item) => item.kind !== 'voice-status')
          return [
            ...withoutStatus,
            {
              role: 'assistant',
              content: '',
              kind: 'voice',
              voiceOverview: data.overview_text,
              audioSrc: data.audio_data_uri,
            },
          ]
        })
      } catch (e) {
        setMessages((current) => current.filter((item) => item.kind !== 'voice-status'))
        setError(e.message || 'Voice generation failed')
      }
      return
    }

    setSending(true)
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, prompt }),
      })

      if (res.status === 429) {
        setError(type === 'image' ? 'Image generation limit reached (5 max).' : 'Video generation limit reached (2 max).')
        return
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Generation failed (${res.status})`)
      }

      const data = await res.json()
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: '',
          kind: type,
          mediaUrl: data.url,
          prompt,
        },
      ])
    } catch (e) {
      setError(e.message || 'Generation failed')
    } finally {
      setSending(false)
    }
  }

  async function sendChatMessage(text) {
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
          model: selectedModel,
        }),
      })
      if (!res.ok) throw new Error(`Backend returned ${res.status}`)
      const data = await res.json()
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: data.reply,
          kind: 'text',
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

  async function send() {
    const text = input.trim()
    if (!text || sending || !sessionId) return
    setError('')
    setInput('')
    stickToBottomRef.current = true
    setShowScrollDown(false)

    const mediaCommand = parseMediaCommand(text)
    if (mediaCommand) {
      setSending(true)
      try {
        await sendMediaCommand(mediaCommand)
      } finally {
        setSending(false)
      }
      return
    }

    setMessages((m) => [...m, { role: 'user', content: text, kind: 'text' }])
    await sendChatMessage(text)
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
      <div className="chat-hints">
        Try <code>/imagine</code>, <code>/gen_video</code>, or <code>/gen_voice</code> followed by a prompt.
      </div>
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
                <div className={`bubble ${m.role}${m.kind === 'voice' ? ' voice-bubble' : ''}`}>
                  <MessageBody message={m} />
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
          {sending && !messages.some((m) => m.kind === 'voice-status') && (
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
        <select
          className="model-select"
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          disabled={sending}
          aria-label="Chat model"
          title="Chat model"
        >
          {(models.length ? models : [{ id: 'qwen-plus', name: 'Qwen Plus (balanced)' }]).map(
            (model) => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ),
          )}
        </select>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Type a message or /imagine, /gen_video, /gen_voice…"
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
