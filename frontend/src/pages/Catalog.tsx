import { useEffect, useMemo, useState } from 'react'
import { ADDONS, FOOD_CATS, ITEMS, Item, naira } from '../data'
import { A } from '../router'
import { Plate } from '../components/Plate'

const POPULAR = ['jr-chicken', 'semo-egusi']

export function Card({ item, add }: { item: Item; add: (id: string) => void }) {
  const svc = item.kind === 'service'
  return (
    <article className="card">
      <A to={'/item/' + item.id}>
        <div className="pw">
          <Plate item={item} />
          {POPULAR.includes(item.id) && <span className="badge">Popular</span>}
          {!item.available && <span className="badge off">Sold out today</span>}
        </div>
      </A>
      <div className="card-b">
        <div className="card-t">
          <h3><A to={'/item/' + item.id}>{item.name}</A></h3>
          <strong>{svc ? 'From ' : ''}{naira(item.price)}</strong>
        </div>
        <p>{item.desc}</p>
        {svc
          ? <A to={'/item/' + item.id} className="btn block">Request service</A>
          : <button className="btn block" disabled={!item.available} onClick={() => add(item.id)}>+ Add to cart</button>}
      </div>
    </article>
  )
}

export function Catalog({ add, query }: { add: (id: string) => void; query: string }) {
  const [q, setQ] = useState('')
  const [kind, setKind] = useState<'all' | 'food' | 'service'>(query === 'svc' ? 'service' : 'all')
  const [cat, setCat] = useState(query && query !== 'svc' ? query : 'All')
  useEffect(() => {
    setKind(query === 'svc' ? 'service' : 'all')
    setCat(query && query !== 'svc' ? query : 'All')
  }, [query])
  const cats = ['All', ...FOOD_CATS, 'Catering', 'Cleaning', 'Errands', 'Organization']
  const list = useMemo(() =>
    ITEMS.filter(i =>
      (kind === 'all' || i.kind === kind) &&
      (cat === 'All' || i.cat === cat) &&
      (i.name + i.desc).toLowerCase().includes(q.toLowerCase())
    ), [q, kind, cat])
  return (
    <div className="wrap page">
      <h1 className="h2">Menu &amp; services</h1>
      <div className="filters">
        <input className="inp" type="search" placeholder="Search jollof, egusi, cleaning…" value={q} onChange={e => setQ(e.target.value)} aria-label="Search" />
        <div className="seg" role="group" aria-label="Type">
          {(['all', 'food', 'service'] as const).map(k => (
            <button key={k} aria-pressed={kind === k} onClick={() => { setKind(k); setCat('All') }}>
              {k === 'all' ? 'All' : k === 'food' ? 'Food' : 'Services'}
            </button>
          ))}
        </div>
      </div>
      <div className="chips">
        {cats
          .filter(c => kind === 'all' || c === 'All' || (kind === 'food' ? FOOD_CATS.includes(c) : !FOOD_CATS.includes(c)))
          .map(c => <button key={c} aria-pressed={cat === c} onClick={() => setCat(c)}>{c}</button>)}
      </div>
      {list.length
        ? <div className="grid4">{list.map(i => <Card key={i.id} item={i} add={add} />)}</div>
        : <div className="empty">
            <p>Nothing matches "{q}".</p>
            <button className="btn" onClick={() => { setQ(''); setCat('All'); setKind('all') }}>Clear filters</button>
          </div>}
    </div>
  )
}
