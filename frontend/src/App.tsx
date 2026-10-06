import { useRoute, A } from './router'
import { Header, Footer } from './components/Layout'
import { Home } from './pages/Home'
import { Catalog } from './pages/Catalog'
import { Detail } from './pages/Detail'
import { Cart } from './pages/Cart'
import { Checkout } from './pages/Checkout'
import { LastOrder } from './pages/OrderStatus'
import { Requests } from './pages/Requests'
import { PaymentCallback } from './pages/PaymentCallback'
import { AdminDashboard } from './pages/admin/index'
import { AppAuth } from './auth'
import { CartProvider, CatalogProvider, useCart } from './store'

function Shell() {
  const route = useRoute()
  const { count } = useCart()
  const [hashPath, qs] = (route.join('/') + '').split('?')
  const [h0, h1] = hashPath.split('/')

  // Real-path routes: admin and payment callback bypass the hash router and
  // render without the storefront chrome (header, footer, pill nav).
  const onCallbackPath = window.location.pathname.endsWith('/payment/callback')
  const onAdminPath = window.location.pathname.startsWith('/admin')

  if (onAdminPath) return <AdminDashboard />
  if (onCallbackPath) return <PaymentCallback />

  const r0 = h0
  const r1 = h1

  return (
    <>
      <Header count={count} go={hashPath} />
      <main>
        {!r0 && <Home />}
        {r0 === 'menu' && <Catalog query={decodeURIComponent(qs || (location.hash.split('?')[1] ?? ''))} />}
        {r0 === 'item' && <Detail id={r1} />}
        {r0 === 'cart' && <Cart />}
        {r0 === 'checkout' && <Checkout />}
        {r0 === 'confirmed' && <LastOrder />}
        {r0 === 'requests' && <Requests />}
      </main>
      <Footer />
      <nav className="pill" aria-label="Quick">
        {([
          ['/', 'lucide:home', 'Home', !r0],
          ['/menu', 'lucide:utensils', 'Menu', r0 === 'menu' && qs !== 'svc'],
          ['/menu?svc', 'lucide:calendar', 'Services', r0 === 'menu' && qs === 'svc'],
          ['/cart', 'lucide:shopping-bag', 'Cart', r0 === 'cart'],
          ['/requests', 'lucide:receipt', 'Account', r0 === 'requests'],
        ] as [string, string, string, boolean][]).map(([to, ic, l, on]) => (
          <A key={l} to={to} className={on ? 'on' : ''}>
            <iconify-icon icon={ic} />
            <span className="sr">{l}</span>
            {l === 'Cart' && count > 0 && <b>{count}</b>}
          </A>
        ))}
        <button
          aria-label="Contact us"
          onClick={() => document.getElementById('contact')?.scrollIntoView({ behavior: 'smooth' })}
        >
          <iconify-icon icon="lucide:phone" />
        </button>
      </nav>
    </>
  )
}

export default function App() {
  return (
    <AppAuth>
      <CatalogProvider>
        <CartProvider>
          <Shell />
        </CartProvider>
      </CatalogProvider>
    </AppAuth>
  )
}
