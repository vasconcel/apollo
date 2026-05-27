import { useState, useEffect } from 'react'
import { Settings, Save } from 'lucide-react'

const API = '/api'

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API}${path}`, { credentials: 'include', ...options })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed (${res.status})`)
  }
  return res.json()
}

function CriterionCard({ criterion, onSave }) {
  const [title, setTitle] = useState(criterion.title)
  const [description, setDescription] = useState(criterion.description)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)
  const hasChanges = title !== criterion.title || description !== criterion.description

  const handleSave = async () => {
    setSaving(true)
    setMsg(null)
    try {
      await apiFetch(`/criteria/${criterion.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description }),
      })
      setMsg('Saved!')
      onSave(criterion.id, title, description)
    } catch (err) {
      setMsg(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
          {criterion.id}
          {criterion.is_heuristic && (
            <span className="ml-2 text-fuchsia-500">[HEURISTIC]</span>
          )}
        </span>
        {msg && (
          <span className={`text-[10px] ${msg === 'Saved!' ? 'text-emerald-400' : 'text-rose-400'}`}>
            {msg}
          </span>
        )}
      </div>
      <input
        className="w-full bg-zinc-800/60 border border-zinc-700 px-2 py-1 text-xs text-zinc-200 placeholder-zinc-600 rounded-sm outline-none focus:border-zinc-500 transition-colors"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <textarea
        className="w-full bg-zinc-800/60 border border-zinc-700 px-2 py-1 text-xs text-zinc-200 placeholder-zinc-600 rounded-sm outline-none focus:border-zinc-500 transition-colors resize-y min-h-[60px]"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <button
        onClick={handleSave}
        disabled={!hasChanges || saving}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-zinc-700 text-[10px] font-bold tracking-wider uppercase text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-150"
      >
        <Save className="w-3 h-3" />
        {saving ? 'Saving...' : 'Save Changes'}
      </button>
    </div>
  )
}

export default function ProtocolSettings() {
  const [criteria, setCriteria] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    (async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await apiFetch('/criteria')
        setCriteria(data.items || [])
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const exclusionCriteria = criteria.filter((c) => c.type === 'EXCLUSION')
  const inclusionCriteria = criteria.filter((c) => c.type === 'INCLUSION')

  if (loading) {
    return (
      <div className="border border-zinc-800 bg-zinc-900/30 rounded-sm p-6 text-center text-zinc-500 text-xs">
        Loading criteria...
      </div>
    )
  }

  if (error) {
    return (
      <div className="border border-rose-800/50 bg-rose-950/20 rounded-sm p-6 text-center text-rose-400 text-xs">
        {error}
      </div>
    )
  }

  const handleSave = (id, title, description) => {
    setCriteria((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title, description } : c))
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
        <Settings className="w-4 h-4 text-cyan-400" />
        <span className="text-[11px] font-bold uppercase tracking-widest text-zinc-400">
          Protocol Criteria Configuration
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-2">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-rose-400 border-b border-zinc-800 pb-1">
            Exclusion Criteria (EC)
          </h3>
          {exclusionCriteria.map((c) => (
            <CriterionCard key={c.id} criterion={c} onSave={handleSave} />
          ))}
        </div>
        <div className="space-y-2">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-emerald-400 border-b border-zinc-800 pb-1">
            Inclusion Criteria (IC)
          </h3>
          {inclusionCriteria.map((c) => (
            <CriterionCard key={c.id} criterion={c} onSave={handleSave} />
          ))}
        </div>
      </div>
    </div>
  )
}
