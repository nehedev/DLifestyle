import { useEffect, useState } from 'react'

export function useRoute() {
  const [h, setH] = useState(location.hash || '#/')
  useEffect(() => {
    const f = () => { setH(location.hash || '#/'); window.scrollTo(0, 0) }
    addEventListener('hashchange', f)
    return () => removeEventListener('hashchange', f)
  }, [])
  return h.replace('#', '').split('/').filter(Boolean)
}

export const A = ({ to, children, className }: { to: string; children: React.ReactNode; className?: string }) =>
  <a href={'#' + to} className={className}>{children}</a>
