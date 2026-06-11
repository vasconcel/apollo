import { useState, useEffect } from 'react'
import { Brain, Save, Play, CheckCircle, XCircle, Clock } from 'lucide-react'

const API = '/api'

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API}${path}`, { credentials: 'include', ...options })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed (${res.status})`)
  }
  return res.json()
}

const PROVIDERS = [
  { value: 'ollama', label: 'Ollama (Local)' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'groq', label: 'Groq' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'other', label: 'Other (Custom / OpenAI-Compatible)' },
]

const PROVIDER_HINTS = {
  ollama: 'http://localhost:11434/v1',
  openai: 'https://api.openai.com/v1',
  groq: 'https://api.groq.com/openai/v1',
  gemini: 'https://generativelanguage.googleapis.com/v1beta/openai',
}

const PROVIDER_DEFAULT_MODELS = {
  ollama: 'qwen2.5:3b-instruct',
  groq: 'llama-3.1-8b-instant',
  openai: 'gpt-4o-mini',
  gemini: 'gemini-2.5-flash',
}

export default function LLMSettings() {
  const [provider, setProvider] = useState('ollama')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [delay, setDelay] = useState('0.0')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [saveMsg, setSaveMsg] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    (async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await apiFetch('/settings/llm')
        setProvider(data.llm_provider || 'ollama')
        setBaseUrl(data.llm_base_url || '')
        setModel(data.llm_model || '')
        setApiKey(data.llm_api_key || '')
        setDelay(data.llm_delay || '0.0')
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const PROVIDER_DELAYS = {
    ollama: '0',
    gemini: '4',
    groq: '2',
    openai: '0',
    other: '2',
  }

  const handleProviderChange = (e) => {
    const val = e.target.value
    setProvider(val)
    setDelay(PROVIDER_DELAYS[val] || '0')
    if (val === 'other') {
      setBaseUrl('')
      setModel('')
    } else {
      if (!baseUrl || Object.values(PROVIDER_HINTS).includes(baseUrl)) {
        setBaseUrl(PROVIDER_HINTS[val] || '')
      }
      if (!model || Object.values(PROVIDER_DEFAULT_MODELS).includes(model)) {
        setModel(PROVIDER_DEFAULT_MODELS[val] || model)
      }
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveMsg(null)
    try {
      await apiFetch('/settings/llm', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ llm_provider: provider, llm_base_url: baseUrl, llm_model: model, llm_api_key: apiKey, llm_delay: delay }),
      })
      setSaveMsg('Settings saved!')
    } catch (err) {
      setSaveMsg(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await apiFetch('/settings/llm/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ llm_provider: provider, llm_base_url: baseUrl, llm_model: model, llm_api_key: apiKey }),
      })
      setTestResult(result)
    } catch (err) {
      setTestResult({ success: false, message: err.message })
    } finally {
      setTesting(false)
    }
  }

  if (loading) {
    return (
      <div className="border border-zinc-800 bg-zinc-900/30 rounded-sm p-6 text-center text-zinc-500 text-xs">
        Loading LLM settings...
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

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
        <Brain className="w-4 h-4 text-cyan-400" />
        <span className="text-[11px] font-bold uppercase tracking-widest text-zinc-400">
          LLM Provider Configuration
        </span>
      </div>

      <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-4 space-y-4">
        {/* Provider */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Provider</label>
          <select
            value={provider}
            onChange={handleProviderChange}
            className="w-full bg-zinc-800/60 border border-zinc-700 px-2 py-1.5 text-xs text-zinc-200 rounded-sm outline-none focus:border-zinc-500 transition-colors"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        {/* Base URL */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Base URL</label>
          <input
            className="w-full bg-zinc-800/60 border border-zinc-700 px-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 rounded-sm outline-none focus:border-zinc-500 transition-colors font-mono"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={provider === 'other' ? 'https://your-api-endpoint.com/v1' : PROVIDER_HINTS[provider]}
          />
        </div>

        {/* Model */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Model</label>
          <input
            className="w-full bg-zinc-800/60 border border-zinc-700 px-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 rounded-sm outline-none focus:border-zinc-500 transition-colors font-mono"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="e.g. qwen2.5:7b, gpt-4o, llama3-70b"
          />
        </div>

        {/* API Key */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">API Key</label>
          <input
            className="w-full bg-zinc-800/60 border border-zinc-700 px-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 rounded-sm outline-none focus:border-zinc-500 transition-colors font-mono"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={provider === 'other' ? 'sk-... (API key for custom provider)' : 'sk-... (leave blank if using local Ollama)'}
          />
          <p className="text-[9px] text-zinc-600">Stored in the local database. Never shared.</p>
        </div>

        {/* Safety Delay */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Safety Delay (seconds)</label>
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
            <input
              type="number"
              step="0.1"
              min="0"
              className="w-full bg-zinc-800/60 border border-zinc-700 px-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 rounded-sm outline-none focus:border-zinc-500 transition-colors font-mono"
              value={delay}
              onChange={(e) => setDelay(e.target.value)}
              placeholder="0.0"
            />
          </div>
          <p className="text-[9px] text-zinc-600 leading-relaxed">
            Protects your API keys from rate-limiting (429) errors. Set to 0 for Ollama,
            17 for SambaNova Free, 4 for Gemini Free. If using paid tiers, set to 0.
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-zinc-700 text-[10px] font-bold tracking-wider uppercase text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-150"
          >
            <Save className="w-3 h-3" />
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button
            onClick={handleTest}
            disabled={testing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-cyan-800/60 text-[10px] font-bold tracking-wider uppercase text-cyan-400 hover:bg-cyan-950/30 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-150"
          >
            <Play className="w-3 h-3" />
            {testing ? 'Testing...' : 'Test Connection'}
          </button>
          {saveMsg && (
            <span className={`text-[10px] ${saveMsg === 'Settings saved!' ? 'text-emerald-400' : 'text-rose-400'}`}>
              {saveMsg}
            </span>
          )}
        </div>

        {/* Test Result */}
        {testResult && (
          <div className={`flex items-start gap-2 border px-3 py-2 rounded-sm text-xs ${
            testResult.success
              ? 'border-emerald-800/50 bg-emerald-950/20 text-emerald-400'
              : 'border-rose-800/50 bg-rose-950/20 text-rose-400'
          }`}>
            {testResult.success
              ? <CheckCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              : <XCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            }
            {testResult.message}
          </div>
        )}
      </div>
    </div>
  )
}
