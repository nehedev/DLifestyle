import { useEffect, useRef, useState } from 'react'
import { getOrder, naira } from '../api'
import type { OrderResponse } from '../api'
import { A } from '../router'

type Phase = 'processing' | 'success' | 'failed'

const POLL_INTERVAL_MS = 2500
const MAX_POLLS = 16 // ~40 seconds before we give up

function phaseFromOrder(order: OrderResponse): Phase {
  if (order.status === 'cancelled') return 'failed'
  if (order.status === 'pending') return 'processing'
  return 'success'
}

export function PaymentCallback() {
  const orderId = (() => {
    const raw = localStorage.getItem('damis.lastOrderId')
    return raw ? Number(raw) : null
  })()

  const [phase, setPhase] = useState<Phase>('processing')
  const [order, setOrder] = useState<OrderResponse | null>(null)
  const [errMsg, setErrMsg] = useState('')
  const polls = useRef(0)

  useEffect(() => {
    if (!orderId) {
      setPhase('failed')
      setErrMsg('No recent order found.')
      return
    }

    let cancelled = false

    const poll = async () => {
      try {
        const o = await getOrder(orderId)
        if (cancelled) return
        setOrder(o)
        const p = phaseFromOrder(o)
        setPhase(p)
        if (p === 'processing' && polls.current < MAX_POLLS) {
          polls.current += 1
          setTimeout(() => { void poll() }, POLL_INTERVAL_MS)
        } else if (p === 'processing') {
          // Timed out — still show as processing but stop polling
          setPhase('processing')
          setErrMsg('Payment is taking longer than expected. Check your orders page for the final status.')
        }
      } catch {
        if (!cancelled) {
          setPhase('failed')
          setErrMsg('We could not confirm your payment. Check your orders page.')
        }
      }
    }

    void poll()
    return () => { cancelled = true }
  }, [orderId])

  return (
    <div className="pcb-backdrop">
      <div className={`pcb-card pcb-${phase}`} role="status" aria-live="polite">
        {phase === 'processing' && (
          <>
            <div className="pcb-spinner" aria-hidden />
            <h2>Confirming your payment…</h2>
            <p>Please wait. Do not close this page.</p>
          </>
        )}

        {phase === 'success' && order && (
          <>
            <div className="pcb-icon pcb-icon-ok" aria-hidden>✓</div>
            <h2>Payment confirmed!</h2>
            <p>Thank you, {order.contact.name.split(' ')[0]}. Your order is in.</p>
            <div className="pcb-summary">
              {order.items.map(item => (
                <div className="pcb-row" key={item.name}>
                  <span>{item.quantity} × {item.name}</span>
                  <span>{naira(item.unit_price_minor * item.quantity)}</span>
                </div>
              ))}
              <div className="pcb-row pcb-row-total">
                <span>Total</span>
                <span>{naira(order.total_minor)}</span>
              </div>
              <div className="pcb-row">
                <span>{order.fulfillment_type === 'pickup' ? 'Pickup' : 'Delivery'}</span>
                <span>{order.fulfillment_date}</span>
              </div>
            </div>
            <div className="pcb-actions">
              <A to="/requests" className="btn lg">View my orders</A>
              <A to="/menu" className="btn ghost lg">Order more</A>
            </div>
          </>
        )}

        {phase === 'failed' && (
          <>
            <div className="pcb-icon pcb-icon-fail" aria-hidden>✕</div>
            <h2>Payment not confirmed</h2>
            <p>{errMsg || 'Something went wrong. No payment was taken. You can try again from your orders page.'}</p>
            <div className="pcb-actions">
              <A to="/requests" className="btn lg">My orders</A>
              <A to="/menu" className="btn ghost lg">Back to menu</A>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
