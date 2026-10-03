import { toneFor } from '../data'
import type { CatalogItem } from '../types'

// Falls back to an illustrated plate until a real photo is set on the item.
export function Plate({ item }: { item: CatalogItem }) {
  const svc = item.kind === 'service'
  if (item.image_url) {
    return (
      <div className="plate">
        <img
          src={item.image_url}
          alt={item.image_alt ?? item.name}
          loading="lazy"
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
      </div>
    )
  }
  return (
    <div className="plate" style={{ background: svc ? 'var(--green)' : 'var(--cream-2)' }}>
      <svg viewBox="0 0 200 140" aria-hidden>
        {svc ? (
          <>
            <path
              d="M0 100 Q60 20 120 80 T200 40"
              stroke="#F2B01E"
              strokeWidth="5"
              fill="none"
            />
            <path
              d="M0 130 Q70 60 130 110 T200 80"
              stroke="#F2B01E"
              strokeWidth="5"
              fill="none"
            />
          </>
        ) : (
          <>
            <ellipse cx="100" cy="76" rx="84" ry="52" fill="#fff" />
            <ellipse cx="100" cy="76" rx="66" ry="40" fill="#F4EFD0" />
            <ellipse cx="86" cy="72" rx="38" ry="24" fill={toneFor(item.category)} />
            <ellipse cx="132" cy="80" rx="20" ry="14" fill="#F2B01E" />
            <ellipse cx="120" cy="62" rx="12" ry="8" fill="#0A6A1B" opacity=".8" />
          </>
        )}
      </svg>
    </div>
  )
}
