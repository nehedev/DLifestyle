import { useState } from 'react'
import { ADDONS, ITEMS, naira } from '../data'
import { A } from '../router'
import { Plate } from '../components/Plate'
import { Card } from './Catalog'
import { Line } from '../types'

export const Qty = ({ v, set }: { v: number; set: (n: number) => void }) => (
  <div className="qty">
    <button aria-label="Decrease" onClick={() => set(Math.max(1, v - 1))}>−</button>
    <span>{v}</span>
    <button aria-label="Increase" onClick={() => set(v + 1)}>+</button>
  </div>
)

export function Detail({ id, add }: { id: string; add: (id: string, qty: number, addons: string[], date?: string) => void }) {
  const item = ITEMS.find(i => i.id === id)
  const [qty, setQty] = useState(1)
  const [ad, setAd] = useState<string[]>([])
  const [date, setDate] = useState('')

  if (!item) return <div className="wrap page"><p>Item not found.</p><A to="/menu" className="btn">Back to menu</A></div>

  const svc = item.kind === 'service'
  const price = item.price + ad.reduce((s, a) => s + ADDONS.find(x => x.id === a)!.price, 0)
  const related = ITEMS.filter(i => i.kind === item.kind && i.id !== id).slice(0, 4)

  const addToCart = () => {
    add(id, svc ? 1 : qty, ad, date)
    location.hash = '/cart'
  }

  return (
    <div className="wrap page">
      <A to="/menu" className="lnk">← Back to menu</A>
      <div className="detail">
        <Plate item={item} />
        <div>
          <div className="tag">{svc ? 'Service' : item.cat}</div>
          <h1 className="h2">{item.name}</h1>
          <p className="lead">{item.desc}</p>
          <div className="price">{svc ? 'From ' : ''}{naira(price)}</div>
          {svc
            ? <label className="fld">Preferred date<input className="inp" type="date" value={date} onChange={e => setDate(e.target.value)} /></label>
            : <fieldset className="opts">
                <legend>Add-ons</legend>
                {ADDONS.map(a => (
                  <label key={a.id}>
                    <input type="checkbox" checked={ad.includes(a.id)} onChange={() => setAd(ad.includes(a.id) ? ad.filter(x => x !== a.id) : [...ad, a.id])} />
                    {a.label}<span>+{naira(a.price)}</span>
                  </label>
                ))}
              </fieldset>}
          {svc && <p className="note">Final price is confirmed after we talk through your needs. You pay only after we agree.</p>}
          <div className="buy">
            {!svc && <Qty v={qty} set={setQty} />}
            <button className="btn lg grow" disabled={!item.available} onClick={addToCart}>
              {!item.available ? 'Sold out today' : svc ? 'Request this service' : `Add to cart · ${naira(price * qty)}`}
            </button>
          </div>
        </div>
      </div>
      <h2 className="sub">You may also like</h2>
      <div className="grid4">
        {related.map(i => <Card key={i.id} item={i} add={(q: string) => add(q, 1, [])} />)}
      </div>
    </div>
  )
}
