import { useState } from 'react'
import { naira } from '../data'
import { A } from '../router'
import { Line, Order, itemOf, unit, fees } from '../types'
import { Row } from './Cart'

export function Checkout({ lines, done }: { lines: Line[]; done: (o: Order) => void }) {
  const [f, setF] = useState({ name: '', phone: '', email: '', address: '', notes: '' })
  const [mode, setMode] = useState('delivery')
  const [pay, setPay] = useState('card')
  const [err, setErr] = useState('')

  const hasF = lines.some(l => itemOf(l.id).kind === 'food')
  const sub = lines.reduce((s, l) => s + unit(l) * l.qty, 0)
  const total = sub + fees(lines, mode)

  if (!lines.length) return (
    <div className="wrap page empty">
      <p>Your cart is empty.</p>
      <A to="/menu" className="btn">Browse the menu</A>
    </div>
  )

  const needAddr = mode === 'delivery' || lines.some(l => itemOf(l.id).kind === 'service')
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value })

  const submit = () => {
    if (!f.name.trim()) return setErr('Enter your full name.')
    if (!/^(\+?234|0)[789]\d{9}$/.test(f.phone.replace(/\s/g, '')))
      return setErr('Enter a valid Nigerian phone number, e.g. 0708 734 9937.')
    if (needAddr && !f.address.trim()) return setErr('Enter your address so we know where to come.')
    done({
      no: 'DLS-' + Math.floor(10000 + Math.random() * 89999),
      lines, total,
      name: f.name, phone: f.phone, address: f.address, mode, pay,
    })
  }

  return (
    <div className="wrap page">
      <h1 className="h2">Checkout</h1>
      <div className="two">
        <div className="form">
          <section>
            <h2>Your details</h2>
            <label className="fld">Full name<input className="inp" autoComplete="name" value={f.name} onChange={set('name')} /></label>
            <div className="r2">
              <label className="fld">Phone number<input className="inp" inputMode="tel" autoComplete="tel" placeholder="0708 734 9937" value={f.phone} onChange={set('phone')} /></label>
              <label className="fld">Email (optional)<input className="inp" type="email" value={f.email} onChange={set('email')} /></label>
            </div>
          </section>
          <section>
            <h2>{hasF ? 'Delivery' : 'Service'}</h2>
            {hasF && (
              <div className="radios">
                {[['delivery', 'Delivery', '₦1,500'], ['pickup', 'Pickup', 'Free']].map(([v, l, p]) => (
                  <label key={v} className={mode === v ? 'on' : ''}>
                    <input type="radio" name="m" checked={mode === v} onChange={() => setMode(v)} />{l}<span>{p}</span>
                  </label>
                ))}
              </div>
            )}
            {needAddr && <label className="fld">Address<input className="inp" autoComplete="street-address" value={f.address} onChange={set('address')} /></label>}
            <label className="fld">Notes for Dami (optional)<textarea className="inp" rows={3} placeholder="Gate code, spice level, rooms to clean…" value={f.notes} onChange={set('notes')} /></label>
          </section>
          <section>
            <h2>Payment</h2>
            <div className="radios">
              {[['card', 'Card', 'Paystack'], ['transfer', 'Bank transfer', 'Instant'], ['cod', 'Pay on delivery', 'Cash or transfer']].map(([v, l, p]) => (
                <label key={v} className={pay === v ? 'on' : ''}>
                  <input type="radio" name="p" checked={pay === v} onChange={() => setPay(v)} />{l}<span>{p}</span>
                </label>
              ))}
            </div>
          </section>
        </div>
        <aside className="sum">
          <h2>Order summary</h2>
          {lines.map(l => <Row key={l.key} a={`${l.qty} × ${itemOf(l.id).name}`} b={naira(unit(l) * l.qty)} />)}
          <hr />
          <Row a="Subtotal" b={naira(sub)} />
          <Row a="Delivery / service fee" b={naira(total - sub)} />
          <Row a="Total" b={naira(total)} bold />
          {err && <p className="err" role="alert">{err}</p>}
          <button className="btn lg block" onClick={submit}>
            {pay === 'cod' ? 'Place order' : `Pay ${naira(total)}`}
          </button>
          <p className="note c">Secure payment. You'll get a confirmation straight away.</p>
        </aside>
      </div>
    </div>
  )
}
