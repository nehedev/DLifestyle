import { useCallback, useEffect, useState } from 'react'
import { adminListServiceRequests, adminPatchServiceRequest, naira } from '../../api'
import type { ServiceRequestAdminResponse } from '../../api'

const STATUS_TRANSITIONS: Record<string, string[]> = {
  requested: ['contacted', 'cancelled'],
  contacted: ['confirmed', 'cancelled'],
  confirmed: ['completed', 'cancelled'],
}

const STATUS_FILTERS = ['', 'requested', 'contacted', 'confirmed', 'completed', 'cancelled']

const STATUS_COLORS: Record<string, string> = {
  requested: '#F2B01E',
  contacted: '#1a6b8a',
  confirmed: '#0A6A1B',
  completed: '#566357',
  cancelled: '#A71930',
}

function StatusBadge({ status }: { status: string }) {
  return <span className="adm-badge" style={{ background: STATUS_COLORS[status] ?? '#566357' }}>{status}</span>
}

function RequestDrawer({
  req,
  onClose,
  onUpdated,
}: {
  req: ServiceRequestAdminResponse
  onClose: () => void
  onUpdated: (r: ServiceRequestAdminResponse) => void
}) {
  const [note, setNote] = useState(req.owner_note ?? '')
  const [quote, setQuote] = useState(req.quoted_amount_minor !== null ? String(req.quoted_amount_minor / 100) : '')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const patch = async (extra: Partial<Parameters<typeof adminPatchServiceRequest>[1]> = {}) => {
    setBusy(true)
    setErr('')
    try {
      const updated = await adminPatchServiceRequest(req.id, {
        owner_note: note.trim() || null,
        quoted_amount_minor: quote !== '' ? Math.round(Number(quote) * 100) : null,
        ...extra,
      })
      onUpdated(updated)
    } catch {
      setErr('That update is not allowed.')
    } finally {
      setBusy(false)
    }
  }

  const advance = (status: string) => void patch({ status })

  return (
    <div className="adm-overlay" onClick={onClose}>
      <aside className="adm-drawer" onClick={e => e.stopPropagation()}>
        <div className="adm-drawer-hdr">
          <h2>Request #{req.id}</h2>
          <button className="adm-close" onClick={onClose} aria-label="Close"><iconify-icon icon="lucide:x" /></button>
        </div>
        <div className="adm-meta">
          <span><b>Status</b> <StatusBadge status={req.status} /></span>
          <span><b>Service ID</b> {req.service_id}</span>
          <span><b>Location</b> {req.location}</span>
          <span><b>Details</b> {req.details}</span>
          <span><b>Phone</b> {req.contact_phone}</span>
          {req.preferred_date && <span><b>Preferred date</b> {req.preferred_date}</span>}
          {req.quoted_amount_minor !== null && <span><b>Quoted</b> {naira(req.quoted_amount_minor)}</span>}
        </div>
        <div className="adm-form">
          <label className="fld">Quote (₦)
            <input className="inp" type="number" min={0} value={quote}
              onChange={e => setQuote(e.target.value)} placeholder="Leave blank to clear" />
          </label>
          <label className="fld">Owner note
            <textarea className="inp" rows={3} value={note} onChange={e => setNote(e.target.value)} />
          </label>
          {err && <p className="err">{err}</p>}
          <div className="adm-actions">
            <button className="btn sm" disabled={busy} onClick={() => void patch()}>Save note / quote</button>
            {STATUS_TRANSITIONS[req.status]?.map(s => (
              <button key={s} className={`btn sm ${s === 'cancelled' ? 'red' : ''}`} disabled={busy} onClick={() => advance(s)}>
                Mark {s}
              </button>
            ))}
          </div>
        </div>
      </aside>
    </div>
  )
}

export function AdminServiceRequests() {
  const [items, setItems] = useState<ServiceRequestAdminResponse[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [selected, setSelected] = useState<ServiceRequestAdminResponse | null>(null)

  const load = useCallback(async (filter: string, cur: string | null, append: boolean) => {
    setLoading(true)
    setErr('')
    try {
      const page = await adminListServiceRequests({ status: filter || undefined, cursor: cur })
      setItems(prev => append ? [...prev, ...page.items] : page.items)
      setCursor(page.next_cursor)
      setHasMore(page.next_cursor !== null)
    } catch {
      setErr('Could not load service requests.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load(statusFilter, null, false) }, [statusFilter, load])

  const handleUpdated = (updated: ServiceRequestAdminResponse) => {
    setItems(prev => prev.map(r => r.id === updated.id ? updated : r))
    setSelected(updated)
  }

  return (
    <div className="adm-section">
      <div className="adm-section-hdr">
        <h1>Service requests</h1>
        <select className="adm-select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          {STATUS_FILTERS.map(s => <option key={s} value={s}>{s || 'All statuses'}</option>)}
        </select>
      </div>
      {err && <p className="err">{err}</p>}
      <table className="adm-table">
        <thead>
          <tr><th>#</th><th>Status</th><th>Location</th><th>Phone</th><th>Date</th><th>Created</th><th></th></tr>
        </thead>
        <tbody>
          {items.map(r => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td><StatusBadge status={r.status} /></td>
              <td>{r.location}</td>
              <td>{r.contact_phone}</td>
              <td>{r.preferred_date ?? '—'}</td>
              <td>{new Date(r.created_at).toLocaleDateString('en-NG')}</td>
              <td><button className="btn sm" onClick={() => setSelected(r)}>View</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 && !loading && <p className="note">No service requests found.</p>}
      {hasMore && (
        <button className="btn ghost sm" disabled={loading} onClick={() => void load(statusFilter, cursor, true)}>
          {loading ? 'Loading…' : 'Load more'}
        </button>
      )}
      {selected && (
        <RequestDrawer req={selected} onClose={() => setSelected(null)} onUpdated={handleUpdated} />
      )}
    </div>
  )
}
