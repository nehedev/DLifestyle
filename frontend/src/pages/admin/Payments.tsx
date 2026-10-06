import { useCallback, useEffect, useState } from 'react'
import { adminListPayments, naira } from '../../api'
import type { AdminPaymentListItem } from '../../api'

const STATUS_FILTERS = ['', 'initiated', 'succeeded', 'failed', 'needs_review', 'refund_pending', 'refunded']

const STATUS_COLORS: Record<string, string> = {
  initiated: '#F2B01E',
  succeeded: '#0A6A1B',
  failed: '#A71930',
  needs_review: '#8B4513',
  refund_pending: '#1a6b8a',
  refunded: '#566357',
}

function StatusBadge({ status }: { status: string }) {
  return <span className="adm-badge" style={{ background: STATUS_COLORS[status] ?? '#566357' }}>{status.replace('_', ' ')}</span>
}

export function AdminPayments() {
  const [items, setItems] = useState<AdminPaymentListItem[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const load = useCallback(async (filter: string, cur: string | null, append: boolean) => {
    setLoading(true)
    setErr('')
    try {
      const page = await adminListPayments({ status: filter || undefined, cursor: cur })
      setItems(prev => append ? [...prev, ...page.items] : page.items)
      setCursor(page.next_cursor)
      setHasMore(page.next_cursor !== null)
    } catch {
      setErr('Could not load payments.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load(statusFilter, null, false) }, [statusFilter, load])

  return (
    <div className="adm-section">
      <div className="adm-section-hdr">
        <h1>Payments</h1>
        <select className="adm-select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          {STATUS_FILTERS.map(s => <option key={s} value={s}>{s || 'All statuses'}</option>)}
        </select>
      </div>
      {err && <p className="err">{err}</p>}
      <table className="adm-table">
        <thead>
          <tr><th>#</th><th>Order</th><th>Status</th><th>Amount</th><th>Reference</th><th>Created</th></tr>
        </thead>
        <tbody>
          {items.map(p => (
            <tr key={p.id}>
              <td>{p.id}</td>
              <td>{p.order_id}</td>
              <td><StatusBadge status={p.status} /></td>
              <td>{naira(p.amount_minor)}</td>
              <td><code className="adm-ref">{p.reference.slice(0, 16)}…</code></td>
              <td>{new Date(p.created_at).toLocaleDateString('en-NG')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 && !loading && <p className="note">No payments found.</p>}
      {hasMore && (
        <button className="btn ghost sm" disabled={loading} onClick={() => void load(statusFilter, cursor, true)}>
          {loading ? 'Loading…' : 'Load more'}
        </button>
      )}
    </div>
  )
}
