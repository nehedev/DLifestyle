import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { ApiError, getMenu, getServices, getStore } from './api'
import type { MenuItem, Service, StoreInfo } from './api'
import { foodKey, serviceKey, type CartLine, type CatalogItem } from './types'

const CART_STORAGE_KEY = 'damis.cart'

function toCatalogItem(menuItem: MenuItem): CatalogItem {
  return {
    kind: 'food',
    id: menuItem.id,
    key: foodKey(menuItem.id),
    name: menuItem.name,
    desc: menuItem.description ?? '',
    price_minor: menuItem.price_minor,
    category: menuItem.category,
    image_url: menuItem.image_url,
    image_alt: menuItem.image_alt,
    sold_out: menuItem.is_sold_out,
    weekdays: menuItem.weekdays,
  }
}

function toCatalogService(service: Service): CatalogItem {
  return {
    kind: 'service',
    id: service.id,
    key: serviceKey(service.id),
    name: service.name,
    desc: service.description,
    price_minor: null,
    category: 'Services',
    image_url: null,
    image_alt: null,
    sold_out: false,
    weekdays: [],
  }
}

interface CatalogValue {
  items: CatalogItem[]
  menu: MenuItem[]
  store: StoreInfo | null
  loading: boolean
  error: string | null
  reload: () => void
}

const CatalogContext = createContext<CatalogValue | null>(null)

export function CatalogProvider({ children }: { children: ReactNode }) {
  const [menu, setMenu] = useState<MenuItem[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [store, setStore] = useState<StoreInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [menuItems, serviceItems, storeInfo] = await Promise.all([
        getMenu(),
        getServices(),
        getStore().catch((cause) => {
          // An unconfigured store is expected until the owner sets it up.
          if (cause instanceof ApiError && cause.status === 503) return null
          throw cause
        }),
      ])
      setMenu(menuItems)
      setServices(serviceItems)
      setStore(storeInfo)
    } catch (cause) {
      setError(
        cause instanceof Error
          ? `We could not reach the store. ${cause.message}`
          : 'We could not reach the store.',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const items = useMemo(
    () => [
      ...menu.map(toCatalogItem),
      ...services.map(toCatalogService),
    ],
    [menu, services],
  )

  return (
    <CatalogContext.Provider value={{ items, menu, store, loading, error, reload: load }}>
      {children}
    </CatalogContext.Provider>
  )
}

export function useCatalog(): CatalogValue {
  const value = useContext(CatalogContext)
  if (!value) throw new Error('useCatalog must be used within CatalogProvider')
  return value
}

export function useCatalogItem(key: string | undefined): CatalogItem | undefined {
  const { items } = useCatalog()
  return items.find((item) => item.key === key)
}

interface CartValue {
  lines: CartLine[]
  add: (item: CatalogItem, qty?: number, date?: string) => void
  setQty: (key: string, qty: number) => void
  remove: (key: string) => void
  clear: () => void
  count: number
  itemsTotalMinor: number
}

const CartContext = createContext<CartValue | null>(null)

function loadStoredCart(): CartLine[] {
  try {
    const raw = localStorage.getItem(CART_STORAGE_KEY)
    return raw ? (JSON.parse(raw) as CartLine[]) : []
  } catch {
    return []
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(loadStoredCart)

  useEffect(() => {
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(lines))
  }, [lines])

  const add = useCallback((item: CatalogItem, qty = 1, date?: string) => {
    const key = item.kind === 'service' ? serviceKey(item.id, date) : foodKey(item.id)
    setLines((current) => {
      const existing = current.find((line) => line.key === key)
      if (existing) {
        if (item.kind === 'service') return current
        return current.map((line) =>
          line.key === key ? { ...line, qty: line.qty + qty } : line,
        )
      }
      return [
        ...current,
        {
          key,
          kind: item.kind,
          id: item.id,
          name: item.name,
          unit_price_minor: item.price_minor ?? 0,
          qty: item.kind === 'service' ? 1 : qty,
          preferred_date: item.kind === 'service' ? date : undefined,
        },
      ]
    })
  }, [])

  const setQty = useCallback((key: string, qty: number) => {
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, qty: Math.max(1, qty) } : line)),
    )
  }, [])

  const remove = useCallback((key: string) => {
    setLines((current) => current.filter((line) => line.key !== key))
  }, [])

  const clear = useCallback(() => setLines([]), [])

  const count = useMemo(() => lines.reduce((sum, line) => sum + line.qty, 0), [lines])
  const itemsTotalMinor = useMemo(
    () =>
      lines
        .filter((line) => line.kind === 'food')
        .reduce((sum, line) => sum + line.unit_price_minor * line.qty, 0),
    [lines],
  )

  return (
    <CartContext.Provider
      value={{ lines, add, setQty, remove, clear, count, itemsTotalMinor }}
    >
      {children}
    </CartContext.Provider>
  )
}

export function useCart(): CartValue {
  const value = useContext(CartContext)
  if (!value) throw new Error('useCart must be used within CartProvider')
  return value
}
