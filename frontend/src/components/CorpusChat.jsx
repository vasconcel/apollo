import { useState, useRef, useEffect } from 'react'
import { MessageSquare, Send, Loader2, BookOpen } from 'lucide-react'

const API = '/api'

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    credentials: 'include',
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const msg = body.detail || `Request failed (${res.status})`
    throw new Error(msg)
  }
  return res.json()
}

function MarkdownBlock({ text }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return (
    <span className="whitespace-pre-wrap break-words leading-relaxed">
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i} className="text-cyan-300">{part.slice(2, -2)}</strong>
        }
        return <span key={i}>{part}</span>
      })}
    </span>
  )
}

export default function CorpusChat({ progressData }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)

  const includedCount = progressData?.included_count ?? 0

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend() {
    const msg = input.trim()
    if (!msg || loading) return

    setInput('')
    setError(null)

    const history = messages.map((m) => ({ role: m.role, content: m.content }))

    setMessages((prev) => [...prev, { role: 'user', content: msg }])
    setLoading(true)

    try {
      const data = await apiFetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, history }),
      })
      setMessages((prev) => [...prev, { role: 'assistant', content: data.response }])
    } catch (err) {
      setError(err.message)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `[Error] ${err.message}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (includedCount === 0) {
    return (
      <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-8 flex flex-col items-center justify-center gap-4 min-h-[300px]">
        <MessageSquare className="w-10 h-10 text-zinc-600" />
        <p className="text-xs text-zinc-500 text-center leading-relaxed max-w-md">
          No included papers found. Please complete some manual reviews or run the
          screening and approve papers first to enable the Corpus Chatbot.
        </p>
      </div>
    )
  }

  return (
    <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm flex flex-col min-h-[500px]">
      {/* Header */}
      <div className="border-b border-zinc-800 px-4 py-3 flex items-center gap-2">
        <BookOpen className="w-4 h-4 text-cyan-400 drop-shadow-[0_0_4px_#22d3ee]" />
        <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">
          Chatting with {includedCount} included paper{includedCount !== 1 ? 's' : ''}
          <span className="text-zinc-600 font-normal lowercase">
            {' '}(Abstracts & Full-Text PDFs loaded)
          </span>
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 max-h-[400px]">
        {messages.length === 0 && !loading && (
          <p className="text-[11px] text-zinc-600 text-center pt-12">
            Ask a question about your included corpus…
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-glide-in`}
          >
            <div
              className={`max-w-[80%] rounded-sm px-4 py-2.5 text-[12px] ${
                m.role === 'user'
                  ? 'bg-slate-800 text-zinc-200 border border-slate-700'
                  : 'bg-zinc-900/50 text-zinc-300 border border-zinc-800'
              }`}
            >
              <MarkdownBlock text={m.content} />
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start animate-glide-in">
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-sm px-4 py-2.5 text-[12px] text-zinc-400">
              <div className="flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                <span>APOLLO is reading the corpus…</span>
              </div>
            </div>
          </div>
        )}
        {error && (
          <div className="flex justify-center">
            <div className="border border-rose-800/50 bg-rose-950/20 px-4 py-2 text-[11px] text-rose-400 rounded-sm">
              {error}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-zinc-800 px-4 py-3">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            placeholder="Type your question about the corpus…"
            className="flex-1 bg-zinc-950 border border-zinc-700 rounded-sm px-3 py-2 text-xs text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-cyan-700 focus:ring-1 focus:ring-cyan-700/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="inline-flex items-center gap-1.5 px-4 py-2 border-2 border-cyan-800/60 text-cyan-400 hover:bg-cyan-950/30 hover:shadow-neon-cyan disabled:border-zinc-700 disabled:text-zinc-600 disabled:cursor-not-allowed text-xs font-bold tracking-wider transition-all duration-200"
          >
            {loading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
            SEND
          </button>
        </div>
      </div>
    </div>
  )
}
