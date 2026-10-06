import { useEffect, useRef, useState } from 'react'
import { getOrder, naira } from '../api'
import type { OrderResponse } from '../api'
import { useSession } from '../auth'

type Phase = 'processing' | 'success' | 'failed' | 'timeout'

const POLL_INTERVAL_MS = 3000
const MAX_POLLS = 20 // ~60 seconds total

function phaseFromOrder(order: OrderResponse): Phase {
  if (order.status === 'cancelled') return 'failed'
  if (order.status === 'pending') return 'processing'
  return 'success'
}

/** Navigate to a hash route from a real-path page by replacing the whole URL. */
function goTo(hash: string) {
  window.location.href = `/${hash}`
}

export function PaymentCallback() {
  const { isAuthenticated, isLoading, login } = useSession()

  // Read orderId once on mount — stable ref, never changes
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
  // Track whether the token getter has been wired by the auth provider's useEffect.
  // We delay the first poll by one tick to let the auth useEffect run first.
  const [authReady, setAuthReady] = useState(false)

  // One tick after auth state settles, mark ready so the poll effect fires
  useEffect(() => {
    if (isLoading) return
    const id = setTimeout(() => setAuthReady(true), 0)
    return () => clearTimeout(id)
  }, [isLoading])

  useEffect(() => {
    if (!authReady) return
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
            setPhase('timeout')
          }
        }
      } catch (e: unknown) {
        if (stopped.current) return
        const s = (e as { status?: number }).status
        if (s === 401 || s === 403) {
          setPhase('failed')
          setErrMsg('Your session expired during the redirect. Sign in again to check your order.')
        } else {
          setPhase('failed')
          setErrMsg('We could not reach the server. Check your orders page for the status.')
        }
      }
    }

    void poll()
    return () => { stopped.current = true }
  }, [authReady, isAuthenticated])

  const retry = () => {
    setPhase('processing')
    setErrMsg('')
    setAuthReady(false)
    polls.current = 0
    setTimeout(() => setAuthReady(true), 0)
  }

  // ── Loading / auth settling ───────────────────────────────────────────────

  if (isLoading || !authReady) {
    return (
      <div className="pcb-backdrop">
        <div className="pcb-card">
          <div className="pcb-spinner" aria-hidden />
          <h2>Loading…</h2>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="pcb-backdrop">
        <div className="pcb-card">
          <div className="pcb-icon pcb-icon-fail" aria-hidden>!</div>
          <h2>Sign in to confirm</h2>
          <p>Your payment may have gone through. Sign in to check.</p>
          <div className="pcb-actions">
            <button className="btn lg" onClick={login}>Sign in</button>
            <button className="btn ghost lg" onClick={() => goTo('#/menu')}>Back to menu</button>
          </div>
        </div>
      </div>
    )
  }

  // ── Main states ───────────────────────────────────────────────────────────

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

        {phase === 'timeout' && (
          <>
            <div className="pcb-icon pcb-icon-warn" aria-hidden>⏱</div>
            <h2>Still waiting on the bank</h2>
            <p>
              Payment confirmation is taking longer than expected.
              Your order page has the latest status.
            </p>
            <div className="pcb-actions">
              <button className="btn lg" onClick={retry}>Check again</button>
              <button className="btn ghost lg" onClick={() => goTo('#/requests')}>My orders</button>
            </div>
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
              <button className="btn lg" onClick={() => goTo('#/requests')}>View my orders</button>
              <button className="btn ghost lg" onClick={() => goTo('#/menu')}>Order more</button>
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
              <button className="btn lg" onClick={retry}>Try again</button>
              <button className="btn ghost lg" onClick={() => goTo('#/requests')}>My orders</button>
              <button className="btn ghost lg" onClick={() => goTo('#/menu')}>Back to menu</button>
            </div>
          </>
        )}

      </div>
    </div>
  )
}
