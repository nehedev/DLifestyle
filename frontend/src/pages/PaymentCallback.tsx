import { useEffect, useRef, useState } from 'react'
import { getOrder, naira } from '../api'
import type { OrderResponse } from '../api'
import { A } from '../router'
import { useSession } from '../auth'

type Phase = 'processing' | 'success' | 'failed'

const POLL_INTERVAL_MS = 3000
const MAX_POLLS = 20 // ~60 seconds total

function phaseFromOrder(order: OrderResponse): Phase {
  if (order.status === 'cancelled') return 'failed'
  if (order.status === 'pending') return 'processing'
  // paid, preparing, ready, completed → success
  return 'success'
}

export function PaymentCallback() {
  const { isAuthenticated, isLoading, login } = useSession()

  const orderId = useRef<number | null>(null)
  if (orderId.current === null) {
    const raw = localStorage.getItem('damis.lastOrderId')
    orderId.current = raw ? Number(raw) : null
  }

  const [phase, setPhase] = useState<Phase>('processing')
  const [order, setOrder] = useState<OrderResponse | null>(null)
  const [errMsg, setErrMsg] = useState('')
  const polls = useRef(0)
  const stopped = useRef(false)

  useEffect(() => {
    // Don't start polling until auth state is resolved
    if (isLoading) return

    if (!isAuthenticated) {
      setPhase('failed')
      setErrMsg('You need to be signed in to confirm your payment.')
      return
    }

    const id = orderId.current

    if (!id) {
      setPhase('failed')
      setErrMsg('No recent order found. Check your orders page for the status.')
      return
    }

    stopped.current = false
    polls.current = 0

    const poll = async () => {
      if (stopped.current) return
      try {
        const o = await getOrder(id)
        if (stopped.current) return
        setOrder(o)
        const p = phaseFromOrder(o)
        setPhase(p)
        if (p === 'processing') {
          if (polls.current < MAX_POLLS) {
            polls.current += 1
            setTimeout(() => { void poll() }, POLL_INTERVAL_MS)
          } else {
            setErrMsg(
              'Payment is taking longer than expected. ' +
              'Check your orders page for the final status.',
            )
          }
        }
      } catch (e: unknown) {
        if (stopped.current) return
        const status = (e as { status?: number }).status
        if (status === 401) {
          setPhase('failed')
          setErrMsg('Your session expired. Please sign in and check your orders.')
        } else {
          setPhase('failed')
          setErrMsg('We could not confirm your payment. Check your orders page.')
        }
      }
    }

    void poll()
    return () => { stopped.current = true }
  }, [isAuthenticated, isLoading])

  // Waiting for auth to settle
  if (isLoading) {
    return (
      <div className="pcb-backdrop">
        <div className="pcb-card">
          <div className="pcb-spinner" aria-hidden />
          <h2>Loading…</h2>
        </div>
      </div>
    )
  }

  // Not signed in
  if (!isAuthenticated) {
    return (
      <div className="pcb-backdrop">
        <div className="pcb-card pcb-failed">
          <div className="pcb-icon pcb-icon-fail" aria-hidden>!</div>
          <h2>Sign in to confirm</h2>
          <p>Your payment may have gone through. Sign in to check.</p>
          <div className="pcb-actions">
            <button className="btn lg" onClick={login}>Sign in</button>
            <A to="/menu" className="btn ghost lg">Back to menu</A>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="pcb-backdrop">
      <div className={`pcb-card pcb-${phase}`} role="status" aria-live="polite">

        {phase === 'processing' && (
          <>
            <div className="pcb-spinner" aria-hidden />
            <h2>Confirming your payment…</h2>
            <p>Please wait. Do not close this page.</p>
            {errMsg && <p className="note">{errMsg}</p>}
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
            <p>
              {errMsg ||
                'Something went wrong. No payment was taken. You can try again from your orders page.'}
            </p>
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
