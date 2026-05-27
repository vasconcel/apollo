import { useState, useEffect } from 'react'
import { ShieldAlert, AlertTriangle, Info, Loader2, Play } from 'lucide-react'

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

export default function AccuracyAudit() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

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

  useEffect(() => {
    fetchMetrics()
  }, [])

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

    </div>
  )
}
