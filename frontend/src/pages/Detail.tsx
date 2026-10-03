import { useState } from 'react'
import { naira } from '../api'
import { A } from '../router'
import { Plate } from '../components/Plate'
import { Card } from './Catalog'
import { useCart, useCatalogItem, useCatalog } from '../store'

export const Qty = ({ v, set }: { v: number; set: (n: number) => void }) => (
  <div className="qty">
    <button aria-label="Decrease" onClick={() => set(Math.max(1, v - 1))}>
      −
    </button>
    <span>{v}</span>
    <button aria-label="Increase" onClick={() => set(v + 1)}>
      +
    </button>
  </div>
)

export function Detail({ id }: { id: string }) {
  const item = useCatalogItem(id)
  const { items } = useCatalog()
  const { add } = useCart()
  const [qty, setQty] = useState(1)
  const [date, setDate] = useState('')

  if (!item)
    return (
      <div className="wrap page">
        <p>Item not found.</p>
        <A to="/menu" className="btn">
          Back to menu
        </A>
      </div>
    )

  const svc = item.kind === 'service'
  const related = items.filter((i) => i.kind === item.kind && i.key !== id).slice(0, 4)

  const addToCart = () => {
    add(item, svc ? 1 : qty, svc ? date || undefined : undefined)
    location.hash = '/cart'
  }

  return (
    <div className="wrap page">
      <A to="/menu" className="lnk">
        ← Back to menu
      </A>
      <div className="detail">
        <Plate item={item} />
        <div>
          <div className="tag">{svc ? 'Service' : item.category}</div>
          <h1 className="h2">{item.name}</h1>
          <p className="lead">{item.desc}</p>
          <div className="price">
            {svc ? 'Price on request' : naira(item.price_minor ?? 0)}
          </div>
          {svc ? (
            <label className="fld">
              Preferred date
              <input
                className="inp"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </label>
          ) : (
            <p className="note">
              Tell us about spice level, protein choices or anything else in the notes at
              checkout.
            </p>
          )}
          {svc && (
            <p className="note">
              Final price is confirmed after we talk through your needs. You pay only
              after we agree.
            </p>
          )}
          <div className="buy">
            {!svc && <Qty v={qty} set={setQty} />}
            <button className="btn lg grow" disabled={item.sold_out} onClick={addToCart}>
              {item.sold_out
                ? 'Sold out'
                : svc
                  ? 'Request this service'
                  : `Add to cart · ${naira((item.price_minor ?? 0) * qty)}`}
            </button>
          </div>
        </div>
      </div>
      {related.length > 0 && (
        <>
          <h2 className="sub">You may also like</h2>
          <div className="grid4">
            {related.map((i) => (
              <Card key={i.key} item={i} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
