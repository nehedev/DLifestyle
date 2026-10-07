// Thin client for the Dami's Lifestyle Services backend.
// The backend is authoritative for prices, fees and totals.

import { Platform } from 'react-native'

const DEFAULT_BASE =
  Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000'

export const API_BASE =
  (process.env.EXPO_PUBLIC_API_BASE_URL as string | undefined) ?? DEFAULT_BASE

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
  role: string
}

export interface GoogleSignInResponse {
  id_token: string
  expires_at: number
  picture: string | null
  user: MeResponse
}

export interface CartLinePayload {
  kind: 'food' | 'service'
  menu_item_id: number | null
  service_id: number | null
  quantity: number
  preferred_date: string | null
}

export interface CartPage {
  items: CartLinePayload[]
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
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  }

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!response.ok) {
    let detail: unknown = response.statusText
    try {
      detail = (await response.json()).detail
    } catch {}
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

export const getMe = (token?: string): Promise<MeResponse> =>
  request<MeResponse>(
    '/api/v1/me',
    token ? { headers: { Authorization: `Bearer ${token}` } } : {},
  )

export const googleSignIn = (
  code: string,
  redirectUri?: string,
): Promise<GoogleSignInResponse> =>
  request<GoogleSignInResponse>('/api/v1/auth/google', {
    method: 'POST',
    body: JSON.stringify({ code, redirect_uri: redirectUri }),
  })

/** Used by native mobile clients: verifies an id_token obtained directly
 *  from Google's implicit flow, no code exchange required. */
export const googleSignInWithToken = (
  idToken: string,
): Promise<GoogleSignInResponse> =>
  request<GoogleSignInResponse>('/api/v1/auth/google/token', {
    method: 'POST',
    body: JSON.stringify({ id_token: idToken }),
  })

/** Loads the signed-in user's cart. */
export const getCart = (): Promise<CartPage> => request<CartPage>('/api/v1/cart')

/** Replaces the signed-in user's cart with the given snapshot. */
export const putCart = (items: CartLinePayload[]): Promise<CartPage> =>
  request<CartPage>('/api/v1/cart', {
    method: 'PUT',
    body: JSON.stringify({ items }),
  })


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

