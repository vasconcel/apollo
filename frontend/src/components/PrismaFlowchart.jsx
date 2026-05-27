import { Layers } from 'lucide-react'

function FlowBox({ label, value, variant, children }) {
  const borderColor =
    variant === 'exclude'
      ? 'border-rose-800/60 bg-rose-950/10'
      : variant === 'pending'
        ? 'border-amber-800/60 bg-amber-950/10'
        : 'border-zinc-700 bg-zinc-800/50'

  const valueColor =
    variant === 'exclude'
      ? 'text-rose-400'
      : variant === 'pending'
        ? 'text-amber-400'
        : 'text-cyan-400'

  return (
    <div className={`flex-1 border ${borderColor} rounded-sm px-5 py-4 min-w-0`}>
      <p className="text-[11px] text-zinc-400 uppercase tracking-wider leading-relaxed">
        {label}
      </p>
      {children || (
        <p className={`text-2xl font-bold mt-1.5 tabular-nums ${valueColor}`}>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </p>
      )}
    </div>
  )
}

function VerticalArrow() {
  return (
    <div className="flex justify-center py-1">
      <svg width="20" height="28" viewBox="0 0 20 28" aria-hidden="true">
        <line x1="10" y1="0" x2="10" y2="24" stroke="#52525b" strokeWidth="2" />
        <polygon points="10,28 5,20 15,20" fill="#52525b" />
      </svg>
    </div>
  )
}

function HorizontalArrow() {
  return (
    <svg width="32" height="20" viewBox="0 0 32 20" className="shrink-0 mt-7" aria-hidden="true">
      <line x1="0" y1="10" x2="26" y2="10" stroke="#52525b" strokeWidth="2" />
      <polygon points="32,10 24,5 24,15" fill="#52525b" />
    </svg>
  )
}

function PhaseLabel({ children }) {
  return (
    <div className="w-28 shrink-0 pt-4">
      <span className="text-[10px] font-bold text-cyan-500 uppercase tracking-[0.25em]">
        {children}
      </span>
    </div>
  )
}

export default function PrismaFlowchart({ progress }) {
  if (!progress || !progress.total_papers) {
    return (
      <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-12">
        <div className="text-center text-zinc-600">
          <Layers className="w-8 h-8 mx-auto mb-2" />
          <p className="text-[11px] uppercase tracking-wider">
            No data available. Import papers to view the PRISMA flowchart.
          </p>
        </div>
      </div>
    )
  }

  const total = progress.total_papers ?? 0
  const duplicates = progress.duplicates_count ?? 0
  const unique = total - duplicates
  const heuristic = progress.heuristic_exclusions ?? 0
  const aiExclusions = progress.ai_exclusions ?? 0
  const pending = progress.pending_count ?? 0
  const included = progress.included_count ?? 0

  return (
    <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm p-6 sm:p-10 overflow-x-auto">
      <div className="min-w-[640px] max-w-4xl mx-auto">
        {/* ── IDENTIFICATION ── */}
        <div className="flex gap-6">
          <PhaseLabel>Identification</PhaseLabel>
          <div className="flex-1 min-w-0">
            <div className="flex items-start gap-3">
              <FlowBox label="Records identified from databases" value={total} />
              <HorizontalArrow />
              <div className="w-56 shrink-0">
                <FlowBox label="Duplicate records removed" value={duplicates} variant="exclude" />
              </div>
            </div>
            <VerticalArrow />
            <FlowBox label="Unique records after deduplication" value={unique} />
          </div>
        </div>

        {/* ── SCREENING ── */}
        <div className="flex gap-6 mt-6">
          <PhaseLabel>Screening</PhaseLabel>
          <div className="flex-1 min-w-0">
            <div className="flex items-start gap-3">
              <FlowBox label="Records screened" value={unique} />
              <HorizontalArrow />
              <div className="w-56 shrink-0">
                <FlowBox label="Records excluded" variant="exclude">
                  <div className="mt-2 space-y-1">
                    <div className="flex justify-between text-[12px] text-rose-300">
                      <span>Heuristic Exclusions</span>
                      <span className="font-bold tabular-nums">{heuristic.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between text-[12px] text-rose-300">
                      <span>AI Excluded</span>
                      <span className="font-bold tabular-nums">{aiExclusions.toLocaleString()}</span>
                    </div>
                  </div>
                </FlowBox>
              </div>
            </div>
            <VerticalArrow />
            <FlowBox label="Papers pending AI screening" value={pending} variant="pending" />
          </div>
        </div>

        {/* ── INCLUDED ── */}
        <div className="flex gap-6 mt-6">
          <PhaseLabel>Included</PhaseLabel>
          <div className="flex-1 min-w-0">
            <VerticalArrow />
            <FlowBox label="Studies included in review" value={included} />
          </div>
        </div>
      </div>
    </div>
  )
}
