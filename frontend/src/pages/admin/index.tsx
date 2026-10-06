import { useState } from 'react'
import { useAdmin } from '../../auth'
import { useSession } from '../../auth'
import { AdminOrders } from './Orders'
import { AdminMenu } from './Menu'
import { AdminServices } from './Services'
import { AdminServiceRequests } from './ServiceRequests'
import { AdminPayments } from './Payments'
import { AdminStoreSettings } from './StoreSettings'

type AdminTab = 'orders' | 'menu' | 'services' | 'requests' | 'payments' | 'settings'

const NAV: { id: AdminTab; label: string; icon: string }[] = [
  { id: 'orders', label: 'Orders', icon: 'lucide:shopping-bag' },
  { id: 'requests', label: 'Service requests', icon: 'lucide:calendar' },
  { id: 'payments', label: 'Payments', icon: 'lucide:credit-card' },
  { id: 'menu', label: 'Menu items', icon: 'lucide:utensils' },
  { id: 'services', label: 'Services', icon: 'lucide:sparkles' },
  { id: 'settings', label: 'Store settings', icon: 'lucide:settings' },
]

export function AdminDashboard() {
  const { isAuthenticated, isLoading, login, logout } = useSession()
  const { isAdmin, loading: adminLoading } = useAdmin()
  const [tab, setTab] = useState<AdminTab>('orders')
  const [menuOpen, setMenuOpen] = useState(false)

  if (isLoading || adminLoading) {
    return (
      <div className="adm-gate">
        <p>Loading…</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="adm-gate">
        <iconify-icon icon="lucide:lock" className="adm-gate-icon" />
        <h1>Admin sign-in required</h1>
        <p>Sign in with your admin Google account to continue.</p>
        <button className="btn lg" onClick={login}>Sign in</button>
      </div>
    )
  }

  if (!isAdmin) {
    return (
      <div className="adm-gate">
        <iconify-icon icon="lucide:shield-off" className="adm-gate-icon" />
        <h1>Access denied</h1>
        <p>Your account does not have admin access.</p>
        <button className="btn ghost" onClick={logout}>Sign out</button>
      </div>
    )
  }

  return (
    <div className="adm-shell">
      {/* Sidebar */}
      <nav className={`adm-sidebar${menuOpen ? ' open' : ''}`} aria-label="Admin navigation">
        <div className="adm-logo">
          <iconify-icon icon="lucide:chef-hat" />
          <span>Dami's Admin</span>
        </div>
        <ul>
          {NAV.map(n => (
            <li key={n.id}>
              <button
                className={tab === n.id ? 'on' : ''}
                onClick={() => { setTab(n.id); setMenuOpen(false) }}
                aria-current={tab === n.id ? 'page' : undefined}
              >
                <iconify-icon icon={n.icon} />
                <span>{n.label}</span>
              </button>
            </li>
          ))}
        </ul>
        <button className="adm-signout btn ghost sm" onClick={logout}>
          <iconify-icon icon="lucide:log-out" /> Sign out
        </button>
      </nav>

      {/* Mobile header */}
      <header className="adm-mob-hdr">
        <button className="adm-burger" aria-label="Open menu" onClick={() => setMenuOpen(v => !v)}>
          <iconify-icon icon={menuOpen ? 'lucide:x' : 'lucide:menu'} />
        </button>
        <span>{NAV.find(n => n.id === tab)?.label ?? 'Admin'}</span>
      </header>

      {/* Main content */}
      <main className="adm-main">
        {tab === 'orders' && <AdminOrders />}
        {tab === 'menu' && <AdminMenu />}
        {tab === 'services' && <AdminServices />}
        {tab === 'requests' && <AdminServiceRequests />}
        {tab === 'payments' && <AdminPayments />}
        {tab === 'settings' && <AdminStoreSettings />}
      </main>
    </div>
  )
}
