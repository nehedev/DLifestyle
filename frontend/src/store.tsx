import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { ApiError, getCart, getMenu, getServices, getStore, putCart } from './api'
import type { CartLinePayload, MenuItem, Service, StoreInfo } from './api'
import { useSession } from './auth'
import { foodKey, serviceKey, type CartLine, type CatalogItem, type Kind } from './types'

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

/** The persistable shape of a cart line; names and prices come from the catalog. */
interface CartEntry {
  kind: Kind
  id: number
  qty: number
  preferred_date?: string
}

const entryKey = (entry: CartEntry): string =>
  entry.kind === 'service' ? serviceKey(entry.id, entry.preferred_date) : foodKey(entry.id)

function loadEntries(): CartEntry[] {
  try {
    const raw = localStorage.getItem(CART_STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    const entries: CartEntry[] = []
    for (const value of parsed) {
      if (!value || typeof value !== 'object') continue
      const record = value as Record<string, unknown>
      const { kind, id, qty, preferred_date: preferred } = record
      if ((kind !== 'food' && kind !== 'service') || typeof id !== 'number') continue
      const lineKind: Kind = kind === 'food' ? 'food' : 'service'
      const quantity = typeof qty === 'number' && qty > 0 ? qty : 1
      const preferredDate = typeof preferred === 'string' ? preferred : undefined
      entries.push({
        kind: lineKind,
        id,
        qty: lineKind === 'service' ? 1 : quantity,
        preferred_date: lineKind === 'service' ? preferredDate : undefined,
      })
    }
    return entries
  } catch {
    return []
  }
}

const toPayload = (entries: CartEntry[]): CartLinePayload[] =>
  entries.map((entry) => ({
    kind: entry.kind,
    menu_item_id: entry.kind === 'food' ? entry.id : null,
    service_id: entry.kind === 'service' ? entry.id : null,
    quantity: entry.kind === 'service' ? 1 : entry.qty,
    preferred_date: entry.kind === 'service' ? entry.preferred_date ?? null : null,
  }))

const fromServer = (items: CartLinePayload[]): CartEntry[] =>
  items.map((item) => {
    const kind: Kind = item.kind
    return {
      kind,
      id: (kind === 'food' ? item.menu_item_id : item.service_id) ?? 0,
      qty: kind === 'service' ? 1 : item.quantity,
      preferred_date: kind === 'service' ? item.preferred_date ?? undefined : undefined,
    }
  })

/** Union of the server cart and the anonymous local cart; food quantities add up. */
function mergeEntries(server: CartEntry[], local: CartEntry[]): CartEntry[] {
  const merged = server.map((entry) => ({ ...entry }))
  for (const entry of local) {
    const existing = merged.find((candidate) => entryKey(candidate) === entryKey(entry))
    if (!existing) {
      merged.push({ ...entry })
    } else if (entry.kind === 'food') {
      existing.qty += entry.qty
    }
  }
  return merged
}

function hydrate(entry: CartEntry, items: CatalogItem[]): CartLine {
  const item = items.find(
    (candidate) => candidate.kind === entry.kind && candidate.id === entry.id,
  )
  const available = item ? !(entry.kind === 'food' && item.sold_out) : false
  return {
    key: entryKey(entry),
    kind: entry.kind,
    id: entry.id,
    name: item?.name ?? 'Unavailable item',
    unit_price_minor: item?.price_minor ?? 0,
    qty: entry.qty,
    preferred_date: entry.preferred_date,
    available,
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useSession()
  const { items: catalogItems } = useCatalog()
  const [entries, setEntries] = useState<CartEntry[]>(loadEntries)
  const [serverReady, setServerReady] = useState(false)
  const previousAuth = useRef<boolean | null>(null)

  // On sign-in, merge the local cart into the server cart; on sign-out, drop
  // the local cache so the next person on the device starts clean.
  useEffect(() => {
    const wasAuthenticated = previousAuth.current
    previousAuth.current = isAuthenticated

    if (!isAuthenticated) {
      setServerReady(false)
      if (wasAuthenticated === true) {
        setEntries([])
        localStorage.removeItem(CART_STORAGE_KEY)
      }
      return
    }

    let active = true
    setServerReady(false)
    getCart()
      .then((page) => {
        if (!active) return
        const serverEntries = fromServer(page.items)
        setEntries((current) =>
          wasAuthenticated === false ? mergeEntries(serverEntries, current) : serverEntries,
        )
        localStorage.removeItem(CART_STORAGE_KEY)
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setServerReady(true)
      })
    return () => {
      active = false
    }
  }, [isAuthenticated])

  // Signed-out carts live in localStorage only.
  useEffect(() => {
    if (isAuthenticated) return
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(entries))
  }, [entries, isAuthenticated])

  // Signed-in changes are mirrored to the server (debounced).
  useEffect(() => {
    if (!isAuthenticated || !serverReady) return
    const timer = setTimeout(() => {
      void putCart(toPayload(entries)).catch(() => undefined)
    }, 400)
    return () => clearTimeout(timer)
  }, [entries, isAuthenticated, serverReady])

  const add = useCallback((item: CatalogItem, qty = 1, date?: string) => {
    setEntries((current) => {
      const key = item.kind === 'service' ? serviceKey(item.id, date) : foodKey(item.id)
      const existing = current.find((entry) => entryKey(entry) === key)
      if (existing) {
        if (item.kind === 'service') return current
        return current.map((entry) =>
          entryKey(entry) === key ? { ...entry, qty: entry.qty + qty } : entry,
        )
      }
      return [
        ...current,
        {
          kind: item.kind,
          id: item.id,
          qty: item.kind === 'service' ? 1 : qty,
          preferred_date: item.kind === 'service' ? date : undefined,
        },
      ]
    })
  }, [])

  const setQty = useCallback((key: string, qty: number) => {
    setEntries((current) =>
      current.map((entry) =>
        entryKey(entry) === key ? { ...entry, qty: Math.max(1, qty) } : entry,
      ),
    )
  }, [])

  const remove = useCallback((key: string) => {
    setEntries((current) => current.filter((entry) => entryKey(entry) !== key))
  }, [])

  const clear = useCallback(() => {
    setEntries([])
    if (isAuthenticated) void putCart([]).catch(() => undefined)
  }, [isAuthenticated])

  const lines = useMemo(
    () => entries.map((entry) => hydrate(entry, catalogItems)),
    [entries, catalogItems],
  )
  const count = useMemo(() => lines.reduce((sum, line) => sum + line.qty, 0), [lines])
  const itemsTotalMinor = useMemo(
    () =>
      lines
        .filter((line) => line.kind === 'food' && line.available !== false)
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
