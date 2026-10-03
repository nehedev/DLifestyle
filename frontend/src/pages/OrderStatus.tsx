import { useCallback, useEffect, useState } from 'react'
import { naira, getOrder, cancelOrder } from '../api'
import type { OrderResponse } from '../api'
import { PHONE } from '../data'
import { A } from '../router'
import { Row } from './Cart'
import { useSession } from '../auth'

export function OrderStatus({ orderId }: { orderId: number }) {
  const { isAuthenticated, login } = useSession()
  const [order, setOrder] = useState<OrderResponse | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setOrder(await getOrder(orderId))
    } catch {
      setError('We could not load that order.')
    }
  }, [orderId])

  useEffect(() => {
    if (isAuthenticated) void load()
  }, [isAuthenticated, load])

  if (!isAuthenticated)
    return (
      <div className="wrap page empty">
        <p>Sign in to see your order.</p>
        <button className="btn" onClick={login}>
          Sign in
        </button>
      </div>
    )
  if (error)
    return (
      <div className="wrap page empty">
        <p>{error}</p>
        <A to="/menu" className="btn">
          Back to menu
        </A>
      </div>
    )
  if (!order) return <div className="wrap page"><p>Loading your order…</p></div>

  const paid = order.status !== 'pending' && order.status !== 'cancelled'
  const cancel = async () => {
    setBusy(true)
    try {
      setOrder(await cancelOrder(order.id))
    } catch {
      setError('That order can no longer be cancelled.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="wrap page conf">
      <div className="ok" aria-hidden>
        ✓
      </div>
      <h1 className="h2">
        {paid
          ? `Payment confirmed. Thank you, ${order.contact.name.split(' ')[0]}.`
          : order.status === 'cancelled'
            ? 'This order was cancelled.'
            : `Order ${order.id} received.`}
      </h1>
      <p className="lead">
        {paid
          ? 'We are preparing your order.'
          : order.status === 'pending'
            ? 'We are confirming your payment. This page updates as soon as the gateway reports back.'
            : 'No payment was taken.'}
      </p>
      <div className="sum wide">
        {order.items.map((item) => (
          <Row
            key={item.name}
            a={`${item.quantity} × ${item.name}`}
            b={naira(item.unit_price_minor * item.quantity)}
          />
        ))}
        <hr />
        <Row a="Items" b={naira(order.items_total_minor)} />
        <Row a="Delivery" b={naira(order.delivery_fee_minor)} />
        <Row a="Total" b={naira(order.total_minor)} bold />
        <Row a="Status" b={order.status} />
        <Row
          a={order.fulfillment_type === 'pickup' ? 'Pickup' : 'Delivery address'}
          b={
            order.fulfillment_type === 'pickup'
              ? 'We will message you when ready'
              : (order.contact.address ?? '')
          }
        />
        <Row a="Fulfillment date" b={order.fulfillment_date} />
      </div>
      <div className="next">
        <h2>What happens next</h2>
        <p>
          {order.fulfillment_type === 'pickup'
            ? 'We will message ' + order.contact.phone + ' when your order is ready.'
            : 'We will contact ' + order.contact.phone + ' about delivery.'}
        </p>
        <div className="cta">
          <button className="btn" onClick={() => void load()} disabled={busy}>
            Refresh
          </button>
          {order.status === 'pending' && (
            <button className="btn ghost" onClick={cancel} disabled={busy}>
              Cancel order
            </button>
          )}
          <a className="btn ghost" href={'tel:' + PHONE}>
            Call {PHONE}
          </a>
          <A to="/menu" className="btn ghost">
            Order more
          </A>
        </div>
      </div>
    </div>
  )
}

export function LastOrder() {
  const stored =
    typeof localStorage === 'undefined' ? null : localStorage.getItem('damis.lastOrderId')
  const orderId = stored ? Number(stored) : null
  if (!orderId)
    return (
      <div className="wrap page empty">
        <p>No recent order.</p>
        <A to="/menu" className="btn">
          Browse the menu
        </A>
      </div>
    )
  return <OrderStatus orderId={orderId} />
}
