import { Item } from '../data'

// Illustrated plate stands in for food photography until real photos are added in /public/img
export function Plate({ item }: { item: Item }) {
  const svc = item.kind === 'service'
  return (
    <div className="plate" style={{ background: svc ? 'var(--green)' : 'var(--cream-2)' }}>
      <svg viewBox="0 0 200 140" aria-hidden>
        {svc
          ? <>
              <path d="M0 100 Q60 20 120 80 T200 40" stroke="#F2B01E" strokeWidth="5" fill="none" />
              <path d="M0 130 Q70 60 130 110 T200 80" stroke="#F2B01E" strokeWidth="5" fill="none" />
            </>
          : <>
              <ellipse cx="100" cy="76" rx="84" ry="52" fill="#fff" />
              <ellipse cx="100" cy="76" rx="66" ry="40" fill="#F4EFD0" />
              <ellipse cx="86" cy="72" rx="38" ry="24" fill={item.tone} />
              <ellipse cx="132" cy="80" rx="20" ry="14" fill="#F2B01E" />
              <ellipse cx="120" cy="62" rx="12" ry="8" fill="#0A6A1B" opacity=".8" />
            </>}
      </svg>
    </div>
  )
}
