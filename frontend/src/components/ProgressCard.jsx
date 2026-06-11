import { useState } from 'react'
import { Play, Square, RefreshCw, Cpu, BarChart3, FlaskConical, Loader2 } from 'lucide-react'

const TARGET_OPTIONS = [
  { key: 'ALL', label: 'ALL' },
  { key: 'WL', label: '[ WL ]' },
  { key: 'GL', label: '[ GL ]' },
]

export default function ProgressCard({ progress, active, started, onStart, onStartCalibration, onProgressUpdate, onStop }) {
  const [targetScope, setTargetScope] = useState('ALL')

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
  const isActive = progress?.is_active ?? active ?? false
  const pct = total > 0 ? Math.round((screened / total) * 100) : 0
  const isCompleted = !isActive && pending === 0 && started
  const canCalibrate = !started && total > 0
  const calibrationPaused = inCalibration && !isActive && screened > 0 && screened < total
  const calibrationComplete = inCalibration && screened === total && total > 0

  const stopping = progress?.stopping_active ?? false

  let statusLabel, statusColor
  if (stopping) {
    statusLabel = 'STOPPING...'
    statusColor = 'text-rose-500 border-rose-500/50 animate-pulse'
  } else if (isCompleted) {
    statusLabel = 'COMPLETE'
    statusColor = 'text-emerald-400 border-emerald-700/50'
  } else if (isActive) {
    if (inCalibration) {
      statusLabel = 'CALIBRATING'
      statusColor = 'text-cyan-400 border-cyan-700/50 animate-neon-pulse'
    } else {
      statusLabel = 'RUNNING'
      statusColor = 'text-cyan-400 border-cyan-700/50 animate-neon-pulse'
    }
  } else if (inCalibration) {
    if (screened < total) {
      statusLabel = 'CALIBRATION PAUSED'
      statusColor = 'text-amber-400 border-amber-700/50'
    } else {
      statusLabel = 'CALIBRATION COMPLETE'
      statusColor = 'text-emerald-400 border-emerald-700/50'
    }
  } else {
    statusLabel = 'IDLE'
    statusColor = 'text-zinc-500 border-zinc-700'
  }

  return (
    <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Cpu className="w-3.5 h-3.5 text-cyan-400 drop-shadow-[0_0_4px_#22d3ee]" />
          SCREENING ENGINE
        </h3>
        <span className={`inline-flex items-center gap-1 border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusColor}`}>
          {statusLabel}
        </span>
      </div>

      {/* Active Engine Badge */}
      {isActive && progress?.active_provider && (
        <div className="flex items-center gap-1.5 border border-cyan-500/20 bg-cyan-950/10 rounded-sm px-2.5 py-1">
          <span className="text-[9px] font-bold uppercase tracking-widest text-cyan-400/70">Active Engine:</span>
          <span className="text-[10px] font-mono text-cyan-300 font-semibold">
            {progress.active_provider.charAt(0).toUpperCase() + progress.active_provider.slice(1)}
            {progress.active_model ? ` (${progress.active_model})` : ''}
          </span>
        </div>
      )}

      {/* Live Status Ticker */}
      {isActive && progress?.currently_screening && (
        <div className="flex items-center gap-1.5 min-h-[20px]">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
          <span className="text-[10px] text-zinc-400 truncate" title={progress.currently_screening}>
            Processing: &ldquo;{progress.currently_screening}&rdquo;
          </span>
        </div>
      )}

      {/* Cooldown countdown */}
      {isActive && (progress?.cooldown_remaining ?? 0) > 0 && (
        <div className="flex items-center gap-1.5 min-h-[16px]">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse shrink-0" />
          <span className="text-[10px] text-amber-400 animate-pulse">
            Cooldown — {progress.cooldown_remaining.toFixed(1)}s
          </span>
        </div>
      )}

      {/* Progress bar — neon gradient */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[11px] text-zinc-500">
          <span>{screened} / {total} SCREENED</span>
          <span className="font-mono text-zinc-400 tabular-nums">{pct}%</span>
        </div>
        <div className="w-full h-2 bg-zinc-800 rounded-sm overflow-hidden">
          <div
            className={`h-full rounded-sm transition-all duration-500 ease-out ${
              isCompleted || calibrationComplete
                ? 'bg-gradient-to-r from-emerald-500 to-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.4)]'
                : 'bg-gradient-to-r from-cyan-500 to-fuchsia-500 shadow-[0_0_10px_rgba(34,211,238,0.3)]'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Telemetry stats */}
      <div className="grid grid-cols-3 gap-3">
        <StatBox label="INCLUDED" value={progress?.included_count ?? 0} color="text-emerald-400 drop-shadow-[0_0_4px_rgba(52,211,153,0.3)]" />
        <StatBox label="EXCLUDED" value={(progress?.duplicates_count ?? 0) + (progress?.heuristic_exclusions ?? 0) + (progress?.ai_exclusions ?? 0)} color="text-rose-400 drop-shadow-[0_0_4px_rgba(251,113,133,0.3)]" />
        <StatBox label="PENDING" value={pending} color="text-amber-400" />
      </div>

      {/* Target scope selector */}
      <div>
        <span className="text-[10px] text-zinc-500 uppercase tracking-widest block mb-1">Screening Target</span>
        <div className="flex items-center gap-1">
          {TARGET_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              onClick={() => setTargetScope(opt.key)}
              disabled={isActive || started}
              className={`px-2.5 py-1 text-[11px] font-bold tracking-wider transition-all duration-150 ${
                targetScope === opt.key
                  ? opt.key === 'WL' ? 'text-cyan-400 bg-cyan-950/30 border border-cyan-700'
                    : opt.key === 'GL' ? 'text-fuchsia-400 bg-fuchsia-950/30 border border-fuchsia-700'
                    : 'text-zinc-200 bg-zinc-800 border border-zinc-600'
                  : 'text-zinc-600 hover:text-zinc-400 border border-transparent'
              } ${(isActive || started) ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Action buttons */}
      <div className="space-y-2">
        {(isActive || stopping) && (
          <button
            onClick={() => { if (!stopping && onStop) onStop() }}
            disabled={stopping}
            className={`w-full inline-flex items-center justify-center gap-2 px-4 py-2 border-2 text-xs font-bold tracking-wider transition-all duration-200 ${
              stopping
                ? 'border-zinc-700 text-zinc-500 bg-zinc-900/40 cursor-not-allowed'
                : 'border-rose-800 text-rose-400 hover:bg-rose-950/30 hover:shadow-[0_0_12px_rgba(251,113,133,0.2)]'
            }`}
          >
            {stopping ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3.5 h-3.5" />}
            {stopping ? 'STOPPING SCREENING...' : 'STOP SCREENING'}
          </button>
        )}
        {!isActive && !isCompleted && onStartCalibration && (canCalibrate || calibrationPaused) && (
          <button
            onClick={() => { if (onStartCalibration) onStartCalibration(targetScope) }}
            disabled={calibrationComplete}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 border-2 border-fuchsia-800/60 text-fuchsia-400 hover:bg-fuchsia-950/30 hover:shadow-[0_0_12px_rgba(217,70,239,0.2)] disabled:border-zinc-700 disabled:text-zinc-600 disabled:cursor-not-allowed text-xs font-bold tracking-wider transition-all duration-200"
          >
            {calibrationPaused ? <RefreshCw className="w-3.5 h-3.5" /> : <FlaskConical className="w-3.5 h-3.5" />}
            {calibrationPaused ? 'RESUME CALIBRATION' : 'START CALIBRATION (100 PAPER SAMPLE)'}
          </button>
        )}
        {!isActive && !isCompleted && (
          <button
            onClick={() => { if (onStart) onStart(targetScope) }}
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
