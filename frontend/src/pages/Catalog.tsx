import { useMemo, useState } from 'react'
import { naira } from '../api'
import { A } from '../router'
import { Plate } from '../components/Plate'
import { useCart, useCatalog } from '../store'
import type { CatalogItem, Kind } from '../types'

export function Card({ item }: { item: CatalogItem }) {
  const { add } = useCart()
  const svc = item.kind === 'service'
  return (
    <article className="card">
      <A to={'/item/' + item.key}>
        <div className="pw">
          <Plate item={item} />
          {item.sold_out && <span className="badge off">Sold out</span>}
        </div>
      </A>
      <div className="card-b">
        <div className="card-t">
          <h3>
            <A to={'/item/' + item.key}>{item.name}</A>
          </h3>
          <strong>{svc ? 'Price on request' : naira(item.price_minor ?? 0)}</strong>
        </div>
        <p>{item.desc}</p>
        {svc ? (
          <A to={'/item/' + item.key} className="btn block">
            Request service
          </A>
        ) : (
          <button className="btn block" disabled={item.sold_out} onClick={() => add(item)}>
            {item.sold_out ? 'Sold out' : '+ Add to cart'}
          </button>
        )}
      </div>
    </article>
  )
}

export function Catalog({ query }: { query: string }) {
  const { items, loading, error, reload } = useCatalog()
  const [q, setQ] = useState('')
  const [kind, setKind] = useState<'all' | Kind>(query === 'svc' ? 'service' : 'all')
  const [cat, setCat] = useState(query && query !== 'svc' ? query : 'All')

  const categories = useMemo(() => {
    const foodCats = [...new Set(items.filter((i) => i.kind === 'food').map((i) => i.category))]
    const hasServices = items.some((i) => i.kind === 'service')
    return ['All', ...foodCats, ...(hasServices ? ['Services'] : [])]
  }, [items])

  const visibleCategories = categories.filter(
    (c) =>
      c === 'All' ||
      (kind === 'all' && (c !== 'Services' || items.some((i) => i.kind === 'service'))) ||
      (kind === 'food' && c !== 'Services') ||
      (kind === 'service' && c === 'Services'),
  )

  const list = useMemo(
    () =>
      items.filter(
        (i) =>
          (kind === 'all' || i.kind === kind) &&
          (cat === 'All' || i.category === cat) &&
          (i.name + i.desc).toLowerCase().includes(q.toLowerCase()),
      ),
    [items, q, kind, cat],
  )

  if (loading) return <div className="wrap page"><p>Loading the menu…</p></div>
  if (error)
    return (
      <div className="wrap page empty">
        <p>{error}</p>
        <button className="btn" onClick={reload}>
          Try again
        </button>
      </div>
    )

  return (
    <div className="wrap page">
      <h1 className="h2">Menu &amp; services</h1>
      <div className="filters">
        <input
          className="inp"
          type="search"
          placeholder="Search jollof, egusi, cleaning…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search"
        />
        <div className="seg" role="group" aria-label="Type">
          {(['all', 'food', 'service'] as const).map((k) => (
            <button
              key={k}
              aria-pressed={kind === k}
              onClick={() => {
                setKind(k)
                setCat('All')
              }}
            >
              {k === 'all' ? 'All' : k === 'food' ? 'Food' : 'Services'}
            </button>
          ))}
        </div>
      </div>
      <div className="chips">
        {visibleCategories.map((c) => (
          <button key={c} aria-pressed={cat === c} onClick={() => setCat(c)}>
            {c}
          </button>
        ))}
      </div>
      {list.length ? (
        <div className="grid4">
          {list.map((i) => (
            <Card key={i.key} item={i} />
          ))}
        </div>
      ) : (
        <div className="empty">
          <p>Nothing matches "{q}".</p>
          <button
            className="btn"
            onClick={() => {
              setQ('')
              setCat('All')
              setKind('all')
            }}
          >
            Clear filters
          </button>
        </div>
      )}
    </div>
  )
}
