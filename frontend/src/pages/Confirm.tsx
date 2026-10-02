import { PHONE, naira } from '../data'
import { A } from '../router'
import { Order, Line, itemOf, unit } from '../types'
import { Row } from './Cart'

export function Confirm({ o }: { o?: Order }) {
  if (!o) return (
    <div className="wrap page empty">
      <p>No recent order.</p>
      <A to="/menu" className="btn">Browse the menu</A>
    </div>
  )

  const svc = o.lines.some((l: Line) => itemOf(l.id).kind === 'service')

  return (
    <div className="wrap page conf">
      <div className="ok" aria-hidden>✓</div>
      <h1 className="h2">Thank you, {o.name.split(' ')[0]}. Your order is in.</h1>
      <p className="lead">Order number <b>{o.no}</b></p>
      <div className="sum wide">
        {o.lines.map((l: Line) => <Row key={l.key} a={`${l.qty} × ${itemOf(l.id).name}`} b={naira(unit(l) * l.qty)} />)}
        <hr />
        <Row a={o.pay === 'cod' ? 'Amount due' : 'Amount paid'} b={naira(o.total)} bold />
        <Row
          a={o.mode === 'pickup' && !svc ? 'Pickup' : 'Delivery / service address'}
          b={o.mode === 'pickup' && !svc ? 'We will message you when ready' : o.address}
        />
      </div>
      <div className="next">
        <h2>What happens next</h2>
        <p>{svc
          ? 'Dami will call you on ' + o.phone + ' to confirm the details and final price.'
          : 'We start preparing your meal now and will message ' + o.phone + ' when it is on its way.'}</p>
        <div className="cta">
          <a className="btn" href={'tel:' + PHONE}>Call {PHONE}</a>
          <A to="/menu" className="btn ghost">Order more</A>
        </div>
      </div>
    </div>
  )
}
