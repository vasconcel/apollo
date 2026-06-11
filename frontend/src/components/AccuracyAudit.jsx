import { useState, useEffect, useCallback, Fragment, useRef } from 'react'
import { ShieldAlert, AlertTriangle, Info, Loader2, Play, Sparkles, ChevronDown, ChevronUp, ClipboardCheck, RefreshCw, ExternalLink, Database } from 'lucide-react'

function KappaBadge({ kappa }) {
  if (kappa < 0.4) {
    return <span className="inline-block border border-rose-700 bg-rose-950/30 px-2 py-0.5 text-[10px] font-bold text-rose-400 tracking-wider uppercase">Poor Agreement</span>
  }
  if (kappa < 0.6) {
    return <span className="inline-block border border-orange-700 bg-orange-950/30 px-2 py-0.5 text-[10px] font-bold text-orange-400 tracking-wider uppercase">Moderate Agreement</span>
  }
  if (kappa < 0.8) {
    return <span className="inline-block border border-indigo-700 bg-indigo-950/30 px-2 py-0.5 text-[10px] font-bold text-indigo-400 tracking-wider uppercase">Substantial Agreement — Highly Trusted</span>
  }
  return <span className="inline-block border border-emerald-700 bg-emerald-950/30 px-2 py-0.5 text-[10px] font-bold text-emerald-400 tracking-wider uppercase">Almost Perfect Agreement — Excellent for Publication</span>
}

function MetricCard({ label, value, suffix, children }) {
  return (
    <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-4 flex flex-col gap-1.5">
      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">{label}</span>
      <span className="text-2xl font-bold tabular-nums text-cyan-400">
        {value}{suffix || ''}
      </span>
      {children}
    </div>
  )
}

function ConfusionCell({ label, value, borderColor, bgColor, description, highlight }) {
  return (
    <div className={`border ${borderColor} ${bgColor} rounded-sm p-3 flex flex-col gap-1 ${highlight ? 'ring-1 ring-rose-500/40' : ''}`}>
      <span className="text-[11px] font-bold text-zinc-300 uppercase tracking-wider">{label}</span>
      <span className={`text-xl font-bold tabular-nums ${highlight ? 'text-rose-400' : 'text-zinc-100'}`}>
        {value}
      </span>
      <p className="text-[10px] text-zinc-500 leading-relaxed">{description}</p>
    </div>
  )
}

const WL_QA = [
  { id: 'WL-Q1', text: 'Is the research design clearly described and appropriate for the stated objectives?' },
  { id: 'WL-Q2', text: 'Is the data collection methodology clearly described and suitable for the research context?' },
  { id: 'WL-Q3', text: 'Are the analytical methods rigorous and appropriate for the data collected?' },
  { id: 'WL-Q4', text: 'Are the conclusions supported by the evidence and are limitations discussed?' },
]

const GL_QA = [
  { id: 'GL-Q1', text: "Is the author's expertise or organizational context explicitly stated?" },
  { id: 'GL-Q2', text: 'Is the source of experience transparent (e.g., specific hiring cycle, personal narrative)?' },
  { id: 'GL-Q3', text: 'Are the claims supported by operational artifacts (e.g., process steps, rubrics, or data)?' },
  { id: 'GL-Q4', text: 'Does the source provide insights beyond generic employer marketing (e.g., trade-offs)?' },
]

export default function AccuracyAudit({ onProgressUpdate } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [qaPapers, setQaPapers] = useState([])
  const [qaPapersLoading, setQaPapersLoading] = useState(false)
  const [qaRunning, setQaRunning] = useState(false)
  const [qaProgress, setQaProgress] = useState(null)
  const [qaExpanded, setQaExpanded] = useState(null)
  const [qaValues, setQaValues] = useState({})
  const [qaSubmitting, setQaSubmitting] = useState({})
  const [qaRefreshKey, setQaRefreshKey] = useState(0)
  const [isSeeding, setIsSeeding] = useState(false)
  const [seedAlert, setSeedAlert] = useState(null)

  const fetchMetrics = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/audit/metrics')
      if (!res.ok) throw new Error('Failed to fetch audit metrics')
      const json = await res.json()
      setData(json)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fetchIncludedPapers = useCallback(async () => {
    setQaPapersLoading(true)
    try {
      const res = await fetch('/api/papers?status=INCLUDED&size=500')
      if (!res.ok) throw new Error('Failed to fetch included papers')
      const json = await res.json()
      setQaPapers(json.items || [])
      const qaMap = {}
      for (const p of json.items || []) {
        if (p.source_type === 'WL') {
          if (p.wl_q1 != null) qaMap[p.id] = { q1: p.wl_q1, q2: p.wl_q2, q3: p.wl_q3, q4: p.wl_q4 }
        } else {
          if (p.gl_q1 != null) qaMap[p.id] = { q1: p.gl_q1, q2: p.gl_q2, q3: p.gl_q3, q4: p.gl_q4 }
        }
      }
      setQaValues((prev) => ({ ...prev, ...qaMap }))
    } catch { /* ignore */ } finally {
      setQaPapersLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMetrics()
    fetchIncludedPapers()
  }, [qaRefreshKey])

  useEffect(() => {
    if (!qaRunning) return
    const interval = setInterval(async () => {
      try {
        const res = await fetch('/api/screening/progress')
        if (res.ok) {
          const data = await res.json()
          setQaProgress(data)
          if (!data.qa_active) {
            setQaRunning(false)
            setQaRefreshKey((k) => k + 1)
          }
        }
      } catch { /* ignore */ }
    }, 2000)
    return () => clearInterval(interval)
  }, [qaRunning])

  const handleRunQA = async () => {
    setQaRunning(true)
    try {
      await fetch('/api/quality/assess-all', { method: 'POST' })
    } catch { /* ignore */ }
  }

  const handleSeedCalibration = async () => {
    setIsSeeding(true)
    setSeedAlert(null)
    try {
      const res = await fetch('/api/screening/calibrate-from-audit', { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Request failed (${res.status})`)
      }
      setSeedAlert({ type: 'success', message: 'Audited decisions successfully seeded into the active calibration set!' })
      if (onProgressUpdate) onProgressUpdate()
      setTimeout(() => setSeedAlert(null), 5000)
    } catch (err) {
      setSeedAlert({ type: 'error', message: err.message })
    } finally {
      setIsSeeding(false)
    }
  }

  const getQAQuestions = (sourceType) => sourceType === 'WL' ? WL_QA : GL_QA

  const getQAScore = (paper) => {
    const vals = qaValues[paper.id]
    if (!vals) return null
    const { q1, q2, q3, q4 } = vals
    if (q1 == null || q2 == null || q3 == null || q4 == null) return null
    return q1 + q2 + q3 + q4
  }

  const handleQAChange = async (paperId, qIdx, value, sourceType) => {
    const updated = { ...(qaValues[paperId] || {}), [`q${qIdx}`]: value }
    setQaValues((prev) => ({ ...prev, [paperId]: updated }))
    if (updated.q1 == null || updated.q2 == null || updated.q3 == null || updated.q4 == null) return
    setQaSubmitting((prev) => ({ ...prev, [paperId]: true }))
    try {
      await fetch(`/api/papers/${paperId}/quality`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q1: updated.q1, q2: updated.q2, q3: updated.q3, q4: updated.q4 }),
      })
    } catch { /* ignore */ } finally {
      setQaSubmitting((prev) => ({ ...prev, [paperId]: false }))
    }
  }

  if (loading) {
    return (
      <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-12">
        <Loader2 className="w-5 h-5 animate-spin text-zinc-600 mx-auto" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-12">
        <div className="text-center text-zinc-600">
          <AlertTriangle className="w-6 h-6 mx-auto mb-2" />
          <p className="text-[11px] uppercase tracking-wider">Failed to load audit metrics.</p>
        </div>
      </div>
    )
  }

  const totalAudited = data?.total_audited ?? 0
  const cm = data?.confusion_matrix || { tp: 0, tn: 0, fp: 0, fn: 0 }
  const recall = data?.recall ?? 0
  const precision = data?.precision ?? 0
  const f1 = data?.f1_score ?? 0
  const kappa = data?.cohens_kappa ?? 0
  const calibrationUsed = data?.calibration_used ?? false

  return (
    <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-6 sm:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
        <ShieldAlert className="w-4 h-4 text-cyan-400" />
        <span className="text-sm font-bold text-zinc-100 tracking-wider uppercase">Quality &amp; Accuracy Audit</span>
      </div>

      {/* Callout */}
      <div className="flex items-start gap-3 border border-cyan-800/40 bg-cyan-950/10 rounded-sm px-4 py-3">
        <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
        <p className="text-[11px] text-zinc-400 leading-relaxed">
          To calibrate and validate the AI&apos;s screening accuracy, select a random sample of papers in the Dataset
          Explorer, expand them, and perform manual audits using the &apos;APPROVE YES&apos; or &apos;REJECT NO&apos; buttons.
          The metrics below are calculated dynamically from your manual auditing decisions.
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Total Audited Papers" value={totalAudited} />
        <MetricCard label="Cohen's Kappa" value={kappa.toFixed(2)}>
          <KappaBadge kappa={kappa} />
        </MetricCard>
        <MetricCard label="Recall (Sensitivity)" value={(recall * 100).toFixed(1)} suffix="%">
          <p className="text-[10px] text-zinc-500 leading-relaxed">
            Crucial for SLRs. High recall (&gt;95%) proves that the AI is not missing relevant papers.
          </p>
        </MetricCard>
        <MetricCard label="Precision" value={(precision * 100).toFixed(1)} suffix="%">
          <p className="text-[10px] text-zinc-500 leading-relaxed">
            Measures how much &apos;noise&apos; (false positives) the AI filtered out.
          </p>
        </MetricCard>
      </div>

      {/* F1 Score */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <MetricCard label="F1-Score" value={(f1 * 100).toFixed(1)} suffix="%" />
      </div>
      {calibrationUsed && (
        <div className="text-[10px] text-cyan-500/70 border border-cyan-800/20 bg-cyan-950/5 rounded-sm px-3 py-2">
          Metrics calculated from calibration sample only.
        </div>
      )}

      {/* Confusion Matrix */}
      <div>
        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-3">
          Confusion Matrix (AI vs Human)
        </span>
        <div className="grid grid-cols-2 gap-3">
          <ConfusionCell
            label="True Positives (TP)"
            value={cm.tp}
            borderColor="border-emerald-700/60"
            bgColor="bg-emerald-950/10"
            description="AI and Human agreed to INCLUDE (YES/YES)"
          />
          <ConfusionCell
            label="False Positives (FP)"
            value={cm.fp}
            borderColor="border-amber-700/60"
            bgColor="bg-amber-950/10"
            description="AI INCLUDED, but Human EXCLUDED (YES/NO)"
          />
          <ConfusionCell
            label="False Negatives (FN)"
            value={cm.fn}
            borderColor="border-rose-700/60"
            bgColor="bg-rose-950/10"
            description="AI EXCLUDED, but Human wanted to INCLUDE (NO/YES). Critical loss of data."
            highlight
          />
          <ConfusionCell
            label="True Negatives (TN)"
            value={cm.tn}
            borderColor="border-zinc-700"
            bgColor="bg-zinc-800/30"
            description="AI and Human agreed to EXCLUDE (NO/NO)"
          />
        </div>
      </div>

      {/* Certification Button */}
      {totalAudited >= 20 && (
        <div className="border-t border-zinc-800 pt-6">
          <button
            onClick={async () => {
              try {
                await fetch('/api/screening/start?mode=full', { method: 'POST' })
              } catch (err) {
                console.error('Failed to start full screening:', err)
              }
            }}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 border-2 border-emerald-700/60 text-emerald-400 hover:bg-emerald-950/30 hover:shadow-[0_0_12px_rgba(52,211,153,0.2)] text-xs font-bold tracking-wider transition-all duration-200"
          >
            <Play className="w-4 h-4" />
            CERTIFY &amp; START FULL SCREENING
          </button>
          <p className="text-[10px] text-zinc-600 mt-2 text-center">
            Certified with {totalAudited} audited papers. Remaining calibration placeholders will be automatically screened.
          </p>
        </div>
      )}

      {/* ── Stage 3: Quality Assurance (QA) Panel ──────────────────────────── */}
      <div className="border-t border-zinc-800 pt-6 mt-6">
        <div className="flex items-center gap-2 border-b border-zinc-800 pb-3 mb-4">
          <ClipboardCheck className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-bold text-zinc-100 tracking-wider uppercase">
            Stage 3: Methodological Quality Assurance (QA)
          </span>
        </div>

        {/* Run Automated QA */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <button
            onClick={handleRunQA}
            disabled={qaRunning}
            className="inline-flex items-center gap-2 px-4 py-2 text-[11px] font-bold tracking-wider text-cyan-400 border border-cyan-800/60 hover:bg-cyan-950/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {qaRunning ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5" />
            )}
            {qaRunning ? 'APOLLO is running automated QA on all included papers...' : 'Run Automated Quality Assessment (QA)'}
          </button>
          <button
            onClick={handleSeedCalibration}
            disabled={isSeeding}
            className="inline-flex items-center gap-2 px-4 py-2 text-[11px] font-bold tracking-wider text-cyan-400 border border-cyan-800/60 hover:bg-cyan-950/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSeeding ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Database className="w-3.5 h-3.5" />
            )}
            {isSeeding ? 'Seeding...' : 'Seed Calibration from Audits'}
          </button>
          <button
            onClick={() => setQaRefreshKey((k) => k + 1)}
            disabled={qaPapersLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-[11px] font-bold tracking-wider text-zinc-500 border border-zinc-700 hover:text-zinc-300 hover:border-zinc-500 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${qaPapersLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {seedAlert && (
          <div className={`rounded-sm p-3 text-[11px] leading-relaxed mb-4 ${
            seedAlert.type === 'success'
              ? 'border border-emerald-500/20 bg-emerald-950/10 text-emerald-400 animate-pulse'
              : 'border border-rose-500/20 bg-rose-950/10 text-rose-400'
          }`}>
            {seedAlert.message}
          </div>
        )}

        {/* QA Table */}
        {qaPapersLoading && qaPapers.length === 0 ? (
          <div className="py-8 text-center">
            <Loader2 className="w-4 h-4 animate-spin text-zinc-600 mx-auto" />
          </div>
        ) : qaPapers.length === 0 ? (
          <div className="border border-zinc-800 bg-zinc-900/30 rounded-sm py-8 text-center">
            <p className="text-[11px] text-zinc-600">No included papers found. Run screening first.</p>
          </div>
        ) : (
          <div className="border border-zinc-800 rounded-sm overflow-hidden">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/60">
                  <th className="w-8 px-2 py-1.5 text-left font-bold text-[9px] text-zinc-500 uppercase tracking-widest">#</th>
                  <th className="px-2 py-1.5 text-left font-bold text-[9px] text-zinc-500 uppercase tracking-widest">Library</th>
                  <th className="px-2 py-1.5 text-left font-bold text-[9px] text-zinc-500 uppercase tracking-widest">Title</th>
                  <th className="w-12 px-2 py-1.5 text-left font-bold text-[9px] text-zinc-500 uppercase tracking-widest">Type</th>
                  <th className="w-28 px-2 py-1.5 text-left font-bold text-[9px] text-zinc-500 uppercase tracking-widest">Quality Score</th>
                </tr>
              </thead>
              <tbody>
                {qaPapers.map((p, idx) => {
                  const open = qaExpanded === p.id
                  const score = getQAScore(p)
                  const questions = getQAQuestions(p.source_type)
                  const vals = qaValues[p.id] || {}
                  const submitting = qaSubmitting[p.id] || false
                  return (
                    <Fragment key={p.id}>
                      <tr
                        onClick={() => setQaExpanded((prev) => (prev === p.id ? null : p.id))}
                        className={`border-b border-zinc-800/60 cursor-pointer transition-all duration-150 hover:bg-zinc-800/80 ${open ? 'bg-zinc-800/60' : ''}`}
                      >
                        <td className="px-2 py-2 text-zinc-500 tabular-nums">{idx + 1}</td>
                        <td className="px-2 py-2 text-zinc-400 max-w-[100px] truncate">{p.source_library}</td>
                        <td className="px-2 py-2 text-zinc-200 max-w-md truncate">{p.title}</td>
                        <td className="px-2 py-2">
                          {p.source_type === 'WL' ? (
                            <span className="inline-block border border-cyan-700 px-1 py-0.5 text-[9px] font-bold text-cyan-400 leading-none">[ WL ]</span>
                          ) : (
                            <span className="inline-block border border-fuchsia-700 px-1 py-0.5 text-[9px] font-bold text-fuchsia-400 leading-none">[ GL ]</span>
                          )}
                        </td>
                        <td className="px-2 py-2">
                          {qaProgress?.qa_active && p.id === qaProgress?.current_qa_paper_id ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-bold text-cyan-400">
                              <Loader2 className="w-3 h-3 animate-spin" />
                              Analyzing...
                            </span>
                          ) : score !== null ? (
                            <span className={`inline-flex items-center gap-1 text-[11px] font-bold tabular-nums ${score < 2.0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                              {score.toFixed(1)} / 4.0
                              {score < 2.0 && (
                                <span className="text-[9px] text-rose-500 border border-rose-800/60 px-1 py-0.5 ml-1">QC FAIL</span>
                              )}
                            </span>
                          ) : (
                            <span className="text-zinc-600 text-[10px]">—</span>
                          )}
                          <span className="ml-1.5 text-zinc-600">{open ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />}</span>
                        </td>
                      </tr>
                      {open && (
                        <tr key={`${p.id}-qa-detail`}>
                          <td colSpan={5} className="px-0 py-0 border-b border-zinc-800">
                            <div className="px-6 py-3 bg-zinc-950/60 animate-glide-in space-y-2">
                              {/* Source Verification Link */}
                              <div>
                                <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                                  &gt; SOURCE VERIFICATION LINK
                                </span>
                                {p.pdf_url ? (
                                  <a
                                    href={p.pdf_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    onClick={(e) => e.stopPropagation()}
                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-bold tracking-wider text-emerald-400 border border-emerald-800/60 hover:bg-emerald-950/30 transition-colors"
                                  >
                                    <ExternalLink className="w-3 h-3" />
                                    Open-Access PDF
                                  </a>
                                ) : p.url ? (
                                  <a
                                    href={p.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    onClick={(e) => e.stopPropagation()}
                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-bold tracking-wider text-zinc-400 border border-zinc-700 hover:text-zinc-200 hover:border-zinc-500 transition-colors"
                                  >
                                    <ExternalLink className="w-3 h-3" />
                                    View Source (ACM/Scopus)
                                  </a>
                                ) : (
                                  <p className="text-[11px] text-zinc-600">No external links available.</p>
                                )}
                              </div>
                              {questions.map((q, qIdx) => {
                                const qKey = `q${qIdx + 1}`
                                return (
                                  <div key={q.id} className="flex items-start gap-2 text-[11px]">
                                    <span className={`font-bold shrink-0 w-12 leading-6 ${p.source_type === 'WL' ? 'text-cyan-400' : 'text-fuchsia-400'}`}>{q.id}</span>
                                    <span className="text-zinc-300 flex-1 leading-6">{q.text}</span>
                                    <div className="flex items-center gap-1 shrink-0">
                                      {[1.0, 0.5, 0.0].map((val) => {
                                        const isActive = vals[qKey] === val
                                        const activeClass = isActive
                                          ? val === 1.0
                                            ? 'border-emerald-600 bg-emerald-950/30 text-emerald-400'
                                            : val === 0.5
                                              ? 'border-amber-600 bg-amber-950/30 text-amber-400'
                                              : 'border-rose-600 bg-rose-950/30 text-rose-400'
                                          : 'border-zinc-700 text-zinc-500 hover:text-zinc-300 hover:border-zinc-500'
                                        return (
                                          <button
                                            key={val}
                                            onClick={(e) => { e.stopPropagation(); handleQAChange(p.id, qIdx + 1, val, p.source_type) }}
                                            disabled={submitting}
                                            className={`px-2 py-1 text-[10px] font-bold tracking-wider border transition-colors ${activeClass}`}
                                          >
                                            {val === 1.0 ? 'Yes' : val === 0.5 ? 'Part.' : 'No'}
                                          </button>
                                        )
                                      })}
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  )
}
