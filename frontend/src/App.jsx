import { useState, useEffect, useCallback, useRef } from 'react'
import { FlaskConical, Download } from 'lucide-react'
import UploadZone from './components/UploadZone'
import ProgressCard from './components/ProgressCard'
import PaperTable from './components/PaperTable'

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

  const [importMsg, setImportMsg] = useState(null)
  const [importError, setImportError] = useState(null)

  const [screeningActive, setScreeningActive] = useState(false)
  const [progress, setProgress] = useState(null)
  const [screenStarted, setScreenStarted] = useState(false)

  const pollRef = useRef(null)
  const fetchPapersRef = useRef(null)

  const fetchProgress = useCallback(async () => {
    try {
      const p = await apiFetch('/screening/progress')
      setProgress(p)
      if (p.is_active) {
        setScreeningActive(true)
        setScreenStarted(true)
      }
      return p
    } catch { /* backend may not be ready */ }
  }, [])

  const fetchPapers = useCallback(async () => {
    setLoadingPapers(true)
    try {
      const params = new URLSearchParams({ page, size })
      if (statusFilter) params.set('status', statusFilter)
      if (literatureType !== 'ALL') params.set('source_type', literatureType)
      const data = await apiFetch(`/papers?${params}`)
      setPapers(data.items)
      setTotal(data.total)
    } catch {
      /* backend may not be ready */
    } finally {
      setLoadingPapers(false)
    }
  }, [page, size, statusFilter, literatureType])

  /* keep a mutable ref so polling interval never captures stale closure */
  fetchPapersRef.current = fetchPapers

  useEffect(() => {
    fetchPapers()
  }, [fetchPapers])

  /* auto‑poll progress on mount if screening was active */
  useEffect(() => {
    fetchProgress()
  }, [fetchProgress])

  /* poll papers every 4 s while screening runs so decisions appear in real time */
  useEffect(() => {
    if (!screeningActive) return
    const interval = setInterval(() => {
      fetchPapersRef.current()
    }, 4000)
    return () => clearInterval(interval)
  }, [screeningActive])

  const handleImportSuccess = (data) => {
    setImportMsg(`Imported ${data.imported_count} paper(s).`)
    setImportError(null)
    setPage(1)
    fetchPapers()
    fetchProgress()
  }

  const handleImportError = (errMsg) => {
    setImportError(errMsg)
    setImportMsg(null)
  }

  const handleStartScreening = async () => {
    console.log('Start Screening clicked')
    try {
      await apiFetch('/screening/start', { method: 'POST' })
      setScreeningActive(true)
      setScreenStarted(true)
      fetchProgress()
    } catch (err) {
      setImportError(err.message)
    }
  }

  const handleProgressUpdate = (p) => {
    setProgress(p)
    if (!p.is_active && p.pending_count === 0) {
      setScreeningActive(false)
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      fetchPapers()
    }
  }

  const handleExport = async () => {
    try {
      const blob = await apiFetch('/export', { blob: true })
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

  const totalPages = Math.max(1, Math.ceil(total / size))

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* ── Fixed Header ── */}
      <header className="fixed top-0 left-0 right-0 z-30 bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center gap-2">
          <FlaskConical className="w-6 h-6 text-emerald-600" />
          <span className="text-lg font-bold tracking-tight text-gray-800">APOLLO</span>
          <span className="text-sm text-gray-400 ml-1 hidden sm:inline">Systematic Literature Review Screening</span>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="flex-1 pt-14">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
          {/* Top control section */}
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <UploadZone
              onSuccess={handleImportSuccess}
              onError={handleImportError}
            />
            <ProgressCard
              progress={progress}
              active={screeningActive}
              started={screenStarted}
              onStart={handleStartScreening}
              onProgressUpdate={handleProgressUpdate}
            />
            {/* Export card */}
            <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col justify-center items-center gap-3">
              <p className="text-sm text-gray-500 text-center leading-relaxed">
                Download the styled workbook with WL and GL sheets.
              </p>
              <button
                onClick={handleExport}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium transition-colors"
              >
                <Download className="w-4 h-4" />
                Export XLSX
              </button>
            </div>
          </section>

          {/* Banners */}
          {importMsg && (
            <div className="flex items-center gap-2 rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-800">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
              {importMsg}
              <button className="ml-auto text-emerald-600 hover:text-emerald-800 font-medium" onClick={() => setImportMsg(null)}>
                Dismiss
              </button>
            </div>
          )}
          {importError && (
            <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-800">
              <span className="inline-block w-2 h-2 rounded-full bg-red-500 shrink-0" />
              {importError}
              <button className="ml-auto text-red-600 hover:text-red-800 font-medium" onClick={() => setImportError(null)}>
                Dismiss
              </button>
            </div>
          )}

          {/* Paper Table */}
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
          />
        </div>
      </main>
    </div>
  )
}
