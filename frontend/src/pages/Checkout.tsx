import { useEffect, useRef, useState } from 'react'
import { ApiError, naira, createOrder, createServiceRequest, payOrder } from '../api'
import { toE164 } from '../data'
import { A } from '../router'
import { Row } from './Cart'
import { useCart, useCatalog } from '../store'
import { useSession } from '../auth'

function friendlyError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.detail === 'ordering_closed_for_date')
      return 'That date is closed. Pick another day or check the cutoff time.'
    if (error.detail === 'store_not_configured')
      return 'Ordering is not open yet. Please check back soon.'
    if (typeof error.detail === 'string') return error.detail.replace(/_/g, ' ')
    if (error.detail && typeof error.detail === 'object')
      return 'Some items are no longer available. Please review your cart.'
    return `Request failed (${error.status}).`
  }
  return 'Something went wrong. Please try again.'
}

function tomorrow(): string {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  return date.toISOString().slice(0, 10)
}

/** Today's date as YYYY-MM-DD in an IANA timezone. */
function todayIn(timezone: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

function addDays(isoDate: string, days: number): string {
  const date = new Date(isoDate + 'T00:00:00Z')
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

export function Checkout() {
  const { lines, itemsTotalMinor, clear } = useCart()
  const { store } = useCatalog()
  const { isAuthenticated, login, isLoading } = useSession()
  const idempotencyKey = useRef(crypto.randomUUID())
  const [form, setForm] = useState({
    name: '',
    phone: '',
    address: '',
    location: '',
    details: '',
    notes: '',
  })
  const [mode, setMode] = useState<'delivery' | 'pickup'>('delivery')
  const [date, setDate] = useState(tomorrow())
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const minDate = store ? todayIn(store.timezone) : undefined
  const maxDate = store ? addDays(todayIn(store.timezone), store.max_advance_days) : undefined

  useEffect(() => {
    if (!minDate || !maxDate) return
    setDate((current) =>
      current < minDate ? minDate : current > maxDate ? maxDate : current,
    )
  }, [minDate, maxDate])

  const foodLines = lines.filter((l) => l.kind === 'food')
  const serviceLines = lines.filter((l) => l.kind === 'service')
  const fee = mode === 'delivery' && foodLines.length ? (store?.delivery_fee_minor ?? 0) : 0
  const total = itemsTotalMinor + fee

  if (!lines.length)
    return (
      <div className="wrap page empty">
        <p>Your cart is empty.</p>
        <A to="/menu" className="btn">
          Browse the menu
        </A>
      </div>
    )

  const set =
    (key: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm({ ...form, [key]: e.target.value })

  const submit = async () => {
    setErr('')
    if (!form.name.trim()) return setErr('Enter your full name.')
    const phone = toE164(form.phone)
    if (!phone) return setErr('Enter a valid Nigerian phone number, e.g. 0708 734 9937.')
    if (foodLines.length && mode === 'delivery' && !form.address.trim())
      return setErr('Enter your address so we know where to deliver.')
    if (serviceLines.length && !form.location.trim())
      return setErr('Tell us the location for the service.')
    if (serviceLines.length && !form.details.trim())
      return setErr('Describe what you need done.')
    if (!isAuthenticated) {
      login()
      return
    }

    setBusy(true)
    try {
      for (const line of serviceLines) {
        await createServiceRequest({
          service_id: line.id,
          preferred_date: line.preferred_date ?? null,
          location: form.location,
          details: form.details,
          contact_phone: phone,
        })
      }

      if (foodLines.length) {
        const order = await createOrder(
          {
            items: foodLines.map((l) => ({ menu_item_id: l.id, quantity: l.qty })),
            fulfillment_type: mode,
            fulfillment_date: date,
            contact: {
              name: form.name,
              phone,
              address: mode === 'delivery' ? form.address : null,
            },
            notes: form.notes || null,
          },
          idempotencyKey.current,
        )
        const { authorization_url } = await payOrder(order.id)
        localStorage.setItem('damis.lastOrderId', String(order.id))
        clear()
        window.location.href = authorization_url
        return
      }

      clear()
      location.hash = '/requests'
    } catch (error) {
      setErr(friendlyError(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="wrap page">
      <h1 className="h2">Checkout</h1>
      <div className="two">
        <div className="form">
          <section>
            <h2>Your details</h2>
            <label className="fld">
              Full name
              <input className="inp" autoComplete="name" value={form.name} onChange={set('name')} />
            </label>
            <label className="fld">
              Phone number
              <input
                className="inp"
                inputMode="tel"
                autoComplete="tel"
                placeholder="0708 734 9937"
                value={form.phone}
                onChange={set('phone')}
              />
            </label>
          </section>

          {foodLines.length > 0 && (
            <section>
              <h2>Delivery</h2>
              <div className="radios">
                {(
                  [
                    ['delivery', 'Delivery', naira(store?.delivery_fee_minor ?? 0)],
                    ['pickup', 'Pickup', 'Free'],
                  ] as const
                ).map(([value, label, price]) => (
                  <label key={value} className={mode === value ? 'on' : ''}>
                    <input
                      type="radio"
                      name="m"
                      checked={mode === value}
                      onChange={() => setMode(value)}
                    />
                    {label}
                    <span>{price}</span>
                  </label>
                ))}
              </div>
              {mode === 'delivery' && (
                <label className="fld">
                  Address
                  <input
                    className="inp"
                    autoComplete="street-address"
                    value={form.address}
                    onChange={set('address')}
                  />
                </label>
              )}
              <label className="fld">
                Fulfillment date
                <input
                  className="inp"
                  type="date"
                  value={date}
                  min={minDate}
                  max={maxDate}
                  onChange={(e) => setDate(e.target.value)}
                />
              </label>
              <label className="fld">
                Notes for Dami (optional)
                <textarea
                  className="inp"
                  rows={3}
                  placeholder="Spice level, gate code…"
                  value={form.notes}
                  onChange={set('notes')}
                />
              </label>
            </section>
          )}

          {serviceLines.length > 0 && (
            <section>
              <h2>Service details</h2>
              <label className="fld">
                Location
                <input className="inp" value={form.location} onChange={set('location')} />
              </label>
              <label className="fld">
                What do you need done?
                <textarea className="inp" rows={3} value={form.details} onChange={set('details')} />
              </label>
            </section>
          )}
        </div>

        <aside className="sum">
          <h2>Order summary</h2>
          {foodLines.map((l) => (
            <Row key={l.key} a={`${l.qty} × ${l.name}`} b={naira(l.unit_price_minor * l.qty)} />
          ))}
          {serviceLines.map((l) => (
            <Row key={l.key} a={l.name} b="On request" />
          ))}
          <hr />
          <Row a="Subtotal" b={naira(itemsTotalMinor)} />
          <Row a="Delivery fee" b={naira(fee)} />
          <Row a="Total" b={naira(total)} bold />
          {err && (
            <p className="err" role="alert">
              {err}
            </p>
          )}
          <button className="btn lg block" onClick={submit} disabled={busy || isLoading}>
            {busy ? 'Working…' : foodLines.length ? `Pay ${naira(total)}` : 'Send request'}
          </button>
          <p className="note c">
            {isAuthenticated
              ? 'Secure payment by card or transfer. You will get a confirmation.'
              : 'You will be asked to sign in before we take your order.'}
          </p>
        </aside>
      </div>
    </div>
  )
}
