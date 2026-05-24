import { useState } from 'react'
import { ChevronDown, ChevronUp, Loader2, AlertCircle, FileText, FileSearch, ThumbsUp, ThumbsDown } from 'lucide-react'

const TABS = ['All', 'Included', 'Excluded', 'Needs Review']

const SOURCE_TYPES = [
  { key: 'ALL', label: 'All Literature' },
  { key: 'WL', label: 'White Literature (WL)' },
  { key: 'GL', label: 'Grey Literature (GL)' },
]

const SOURCE_BADGE = {
  WL: { label: 'WL', classes: 'bg-sky-100 text-sky-700 border-sky-200' },
  GL: { label: 'GL', classes: 'bg-violet-100 text-violet-700 border-violet-200' },
}

const STATUS_MAP = {
  INCLUDED: { label: 'YES', classes: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  EXCLUDED: { label: 'NO', classes: 'bg-rose-100 text-rose-700 border-rose-200' },
  NEEDS_REVIEW: { label: 'NEEDS_REVIEW', classes: 'bg-amber-100 text-amber-700 border-amber-200' },
}

function statusBadge(status) {
  if (!status) {
    return <span className="inline-block rounded-md border border-gray-200 bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-400">PENDING</span>
  }
  const m = STATUS_MAP[status]
  if (!m) return <span className="text-xs text-gray-400">{status}</span>
  return <span className={`inline-block rounded-md border px-2.5 py-0.5 text-xs font-medium ${m.classes}`}>{m.label}</span>
}

export default function PaperTable({
  papers,
  total,
  page,
  totalPages,
  loading,
  statusFilter,
  literatureType,
  onTabChange,
  onPageChange,
  onLiteratureTypeChange,
  onRefresh,
}) {
  const [expanded, setExpanded] = useState(null)
  const [auditingId, setAuditingId] = useState(null)

  const activeTab = !statusFilter ? 'All' : statusFilter === 'INCLUDED' ? 'Included' : statusFilter === 'EXCLUDED' ? 'Excluded' : 'Needs Review'

  const toggleRow = (id) => {
    setExpanded((prev) => (prev === id ? null : id))
  }

  const handleAudit = async (paperId, verdict) => {
    setAuditingId(paperId)
    try {
      const res = await fetch(`/api/papers/${paperId}/audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ verdict }),
      })
      if (!res.ok) return
      if (onRefresh) onRefresh()
    } catch { /* ignore */ } finally {
      setAuditingId(null)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* ── Status Filters ── */}
      <div className="flex items-center gap-1 px-4 pt-4 pb-2">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => onTabChange(tab)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab
                ? 'bg-emerald-100 text-emerald-800'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            {tab}
          </button>
        ))}
        <span className="ml-auto text-xs text-gray-400 tabular-nums">{total} paper{total !== 1 ? 's' : ''}</span>
      </div>

      {/* ── Literature Type Toggle ── */}
      <div className="flex items-center gap-1 px-4 pb-3 border-b border-gray-100">
        {SOURCE_TYPES.map((st) => (
          <button
            key={st.key}
            onClick={() => onLiteratureTypeChange(st.key)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              literatureType === st.key
                ? 'bg-indigo-100 text-indigo-800'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            {st.key === 'WL' && <FileText className="w-3.5 h-3.5" />}
            {st.key === 'GL' && <FileSearch className="w-3.5 h-3.5" />}
            {st.label}
          </button>
        ))}
      </div>

      {/* ── Table ── */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/50">
              <th className="w-8 px-3 py-2.5 text-left font-medium text-gray-400 text-xs uppercase tracking-wider" />
              <th className="px-3 py-2.5 text-left font-medium text-gray-400 text-xs uppercase tracking-wider w-10">#</th>
              <th className="px-3 py-2.5 text-left font-medium text-gray-400 text-xs uppercase tracking-wider">Library</th>
              <th className="px-3 py-2.5 text-left font-medium text-gray-400 text-xs uppercase tracking-wider">Title</th>
              <th className="px-3 py-2.5 text-left font-medium text-gray-400 text-xs uppercase tracking-wider w-28">Decision</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-3 py-12 text-center">
                  <Loader2 className="w-5 h-5 animate-spin text-gray-400 mx-auto" />
                </td>
              </tr>
            ) : papers.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-12 text-center text-gray-400 text-sm">
                  <AlertCircle className="w-5 h-5 mx-auto mb-1" />
                  No papers match this filter.
                </td>
              </tr>
            ) : (
              papers.map((p, idx) => {
                const open = expanded === p.id
                const rowNum = (page - 1) * 20 + idx + 1
                return (
                  <PaperRow
                    key={p.id}
                    paper={p}
                    rowNum={rowNum}
                    open={open}
                    auditing={auditingId === p.id}
                    onToggle={() => toggleRow(p.id)}
                    onAudit={(verdict) => handleAudit(p.id, verdict)}
                  />
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50/50">
          <button
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="px-3 py-1.5 rounded-md text-sm font-medium text-gray-600 hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500 tabular-nums">
            Page {page} of {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="px-3 py-1.5 rounded-md text-sm font-medium text-gray-600 hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}

function PaperRow({ paper, rowNum, open, auditing, onToggle, onAudit }) {
  const criteria = paper.applied_criteria_codes || []
  const exclusionCriteria = criteria.filter((c) => c.startsWith('EC'))
  const inclusionCriteria = criteria.filter((c) => c.startsWith('IC'))

  return (
    <>
      <tr
        onClick={onToggle}
        className={`border-b border-gray-50 cursor-pointer transition-colors hover:bg-gray-50 ${
          open ? 'bg-gray-50' : ''
        }`}
      >
        <td className="px-3 py-2.5 text-gray-400">
          {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </td>
        <td className="px-3 py-2.5 text-gray-500 tabular-nums">{rowNum}</td>
        <td className="px-3 py-2.5 text-gray-700 max-w-[140px] truncate">{paper.source_library}</td>
        <td className="px-3 py-2.5 text-gray-800 font-medium max-w-md">
          <div className="flex items-center gap-2 truncate">
            {paper.source_type && SOURCE_BADGE[paper.source_type] && (
              <span className={`inline-block rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase leading-none shrink-0 ${SOURCE_BADGE[paper.source_type].classes}`}>
                {SOURCE_BADGE[paper.source_type].label}
              </span>
            )}
            <span className="truncate">{paper.title}</span>
          </div>
        </td>
        <td className="px-3 py-2.5">{statusBadge(paper.status)}</td>
      </tr>
      {open && (
        <tr key={`${paper.id}-detail`}>
          <td colSpan={5} className="px-3 py-0 border-b border-gray-100">
            <div className="px-10 py-4 space-y-3 bg-white text-sm leading-relaxed">
              {/* Abstract */}
              <Section title="Abstract">
                <p className="text-gray-600 max-h-24 overflow-y-auto whitespace-pre-wrap">
                  {paper.abstract || '(no abstract)'}
                </p>
              </Section>

              {/* Criteria codes */}
              <div className="flex flex-wrap gap-6">
                {inclusionCriteria.length > 0 && (
                  <div>
                    <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Inclusion Criteria</span>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {inclusionCriteria.map((code) => (
                        <span key={code} className="inline-block rounded-md bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-xs font-medium text-emerald-700">
                          {code}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {exclusionCriteria.length > 0 && (
                  <div>
                    <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Exclusion Criteria</span>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {exclusionCriteria.map((code) => (
                        <span key={code} className="inline-block rounded-md bg-rose-50 border border-rose-200 px-2 py-0.5 text-xs font-medium text-rose-700">
                          {code}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {criteria.length === 0 && (
                  <p className="text-xs text-gray-400">No criteria codes recorded.</p>
                )}
              </div>

              {/* AI Rationale */}
              {paper.rationale && (
                <Section title="AI Rationale">
                  <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 text-gray-700 text-xs leading-relaxed max-h-48 overflow-y-auto whitespace-pre-wrap font-mono">
                    {paper.rationale}
                  </div>
                </Section>
              )}

              {/* Human Audit Override */}
              <div>
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-2">Human Audit Override</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => { e.stopPropagation(); onAudit('YES') }}
                    disabled={auditing}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-300 px-3 py-1.5 text-xs font-medium text-white transition-colors"
                  >
                    {auditing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ThumbsUp className="w-3.5 h-3.5" />}
                    Approve as YES (Included)
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onAudit('NO') }}
                    disabled={auditing}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 disabled:bg-rose-300 px-3 py-1.5 text-xs font-medium text-white transition-colors"
                  >
                    {auditing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ThumbsDown className="w-3.5 h-3.5" />}
                    Reject as NO (Excluded)
                  </button>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function Section({ title, children }) {
  return (
    <div>
      <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-1">{title}</span>
      {children}
    </div>
  )
}
