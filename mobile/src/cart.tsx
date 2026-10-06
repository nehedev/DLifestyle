import AsyncStorage from '@react-native-async-storage/async-storage'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { CartLine, CatalogItem } from './types'
import { foodKey, serviceKey } from './types'

interface CartState {
  lines: CartLine[]
  count: number
  subtotalMinor: number
  add: (item: CatalogItem, opts?: { qty?: number; preferredDate?: string }) => void
  updateQty: (key: string, qty: number) => void
  remove: (key: string) => void
  clear: () => void
}

const CartContext = createContext<CartState>({
  lines: [],
  count: 0,
  subtotalMinor: 0,
  add: () => {},
  updateQty: () => {},
  remove: () => {},
  clear: () => {},
})

export const useCart = () => useContext(CartContext)

const KEY = 'damis.cart'

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([])
  const [hydrated, setHydrated] = useState(false)

  // load local cart on mount
  useEffect(() => {
    AsyncStorage.getItem(KEY).then((raw) => {
      if (raw) {
        try { setLines(JSON.parse(raw)) } catch {}
      }
      setHydrated(true)
    })
  }, [])

  // persist locally
  useEffect(() => {
    if (!hydrated) return
    void AsyncStorage.setItem(KEY, JSON.stringify(lines))
  }, [lines, hydrated])

  const add = useCallback<CartState['add']>((item, opts) => {
    const qty = opts?.qty ?? 1
    const date = opts?.preferredDate
    const key = item.kind === 'food' ? foodKey(item.id) : serviceKey(item.id, date)
    const priceMinor = item.price_minor ?? 0
    setLines((prev) => {
      const existing = prev.find((l) => l.key === key)
      if (existing) {
        return prev.map((l) =>
          l.key === key ? { ...l, qty: l.qty + qty } : l,
        )
      }
      return [
        ...prev,
        {
          key,
          kind: item.kind,
          id: item.id,
          name: item.name,
          unit_price_minor: priceMinor,
          qty,
          preferred_date: date,
          available: !item.sold_out,
        },
      ]
    })
  }, [])

  const updateQty = useCallback<CartState['updateQty']>((key, qty) => {
    setLines((prev) =>
      qty <= 0
        ? prev.filter((l) => l.key !== key)
        : prev.map((l) => (l.key === key ? { ...l, qty } : l)),
    )
  }, [])

  const remove = useCallback<CartState['remove']>((key) => {
    setLines((prev) => prev.filter((l) => l.key !== key))
  }, [])

  const clear = useCallback(() => setLines([]), [])

  const value = useMemo<CartState>(() => {
    const count = lines.reduce((s, l) => s + l.qty, 0)
    const subtotalMinor = lines.reduce((s, l) => s + l.qty * l.unit_price_minor, 0)
    return { lines, count, subtotalMinor, add, updateQty, remove, clear }
  }, [lines, add, updateQty, remove, clear])

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}