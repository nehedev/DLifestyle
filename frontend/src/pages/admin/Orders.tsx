import { useCallback, useEffect, useState } from 'react'
import {
  adminGetOrder,
  adminListOrders,
  adminSetOrderStatus,
  naira,
} from '../../api'
import type { AdminOrderDetail, AdminOrderListItem } from '../../api'

const STATUS_COLORS: Record<string, string> = {
  pending: '#F2B01E',
  paid: '#0A6A1B',
  preparing: '#1a6b8a',
  ready: '#5b2d8e',
  completed: '#566357',
  cancelled: '#A71930',
}

const NEXT_STATUSES: Record<string, ('preparing' | 'ready' | 'completed' | 'cancelled')[]> = {
  paid: ['preparing', 'cancelled'],
  preparing: ['ready', 'cancelled'],
  ready: ['completed'],
}

const STATUS_FILTERS = ['', 'pending', 'paid', 'preparing', 'ready', 'completed', 'cancelled']

function StatusBadge({ status }: { status: string }) {
  return (
    <span className="adm-badge" style={{ background: STATUS_COLORS[status] ?? '#566357' }}>
      {status}
    </span>
  )
}

function OrderDrawer({
  orderId,
  onClose,
  onUpdated,
}: {
  orderId: number
  onClose: () => void
  onUpdated: (o: AdminOrderDetail) => void
}) {
  const [order, setOrder] = useState<AdminOrderDetail | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    adminGetOrder(orderId)
      .then(setOrder)
      .catch(() => setErr('Could not load order.'))
  }, [orderId])

  const advance = async (status: 'preparing' | 'ready' | 'completed' | 'cancelled') => {
    if (!order) return
    setBusy(true)
    setErr('')
    try {
      const updated = await adminSetOrderStatus(order.id, status)
      setOrder(updated)
      onUpdated(updated)
    } catch {
      setErr('That transition is not allowed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="adm-overlay" onClick={onClose}>
      <aside className="adm-drawer" onClick={e => e.stopPropagation()}>
        <div className="adm-drawer-hdr">
          <h2>Order #{orderId}</h2>
          <button className="adm-close" onClick={onClose} aria-label="Close">
            <iconify-icon icon="lucide:x" />
          </button>
        </div>
        {!order && !err && <p className="note">Loading…</p>}
        {err && <p className="err">{err}</p>}
        {order && (
          <>
            <div className="adm-meta">
              <span><b>Status</b> <StatusBadge status={order.status} /></span>
              <span><b>Type</b> {order.fulfillment_type}</span>
              <span><b>Date</b> {order.fulfillment_date}</span>
              <span><b>Customer</b> {order.contact.name}</span>
              <span><b>Phone</b> {order.contact.phone}</span>
              {order.contact.address && <span><b>Address</b> {order.contact.address}</span>}
              {order.notes && <span><b>Notes</b> {order.notes}</span>}
            </div>
            <table className="adm-table">
              <thead><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Line</th></tr></thead>
              <tbody>
                {order.items.map(item => (
                  <tr key={item.id}>
                    <td>{item.name}</td>
                    <td>{item.quantity}</td>
                    <td>{naira(item.unit_price_minor)}</td>
                    <td>{naira(item.unit_price_minor * item.quantity)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr><td colSpan={3}><b>Delivery fee</b></td><td>{naira(order.delivery_fee_minor)}</td></tr>
                <tr><td colSpan={3}><b>Total</b></td><td><b>{naira(order.total_minor)}</b></td></tr>
              </tfoot>
            </table>
            <div className="adm-meta" style={{ marginTop: 16 }}>
              <span><b>Payments</b></span>
              {order.payments.length === 0 && <span className="note">None yet.</span>}
              {order.payments.map(p => (
                <span key={p.id}>
                  #{p.id} — <StatusBadge status={p.status} /> — {naira(p.amount_minor)}
                  {p.reference && <> · <code>{p.reference.slice(0, 12)}…</code></>}
                </span>
              ))}
            </div>
            {(NEXT_STATUSES[order.status]?.length ?? 0) > 0 && (
              <div className="adm-actions">
                {NEXT_STATUSES[order.status].map(s => (
                  <button
                    key={s}
                    className={`btn sm ${s === 'cancelled' ? 'red' : ''}`}
                    disabled={busy}
                    onClick={() => void advance(s)}
                  >
                    Mark {s}
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </aside>
    </div>
  )
}

export function AdminOrders() {
  const [items, setItems] = useState<AdminOrderListItem[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [selected, setSelected] = useState<number | null>(null)

  const load = useCallback(async (filter: string, cur: string | null, append: boolean) => {
    setLoading(true)
    setErr('')
    try {
      const page = await adminListOrders({ status: filter || undefined, cursor: cur })
      setItems(prev => append ? [...prev, ...page.items] : page.items)
      setCursor(page.next_cursor)
      setHasMore(page.next_cursor !== null)
    } catch {
      setErr('Could not load orders.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load(statusFilter, null, false) }, [statusFilter, load])

  const handleUpdated = (updated: AdminOrderDetail) => {
    setItems(prev => prev.map(o => o.id === updated.id
      ? { ...o, status: updated.status }
      : o,
    ))
  }

  return (
    <div className="adm-section">
      <div className="adm-section-hdr">
        <h1>Orders</h1>
        <select
          className="adm-select"
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
        >
          {STATUS_FILTERS.map(s => (
            <option key={s} value={s}>{s || 'All statuses'}</option>
          ))}
        </select>
      </div>
      {err && <p className="err">{err}</p>}
      <table className="adm-table">
        <thead>
          <tr>
            <th>#</th><th>Status</th><th>Type</th><th>Date</th><th>Total</th><th>Created</th><th></th>
          </tr>
        </thead>
        <tbody>
          {items.map(o => (
            <tr key={o.id}>
              <td>{o.id}</td>
              <td><StatusBadge status={o.status} /></td>
              <td>{o.fulfillment_type}</td>
              <td>{o.fulfillment_date}</td>
              <td>{naira(o.total_minor)}</td>
              <td>{new Date(o.created_at).toLocaleDateString('en-NG')}</td>
              <td>
                <button className="btn sm" onClick={() => setSelected(o.id)}>View</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 && !loading && <p className="note">No orders found.</p>}
      {hasMore && (
        <button className="btn ghost sm" disabled={loading} onClick={() => void load(statusFilter, cursor, true)}>
          {loading ? 'Loading…' : 'Load more'}
        </button>
      )}
      {selected !== null && (
        <OrderDrawer
          orderId={selected}
          onClose={() => setSelected(null)}
          onUpdated={handleUpdated}
        />
      )}
    </div>
  )
}
