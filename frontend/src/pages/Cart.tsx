import { naira } from '../api'
import { A } from '../router'
import { Plate } from '../components/Plate'
import { Qty } from './Detail'
import { useCart, useCatalog } from '../store'

export const Row = ({ a, b, bold }: { a: string; b: string; bold?: boolean }) => (
  <div className={'row' + (bold ? ' bold' : '')}>
    <span>{a}</span>
    <span>{b}</span>
  </div>
)

export function Cart() {
  const { lines, setQty, remove, itemsTotalMinor } = useCart()
  const { items, store } = useCatalog()
  const itemByKey = (key: string, id: number, kind: string) =>
    items.find((i) => i.key === key) ?? items.find((i) => i.kind === kind && i.id === id)

  const hasFood = lines.some((l) => l.kind === 'food')
  const fee = hasFood ? (store?.delivery_fee_minor ?? 0) : 0
  const total = itemsTotalMinor + fee

  if (!lines.length)
    return (
      <div className="wrap page empty">
        <h1 className="h2">Your cart is empty</h1>
        <p>Pick a meal or request a service to get started.</p>
        <A to="/menu" className="btn lg">
          Browse the menu
        </A>
      </div>
    )

  return (
    <div className="wrap page">
      <h1 className="h2">Your cart</h1>
      <div className="two">
        <div className="lines">
          {lines.map((line) => {
            const item = itemByKey(line.key, line.id, line.kind)
            return (
              <div className="line" key={line.key}>
                {item ? (
                  <Plate item={item} />
                ) : (
                  <div className="plate" aria-hidden />
                )}
                <div className="line-i">
                  <h3>{line.name}</h3>
                  <p>
                    {line.kind === 'service'
                      ? line.preferred_date
                        ? 'Preferred date: ' + line.preferred_date
                        : 'Service request'
                      : 'Meal'}
                  </p>
                  <div className="line-c">
                    {line.kind === 'food' ? (
                      <Qty v={line.qty} set={(n) => setQty(line.key, n)} />
                    ) : (
                      <span />
                    )}
                    <button className="lnk" onClick={() => remove(line.key)}>
                      Remove
                    </button>
                  </div>
                </div>
                <strong>
                  {line.kind === 'service'
                    ? 'On request'
                    : naira(line.unit_price_minor * line.qty)}
                </strong>
              </div>
            )
          })}
        </div>
        <aside className="sum">
          <h2>Summary</h2>
          <Row a="Subtotal" b={naira(itemsTotalMinor)} />
          <Row a="Delivery fee (if chosen)" b={naira(fee)} />
          <Row a="Total" b={naira(total)} bold />
          <p className="note">
            Services are quoted separately. Final delivery fee is set at checkout; pickup
            is free.
          </p>
          <A to="/checkout" className="btn lg block">
            Proceed to checkout
          </A>
          <A to="/menu" className="lnk c">
            Continue shopping
          </A>
        </aside>
      </div>
    </div>
  )
}
