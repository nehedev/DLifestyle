import { useEffect, useState } from 'react'
import { PHONE } from '../data'
import { A } from '../router'
import { useSession } from '../auth'

export function Logo({ light }: { light?: boolean }) {
  return (
    <A to="/" className={'logo' + (light ? ' light' : '')}>
      <span>Dami's</span>
      <span>Lifestyle Services</span>
      <i />
    </A>
  )
}

export function Header({ count, go }: { count: number; go: string }) {
  const [open, setOpen] = useState(false)
  const { isAuthenticated, isLoading, user, login, logout } = useSession()
  useEffect(() => setOpen(false), [go])
  const nav = [
    ['/menu', 'Menu'],
    ['/menu?svc', 'Services'],
    ['/#about', 'About'],
    ['/#contact', 'Contact'],
  ]
  return (
    <header className="hdr">
      <div className="wrap hdr-in">
        <A to="/" className="brand">
          <span className="mark">D</span>
          <span className="wm">
            Dami's
            <br />
            Lifestyle
          </span>
        </A>
        <nav className={'nav' + (open ? ' open' : '')} aria-label="Main">
          {nav.map(([to, l]) => (
            <a
              key={l}
              href={'#' + to}
              onClick={(e) => {
                if (to.includes('#about') || to.includes('#contact')) {
                  e.preventDefault()
                  location.hash = '/'
                  setTimeout(
                    () => document.getElementById(l.toLowerCase())?.scrollIntoView(),
                    50,
                  )
                  setOpen(false)
                }
              }}
            >
              {l}
            </a>
          ))}
        </nav>
        <div className="hdr-r">
          <A to="/cart" className="cartbtn" aria-label={`Cart, ${count} items`}>
            <iconify-icon icon="lucide:shopping-cart" />
            <b>{count}</b>
          </A>
          {isAuthenticated ? (
            <span className="hdr-user">
              <A to="/requests" className="lnk">
                {user?.given_name ?? user?.name ?? 'Account'}
              </A>
              <button className="lnk" onClick={logout}>
                Sign out
              </button>
            </span>
          ) : (
            <button className="btn red sm" onClick={login} disabled={isLoading}>
              Sign in
            </button>
          )}
          <button
            className="burger"
            aria-label="Menu"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            <iconify-icon icon={open ? 'lucide:x' : 'lucide:menu'} />
          </button>
        </div>
      </div>
    </header>
  )
}

export function Footer() {
  return (
    <footer className="ftr" id="contact">
      <div className="wrap ftr-in">
        <div>
          <Logo light />
          <p>Making life easier, one service at a time.</p>
          <A to="/menu" className="btn gold">
            Order now
          </A>
        </div>
        <div>
          <h4>Explore</h4>
          <A to="/menu">Menu</A>
          <A to="/menu?svc">Services</A>
          <A to="/cart">Cart</A>
          <A to="/requests">Account</A>
        </div>
        <div>
          <h4>Services</h4>
          <span>Personal chef &amp; catering</span>
          <span>Home cleaning</span>
          <span>Errand running</span>
          <span>Home organization</span>
        </div>
        <div>
          <h4>Contact</h4>
          <a href={'tel:' + PHONE}>{PHONE}</a>
          <span>@damislifestyleservices</span>
          <div className="soc">
            <iconify-icon icon="mdi:instagram" />
            <iconify-icon icon="mdi:whatsapp" />
            <iconify-icon icon="mdi:facebook" />
            <iconify-icon icon="mdi:youtube" />
          </div>
        </div>
      </div>
    </footer>
  )
}
