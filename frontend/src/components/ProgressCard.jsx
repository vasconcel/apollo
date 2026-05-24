import { useEffect, useRef } from 'react'
import { Play, Sparkles, BarChart3 } from 'lucide-react'

export default function ProgressCard({ progress, active, started, onStart, onProgressUpdate }) {
  const intervalRef = useRef(null)

  /* start/stop polling based on active state */
  useEffect(() => {
    if (active) {
      intervalRef.current = setInterval(async () => {
        try {
          const res = await fetch('/api/screening/progress')
          if (res.ok) onProgressUpdate(await res.json())
        } catch { /* ignore */ }
      }, 2000)
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [active, onProgressUpdate])

  if ((!progress || !progress.total_papers) && !active && !started) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col justify-center items-center gap-3">
        <BarChart3 className="w-8 h-8 text-gray-300" />
        <p className="text-sm text-gray-400 text-center leading-relaxed">
          Import a dataset, then start AI screening.
        </p>
        <button
          disabled
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gray-200 text-gray-400 text-sm font-medium cursor-not-allowed"
        >
          <Play className="w-4 h-4" />
          Start AI Screening
        </button>
      </div>
    )
  }

  const total = progress?.total_papers ?? 0
  const screened = progress?.screened_count ?? 0
  const pending = progress?.pending_count ?? 0
  const pct = total > 0 ? Math.round((screened / total) * 100) : 0
  const isCompleted = !active && pending === 0 && started

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
          <Sparkles className="w-4 h-4 text-emerald-500" />
          AI Screening
        </h3>
        {isCompleted ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Completed
          </span>
        ) : active ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            Running
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-500">
            Idle
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{screened} / {total} screened</span>
          <span className="font-mono">{pct}%</span>
        </div>
        <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              isCompleted ? 'bg-emerald-500' : 'bg-emerald-400'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-3">
        <StatBox label="Heuristics" value={progress?.heuristic_exclusions ?? 0} color="text-rose-600" />
        <StatBox label="AI Excluded" value={progress?.ai_exclusions ?? 0} color="text-rose-500" />
        <StatBox label="Pending" value={pending} color="text-amber-600" />
      </div>

      {/* Action button */}
      {!active && !isCompleted && (
        <button
          onClick={onStart}
          disabled={total === 0}
          className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
        >
          <Play className="w-4 h-4" />
          {started ? 'Resume Screening' : 'Start AI Screening'}
        </button>
      )}
    </div>
  )
}

function StatBox({ label, value, color }) {
  return (
    <div className="rounded-lg bg-gray-50 px-3 py-2 text-center">
      <p className={`text-lg font-bold tabular-nums ${color}`}>{value}</p>
      <p className="text-[10px] text-gray-400 leading-tight">{label}</p>
    </div>
  )
}
