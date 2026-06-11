import { useState, useEffect, useCallback, useRef } from 'react'
import { Terminal, Download, Trash2, ShieldAlert, Settings, MessageSquare, Brain } from 'lucide-react'
import UploadZone from './components/UploadZone'
import ProgressCard from './components/ProgressCard'
import PaperTable from './components/PaperTable'
import PrismaFlowchart from './components/PrismaFlowchart'
import AccuracyAudit from './components/AccuracyAudit'
import ProtocolSettings from './components/ProtocolSettings'
import LLMSettings from './components/LLMSettings'
import CorpusChat from './components/CorpusChat'

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
  return options?.blob ? res : res.json()
}

export default function App() {
  const [papers, setPapers] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [size] = useState(20)
  const [statusFilter, setStatusFilter] = useState(null)
  const [literatureType, setLiteratureType] = useState('ALL')
  const [loadingPapers, setLoadingPapers] = useState(false)

  const [viewTab, setViewTab] = useState('explorer')
  const [filters, setFilters] = useState({})

  const [importMsg, setImportMsg] = useState(null)
  const [importError, setImportError] = useState(null)

  const [screeningActive, setScreeningActive] = useState(false)
  const [progress, setProgress] = useState(null)
  const [screenStarted, setScreenStarted] = useState(false)
  const [calibrationBanner, setCalibrationBanner] = useState(false)

  const pollingIntervalRef = useRef(null)
  const fetchPapersRef = useRef(null)

  const fetchProgress = useCallback(async () => {
    try {
      const p = await apiFetch('/screening/progress')
      setProgress(p)
      if (p.is_active) {
        setScreeningActive(true)
        setScreenStarted(true)
      }
      if (p.in_calibration && !p.is_active && p.screened_count === p.total_papers && p.total_papers > 0) {
        setCalibrationBanner(true)
      }
      return p
    } catch { /* backend may not be ready */ }
  }, [])

  const fetchPapers = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoadingPapers(true)
    try {
      const params = new URLSearchParams({ page, size })
      if (statusFilter) params.set('status', statusFilter)
      if (literatureType !== 'ALL') params.set('source_type', literatureType)
      if (filters.search) params.set('search', filters.search)
      if (filters.title_contains) params.set('title_contains', filters.title_contains)
      if (filters.abstract_contains) params.set('abstract_contains', filters.abstract_contains)
      if (filters.year_from) params.set('year_from', filters.year_from)
      if (filters.year_to) params.set('year_to', filters.year_to)
      const data = await apiFetch(`/papers?${params}`)
      setPapers(data.items)
      setTotal(data.total)
    } catch {
      /* backend may not be ready */
    } finally {
      if (!isSilent) setLoadingPapers(false)
    }
  }, [page, size, statusFilter, literatureType, filters])

  fetchPapersRef.current = fetchPapers

  const handleProgressUpdate = useCallback((p) => {
    setProgress(p)
    if (p.in_calibration && !p.is_active && p.screened_count === p.total_papers && p.total_papers > 0) {
      setCalibrationBanner(true)
    }
    if (!p.is_active) {
      setScreeningActive(false)
      fetchPapersRef.current?.(true)
    }
  }, [])

  useEffect(() => {
    fetchPapers()
  }, [fetchPapers])

  useEffect(() => {
    fetchProgress()
  }, [fetchProgress])

  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current) return

    const tick = async () => {
      try {
        const res = await fetch('/api/screening/progress')
        if (!res.ok) return
        const data = await res.json()
        handleProgressUpdate(data)
        fetchPapersRef.current?.(true)

        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
        const nextDelay = data.is_active ? 2000 : 8000
        pollingIntervalRef.current = setInterval(tick, nextDelay)
      } catch {
        // Network error — keep current interval
      }
    }

    pollingIntervalRef.current = setInterval(tick, 2000)
  }, [handleProgressUpdate])

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }
  }, [])

  useEffect(() => {
    startPolling()
    return () => stopPolling()
  }, [startPolling, stopPolling])

  const handleImportSuccess = (data) => {
    setImportMsg(`Imported ${data.imported_count} paper(s).`)
    setImportError(null)
    setCalibrationBanner(false)
    setPage(1)
    fetchPapers()
    fetchProgress()
  }

  const handleImportError = (errMsg) => {
    setImportError(errMsg)
    setImportMsg(null)
  }

  const handleStartScreening = async (mode = 'full', target = 'ALL') => {
    try {
      await apiFetch(`/screening/start?mode=${mode}&target=${target}`, { method: 'POST' })
      setScreeningActive(true)
      setScreenStarted(true)
      fetchProgress()
    } catch (err) {
      setImportError(err.message)
    }
  }

  const handleStopScreening = async () => {
    try {
      await apiFetch('/screening/stop', { method: 'POST' })
    } catch (err) {
      setImportError(err.message)
    }
  }

  const handleReset = async () => {
    if (!window.confirm("Are you sure you want to delete all papers and decisions? This action cannot be undone.")) return
    try {
      await apiFetch('/system/reset', { method: 'POST' })
      setPapers([])
      setTotal(0)
      setProgress(null)
      setScreeningActive(false)
      setScreenStarted(false)
      setCalibrationBanner(false)
      setPage(1)
      setImportMsg(null)
      setImportError(null)
    } catch (err) {
      setImportError(err.message)
    }
  }

  const handleExport = async () => {
    try {
      const res = await apiFetch('/export?format=xlsx', { blob: true })
      const blob = await res.blob()
      if (blob.type !== 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') {
        throw new Error('Failed to export results. Ensure that some papers have been screened before exporting.')
      }
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'APOLLO_Screening_Results.xlsx'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      setImportError(err.message)
    }
  }

  const handleExportCsv = async () => {
    try {
      const res = await apiFetch('/export?format=csv', { blob: true })
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'APOLLO_Screening_Results_CSV.zip'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      setImportError(err.message)
    }
  }

  const handleTabChange = (tab) => {
    setStatusFilter(tab === 'All' ? null : tab === 'Included' ? 'INCLUDED' : tab === 'Excluded' ? 'EXCLUDED' : 'NEEDS_REVIEW')
    setPage(1)
  }

  const handleLiteratureTypeChange = (type) => {
    setLiteratureType(type)
    setPage(1)
  }

  const handleRefresh = useCallback(() => {
    fetchPapers()
    fetchProgress()
  }, [fetchPapers, fetchProgress])

  const handleFiltersChange = useCallback((newFilters) => {
    setFilters(newFilters)
    setPage(1)
  }, [])

  const totalPages = Math.max(1, Math.ceil(total / size))

  return (
    <div className="min-h-screen bg-zinc-950 font-mono">
      {/* ── Header ── */}
      <header className="fixed top-0 left-0 right-0 z-30 bg-zinc-950/90 backdrop-blur border-b border-zinc-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-11 flex items-center gap-2">
          <Terminal className="w-4 h-4 text-cyan-400 drop-shadow-[0_0_6px_#22d3ee]" />
          <span className="text-sm font-bold tracking-wide text-zinc-100 drop-shadow-[0_0_8px_#22d3ee]">
            APOLLO
          </span>
          <span className="text-[10px] text-zinc-600 ml-1 hidden sm:inline border-l border-zinc-700 pl-2 tracking-widest uppercase">
            SYSTEM_LOG // SLR_MLR_ENGINE_v1.0
          </span>
          <span className="ml-auto text-[10px] text-zinc-600 tabular-nums tracking-wider">
            {progress?.total_papers ?? 0} PAPERS
          </span>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="flex-1 pt-11">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5 space-y-5">
          {/* Top control section */}
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <UploadZone
              onSuccess={handleImportSuccess}
              onError={handleImportError}
            />
            <ProgressCard
              progress={progress}
              active={screeningActive}
              started={screenStarted}
              onStart={(target) => handleStartScreening('full', target)}
              onStartCalibration={(target) => handleStartScreening('calibration', target)}
              onProgressUpdate={handleProgressUpdate}
              onStop={handleStopScreening}
            />
            {/* Export card */}
            <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-4 flex flex-col justify-center items-center gap-3">
              <p className="text-[11px] text-zinc-500 text-center leading-relaxed uppercase tracking-wider">
                Export screened results
              </p>
              <button
                onClick={handleExport}
                disabled={screeningActive}
                className="inline-flex items-center gap-2 px-4 py-2 border-2 border-cyan-800/60 text-cyan-400 hover:bg-cyan-950/30 hover:shadow-neon-cyan text-xs font-bold tracking-wider transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Download className="w-3.5 h-3.5" />
                EXPORT XLSX
              </button>
              <button
                onClick={handleExportCsv}
                disabled={screeningActive}
                className="inline-flex items-center gap-2 px-4 py-2 border-2 border-teal-800/60 text-teal-400 hover:bg-teal-950/30 hover:shadow-neon-teal text-xs font-bold tracking-wider transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Download className="w-3.5 h-3.5" />
                EXPORT CSV
              </button>
              <button
                onClick={handleReset}
                className="inline-flex items-center gap-2 px-4 py-2 border-2 border-rose-800/60 text-rose-400 hover:bg-rose-950/30 text-xs font-bold tracking-wider transition-all duration-200"
              >
                <Trash2 className="w-3.5 h-3.5" />
                RESET
              </button>
            </div>
          </section>

          {/* Banners */}
          {importMsg && (
            <div className="flex items-center gap-2 border border-emerald-800/50 bg-emerald-950/20 px-4 py-2.5 text-xs text-emerald-400 rounded-sm">
              <span className="text-emerald-400 font-bold">&gt;</span>
              {importMsg}
              <button className="ml-auto text-zinc-600 hover:text-zinc-400" onClick={() => setImportMsg(null)}>
                x
              </button>
            </div>
          )}
          {calibrationBanner && (
            <div className="flex items-center gap-2 border border-fuchsia-800/50 bg-fuchsia-950/20 px-4 py-2.5 text-xs text-fuchsia-400 rounded-sm">
              <span className="text-fuchsia-400 font-bold">&gt;</span>
              Calibration complete! Go to the Quality Audit tab to review the 100-paper sample and certify the system.
              <button className="ml-auto text-zinc-600 hover:text-zinc-400" onClick={() => setCalibrationBanner(false)}>
                x
              </button>
            </div>
          )}
          {importError && (
            <div className="flex items-center gap-2 border border-rose-800/50 bg-rose-950/20 px-4 py-2.5 text-xs text-rose-400 rounded-sm">
              <span className="text-rose-400 font-bold">!</span>
              {importError}
              <button className="ml-auto text-zinc-600 hover:text-zinc-400" onClick={() => setImportError(null)}>
                x
              </button>
            </div>
          )}

          {/* View Tabs */}
          <div className="flex items-center gap-6 border-b border-zinc-800 pb-2">
            <button
              onClick={() => setViewTab('explorer')}
              className={`text-[11px] font-bold uppercase tracking-widest transition-colors duration-150 ${
                viewTab === 'explorer'
                  ? 'text-cyan-400 border-b-2 border-cyan-500 pb-2 -mb-2.5'
                  : 'text-zinc-600 hover:text-zinc-400'
              }`}
            >
              Dataset Explorer
            </button>
            <button
              onClick={() => setViewTab('prisma')}
              className={`text-[11px] font-bold uppercase tracking-widest transition-colors duration-150 ${
                viewTab === 'prisma'
                  ? 'text-cyan-400 border-b-2 border-cyan-500 pb-2 -mb-2.5'
                  : 'text-zinc-600 hover:text-zinc-400'
              }`}
            >
              PRISMA Flowchart
            </button>
            <button
              onClick={() => setViewTab('audit')}
              className={`inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest transition-colors duration-150 ${
                viewTab === 'audit'
                  ? 'text-cyan-400 border-b-2 border-cyan-500 pb-2 -mb-2.5'
                  : 'text-zinc-600 hover:text-zinc-400'
              }`}
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              Quality Audit
            </button>
            <button
              onClick={() => setViewTab('settings')}
              className={`inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest transition-colors duration-150 ${
                viewTab === 'settings'
                  ? 'text-cyan-400 border-b-2 border-cyan-500 pb-2 -mb-2.5'
                  : 'text-zinc-600 hover:text-zinc-400'
              }`}
            >
              <Settings className="w-3.5 h-3.5" />
              Protocol Settings
            </button>
            <button
              onClick={() => setViewTab('llm')}
              className={`inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest transition-colors duration-150 ${
                viewTab === 'llm'
                  ? 'text-cyan-400 border-b-2 border-cyan-500 pb-2 -mb-2.5'
                  : 'text-zinc-600 hover:text-zinc-400'
              }`}
            >
              <Brain className="w-3.5 h-3.5" />
              LLM Config
            </button>
            <button
              onClick={() => setViewTab('chat')}
              className={`inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest transition-colors duration-150 ${
                viewTab === 'chat'
                  ? 'text-cyan-400 border-b-2 border-cyan-500 pb-2 -mb-2.5'
                  : 'text-zinc-600 hover:text-zinc-400'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Corpus Chat
            </button>
          </div>

          {/* Content */}
          {viewTab === 'explorer' ? (
            <PaperTable
              papers={papers}
              total={total}
              page={page}
              totalPages={totalPages}
              loading={loadingPapers}
              statusFilter={statusFilter}
              literatureType={literatureType}
              onTabChange={handleTabChange}
              onPageChange={setPage}
              onLiteratureTypeChange={handleLiteratureTypeChange}
              onRefresh={handleRefresh}
              onFiltersChange={handleFiltersChange}
            />
          ) : viewTab === 'prisma' ? (
            <PrismaFlowchart progress={progress} />
          ) : viewTab === 'audit' ? (
            <AccuracyAudit />
          ) : viewTab === 'llm' ? (
            <LLMSettings />
          ) : viewTab === 'chat' ? (
            <CorpusChat progressData={progress} />
          ) : (
            <ProtocolSettings />
          )}
        </div>
      </main>
    </div>
  )
}
