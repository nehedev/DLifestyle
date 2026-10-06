import type { Contact, OrderResponse } from './api'

export type Kind = 'food' | 'service'

export interface CatalogItem {
  kind: Kind
  id: number
  key: string
  name: string
  desc: string
  price_minor: number | null
  category: string
  image_url: string | null
  image_alt: string | null
  sold_out: boolean
  weekdays: number[]
}

export interface CartLine {
  key: string
  kind: Kind
  id: number
  name: string
  unit_price_minor: number
  qty: number
  preferred_date?: string
  available?: boolean
}

export const foodKey = (id: number) => `food:${id}`
export const serviceKey = (id: number, date?: string) => `service:${id}:${date ?? ''}`

export type { Contact, OrderResponse }