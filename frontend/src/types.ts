import { ADDONS, ITEMS } from './data'

export interface Line { key: string; id: string; qty: number; addons: string[]; date?: string }
export interface Order { no: string; lines: Line[]; total: number; name: string; phone: string; address: string; mode: string; pay: string }

export const itemOf = (id: string) => ITEMS.find(i => i.id === id)!
export const unit = (l: Line) => itemOf(l.id).price + l.addons.reduce((s, a) => s + ADDONS.find(x => x.id === a)!.price, 0)
export const fees = (lines: Line[], mode: string) => {
  const hasF = lines.some(l => itemOf(l.id).kind === 'food')
  const hasS = lines.some(l => itemOf(l.id).kind === 'service')
  return (hasF && mode === 'delivery' ? 1500 : 0) + (hasS ? 2000 : 0)
}
