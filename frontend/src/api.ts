// Thin client for the Dami's Lifestyle Services backend.
// The backend is authoritative for prices, fees and totals; never compute
// money on the client beyond display.

export const API_BASE =
  (import.meta.env.API_BASE_URL as string | undefined) ?? 'http://localhost:8000'

export interface MenuItem {
  id: number
  name: string
  description: string | null
  category: string
  image_url: string | null
  image_alt: string | null
  price_minor: number
  is_sold_out: boolean
  weekdays: number[]
}

export interface Service {
  id: number
  name: string
  description: string
}

export interface StoreInfo {
  delivery_fee_minor: number
  order_cutoff_time: string
  max_advance_days: number
  currency: string
  timezone: string
}

export interface OrderItemResponse {
  name: string
  quantity: number
  unit_price_minor: number
}

export interface Contact {
  name: string
  phone: string
  address?: string | null
}

export interface OrderResponse {
  id: number
  status: string
  fulfillment_type: 'delivery' | 'pickup'
  fulfillment_date: string
  contact: Contact
  notes: string | null
  items_total_minor: number
  delivery_fee_minor: number
  total_minor: number
  currency: string
  created_at: string
  updated_at: string
  items: OrderItemResponse[]
}

export interface CreateOrderPayload {
  items: { menu_item_id: number; quantity: number }[]
  fulfillment_type: 'delivery' | 'pickup'
  fulfillment_date: string
  contact: Contact
  notes?: string | null
}

export interface ServiceRequestResponse {
  id: number
  service_id: number
  preferred_date: string | null
  location: string
  details: string
  contact_phone: string
  status: string
  quoted_amount_minor: number | null
  owner_note: string | null
  created_at: string
  updated_at: string
}

export interface CreateServiceRequestPayload {
  service_id: number
  preferred_date?: string | null
  location: string
  details: string
  contact_phone: string
}

export interface MeResponse {
  id: number
  email: string
  first_name: string
  last_name: string | null
  is_owner: boolean
}

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed (${status})`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export const naira = (minor: number) =>
  '₦' + (minor / 100).toLocaleString('en-NG', { maximumFractionDigits: 2 })

let tokenGetter: (() => Promise<string | undefined>) | undefined

/** Register the Auth0 access-token source used for authenticated calls. */
export function setAccessTokenGetter(getter: () => Promise<string | undefined>) {
  tokenGetter = getter
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (tokenGetter) {
    const token = await tokenGetter()
    if (token) headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!response.ok) {
    let detail: unknown = response.statusText
    try {
      detail = (await response.json()).detail
    } catch {
      // Non-JSON error body; keep the status text.
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const getMenu = async (): Promise<MenuItem[]> =>
  (await request<{ items: MenuItem[] }>('/api/v1/menu')).items

export const getServices = async (): Promise<Service[]> =>
  (await request<{ items: Service[] }>('/api/v1/services')).items

export const getStore = (): Promise<StoreInfo> => request<StoreInfo>('/api/v1/store')

export const getMe = (): Promise<MeResponse> => request<MeResponse>('/api/v1/me')

export const createOrder = (
  payload: CreateOrderPayload,
  idempotencyKey?: string,
): Promise<OrderResponse> =>
  request<OrderResponse>('/api/v1/orders', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
  })

export const payOrder = (orderId: number): Promise<{ authorization_url: string }> =>
  request<{ authorization_url: string }>(`/api/v1/orders/${orderId}/pay`, {
    method: 'POST',
  })

export const cancelOrder = (orderId: number): Promise<OrderResponse> =>
  request<OrderResponse>(`/api/v1/orders/${orderId}/cancel`, { method: 'POST' })

export const getOrder = (orderId: number): Promise<OrderResponse> =>
  request<OrderResponse>(`/api/v1/orders/${orderId}`)

export const listOrders = (): Promise<{ items: OrderResponse[]; next_cursor: string | null }> =>
  request<{ items: OrderResponse[]; next_cursor: string | null }>('/api/v1/orders')

export const createServiceRequest = (
  payload: CreateServiceRequestPayload,
): Promise<ServiceRequestResponse> =>
  request<ServiceRequestResponse>('/api/v1/service-requests', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const listServiceRequests = (): Promise<{
  items: ServiceRequestResponse[]
  next_cursor: string | null
}> =>
  request<{ items: ServiceRequestResponse[]; next_cursor: string | null }>(
    '/api/v1/service-requests',
  )

export const cancelServiceRequest = (requestId: number): Promise<ServiceRequestResponse> =>
  request<ServiceRequestResponse>(`/api/v1/service-requests/${requestId}/cancel`, {
    method: 'POST',
  })
