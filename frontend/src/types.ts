import type { Contact, OrderResponse } from './api'

export type Kind = 'food' | 'service'

/** A menu item or service shaped for the storefront UI. */
export interface CatalogItem {
  kind: Kind
  id: number
  key: string
  name: string
  desc: string
  /** Integer minor units; null for services, which are quoted by the owner. */
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
  /** Service requests only. */
  preferred_date?: string
  /** False when the catalog item is missing, inactive, or sold out. */
  available?: boolean
}

export const foodKey = (id: number) => `food:${id}`
export const serviceKey = (id: number, date?: string) => `service:${id}:${date ?? ''}`

export type { Contact, OrderResponse }
