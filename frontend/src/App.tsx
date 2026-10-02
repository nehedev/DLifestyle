import { useState } from 'react'
import { useRoute, A } from './router'
import { Header, Footer } from './components/Layout'
import { Home } from './pages/Home'
import { Catalog } from './pages/Catalog'
import { Detail } from './pages/Detail'
import { Cart } from './pages/Cart'
import { Checkout } from './pages/Checkout'
import { Confirm } from './pages/Confirm'
import { Line, Order } from './types'

export default function App() {
  const route = useRoute()
  const [lines, setLines] = useState<Line[]>([])
  const [order, setOrder] = useState<Order>()
  const [path, qs] = (route.join('/') + '').split('?')
  const [r0, r1] = path.split('/')

  const add = (id: string, qty = 1, addons: string[] = [], date?: string) =>
    setLines(ls => {
      const key = id + addons.slice().sort().join('+')
      const hit = ls.find(l => l.key === key)
      return hit
        ? ls.map(l => l.key === key ? { ...l, qty: l.qty + qty } : l)
        : [...ls, { key, id, qty, addons, date }]
    })

  const count = lines.reduce((s, l) => s + l.qty, 0)

  return (
    <>
      <Header count={count} go={path} />
      <main>
        {!r0 && <Home add={id => add(id)} />}
        {r0 === 'menu' && <Catalog add={id => add(id)} query={decodeURIComponent(qs || (location.hash.split('?')[1] ?? ''))} />}
        {r0 === 'item' && <Detail id={r1} add={add} />}
        {r0 === 'cart' && <Cart lines={lines} setLines={setLines} />}
        {r0 === 'checkout' && <Checkout lines={lines} done={o => { setOrder(o); setLines([]); location.hash = '/confirmed' }} />}
        {r0 === 'confirmed' && <Confirm o={order} />}
      </main>
      <Footer />
      <nav className="pill" aria-label="Quick">
        {([
          ['/', 'lucide:home', 'Home', !r0],
          ['/menu', 'lucide:utensils', 'Menu', r0 === 'menu' && qs !== 'svc'],
          ['/menu?svc', 'lucide:calendar', 'Services', r0 === 'menu' && qs === 'svc'],
          ['/cart', 'lucide:shopping-bag', 'Cart', r0 === 'cart'],
        ] as [string, string, string, boolean][]).map(([to, ic, l, on]) => (
          <A key={l} to={to} className={on ? 'on' : ''}>
            <iconify-icon icon={ic} /><span className="sr">{l}</span>
            {l === 'Cart' && count > 0 && <b>{count}</b>}
          </A>
        ))}
        <button aria-label="Contact us" onClick={() => document.getElementById('contact')?.scrollIntoView({ behavior: 'smooth' })}>
          <iconify-icon icon="lucide:phone" />
        </button>
      </nav>
    </>
  )
}
