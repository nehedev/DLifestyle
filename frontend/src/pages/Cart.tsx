import { ADDONS, naira } from '../data'
import { A } from '../router'
import { Plate } from '../components/Plate'
import { Qty } from './Detail'
import { Line, itemOf, unit, fees } from '../types'

export const Row = ({ a, b, bold }: { a: string; b: string; bold?: boolean }) => (
  <div className={'row' + (bold ? ' bold' : '')}><span>{a}</span><span>{b}</span></div>
)

export function Cart({ lines, setLines }: { lines: Line[]; setLines: (l: Line[]) => void }) {
  const sub = lines.reduce((s, l) => s + unit(l) * l.qty, 0)
  const fee = fees(lines, 'delivery')

  if (!lines.length) return (
    <div className="wrap page empty">
      <h1 className="h2">Your cart is empty</h1>
      <p>Pick a meal or request a service to get started.</p>
      <A to="/menu" className="btn lg">Browse the menu</A>
    </div>
  )

  return (
    <div className="wrap page">
      <h1 className="h2">Your cart</h1>
      <div className="two">
        <div className="lines">
          {lines.map(l => {
            const it = itemOf(l.id)
            return (
              <div className="line" key={l.key}>
                <Plate item={it} />
                <div className="line-i">
                  <h3>{it.name}</h3>
                  <p>{l.addons.map((a: string) => ADDONS.find(x => x.id === a)!.label).join(', ') ||
                    (it.kind === 'service' ? (l.date ? 'Preferred date: ' + l.date : 'Service request') : 'No add-ons')}</p>
                  <div className="line-c">
                    {it.kind === 'food'
                      ? <Qty v={l.qty} set={n => setLines(lines.map(x => x.key === l.key ? { ...x, qty: n } : x))} />
                      : <span />}
                    <button className="lnk" onClick={() => setLines(lines.filter(x => x.key !== l.key))}>Remove</button>
                  </div>
                </div>
                <strong>{naira(unit(l) * l.qty)}</strong>
              </div>
            )
          })}
        </div>
        <aside className="sum">
          <h2>Summary</h2>
          <Row a="Subtotal" b={naira(sub)} />
          <Row a="Delivery / service fee" b={naira(fee)} />
          <Row a="Total" b={naira(sub + fee)} bold />
          <p className="note">Delivery fee is final at checkout. Pickup is free.</p>
          <A to="/checkout" className="btn lg block">Proceed to checkout</A>
          <A to="/menu" className="lnk c">Continue shopping</A>
        </aside>
      </div>
    </div>
  )
}
