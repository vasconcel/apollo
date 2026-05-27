import { useEffect, useRef } from 'react'
import { Play, Cpu, BarChart3, FlaskConical } from 'lucide-react'

export default function ProgressCard({ progress, active, started, onStart, onStartCalibration, onProgressUpdate }) {
  const intervalRef = useRef(null)

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
      <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-5 flex flex-col justify-center items-center gap-3">
        <BarChart3 className="w-6 h-6 text-zinc-600" />
        <p className="text-[11px] text-zinc-500 text-center leading-relaxed uppercase tracking-wider">
          No dataset loaded
        </p>
        <button
          disabled
          className="inline-flex items-center gap-2 px-4 py-2 border-2 border-zinc-700 text-zinc-600 text-xs font-bold tracking-wider cursor-not-allowed"
        >
          <Play className="w-3.5 h-3.5" />
          START SCREENING
        </button>
      </div>
    )
  }

  const total = progress?.total_papers ?? 0
  const screened = progress?.screened_count ?? 0
  const pending = progress?.pending_count ?? 0
  const inCalibration = progress?.in_calibration ?? false
  const pct = total > 0 ? Math.round((screened / total) * 100) : 0
  const isCompleted = !active && pending === 0 && started
  const canCalibrate = !started && total > 0

  return (
    <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Cpu className="w-3.5 h-3.5 text-cyan-400 drop-shadow-[0_0_4px_#22d3ee]" />
          SCREENING ENGINE
        </h3>
        {isCompleted ? (
          <span className="inline-flex items-center gap-1 border border-emerald-700/50 px-2 py-0.5 text-[10px] font-bold text-emerald-400 uppercase tracking-wider">
            COMPLETE
          </span>
        ) : active ? (
          <span className="inline-flex items-center gap-1 border border-cyan-700/50 px-2 py-0.5 text-[10px] font-bold text-cyan-400 uppercase tracking-wider animate-neon-pulse">
            {inCalibration ? 'CALIBRATING' : 'RUNNING'}
          </span>
        ) : inCalibration ? (
          <span className="inline-flex items-center gap-1 border border-emerald-700/50 px-2 py-0.5 text-[10px] font-bold text-emerald-400 uppercase tracking-wider">
            CALIBRATED
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 border border-zinc-700 px-2 py-0.5 text-[10px] font-bold text-zinc-500 uppercase tracking-wider">
            IDLE
          </span>
        )}
      </div>

      {/* Progress bar — neon gradient */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[11px] text-zinc-500">
          <span>{screened} / {total} SCREENED</span>
          <span className="font-mono text-zinc-400 tabular-nums">{pct}%</span>
        </div>
        <div className="w-full h-2 bg-zinc-800 rounded-sm overflow-hidden">
          <div
            className={`h-full rounded-sm transition-all duration-500 ease-out ${
              isCompleted
                ? 'bg-gradient-to-r from-emerald-500 to-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.4)]'
                : 'bg-gradient-to-r from-cyan-500 to-fuchsia-500 shadow-[0_0_10px_rgba(34,211,238,0.3)]'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Telemetry stats */}
      <div className="grid grid-cols-3 gap-3">
        <StatBox label="HEURISTICS" value={progress?.heuristic_exclusions ?? 0} color="text-rose-400" />
        <StatBox label="AI EXCLUDED" value={progress?.ai_exclusions ?? 0} color="text-rose-400" />
        <StatBox label="PENDING" value={pending} color="text-amber-400" />
      </div>

      {/* Action buttons */}
      <div className="space-y-2">
        {!active && !isCompleted && onStartCalibration && canCalibrate && (
          <button
            onClick={onStartCalibration}
            disabled={inCalibration || screened > 0}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 border-2 border-fuchsia-800/60 text-fuchsia-400 hover:bg-fuchsia-950/30 hover:shadow-[0_0_12px_rgba(217,70,239,0.2)] disabled:border-zinc-700 disabled:text-zinc-600 disabled:cursor-not-allowed text-xs font-bold tracking-wider transition-all duration-200"
          >
            <FlaskConical className="w-3.5 h-3.5" />
            START CALIBRATION (100 PAPER SAMPLE)
          </button>
        )}
        {!active && !isCompleted && (
          <button
            onClick={onStart}
            disabled={total === 0}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 border-2 border-cyan-800/60 text-cyan-400 hover:bg-cyan-950/30 hover:shadow-neon-cyan disabled:border-zinc-700 disabled:text-zinc-600 disabled:cursor-not-allowed text-xs font-bold tracking-wider transition-all duration-200"
          >
            <Play className="w-3.5 h-3.5" />
            {started ? 'RESUME FULL SCREENING' : inCalibration ? 'START FULL SCREENING' : 'START SCREENING'}
          </button>
        )}
      </div>
    </div>
  )
}

function StatBox({ label, value, color }) {
  return (
    <div className="border border-zinc-800 bg-zinc-950/30 rounded-sm px-3 py-2 text-center">
      <p className={`text-lg font-bold tabular-nums drop-shadow-[0_0_4px_currentColor] ${color}`}>{value}</p>
      <p className="text-[10px] text-zinc-500 leading-tight tracking-widest">{label}</p>
    </div>
  )
}
