export type Kind = 'food' | 'service'
export interface Item { id: string; name: string; desc: string; price: number; cat: string; kind: Kind; available: boolean; tone: string }
export const naira = (n: number) => '₦' + n.toLocaleString('en-NG')
// Prices are placeholders — replace with Dami's real prices.
export const ITEMS: Item[] = [
  { id: 'jr-chicken', name: 'Jollof Rice + Chicken', desc: 'Smoky party-style jollof with grilled chicken.', price: 4500, cat: 'Rice', kind: 'food', available: true, tone: '#D9541E' },
  { id: 'jr-plantain', name: 'Jollof Rice + Fried Plantain', desc: 'Jollof rice with sweet fried plantain.', price: 3000, cat: 'Rice', kind: 'food', available: true, tone: '#D9541E' },
  { id: 'fr-chicken', name: 'Fried Rice + Chicken', desc: 'Veg-packed fried rice with chicken.', price: 4500, cat: 'Rice', kind: 'food', available: true, tone: '#7A9A2E' },
  { id: 'beans-plantain', name: 'Beans + Fried Plantain', desc: 'Slow-cooked beans with fried plantain.', price: 2500, cat: 'Beans', kind: 'food', available: true, tone: '#8A4B22' },
  { id: 'beans-egg', name: 'Beans + Plantain + Egg', desc: 'Beans, plantain and a boiled egg.', price: 3000, cat: 'Beans', kind: 'food', available: true, tone: '#8A4B22' },
  { id: 'js-chicken', name: 'Jollof Spaghetti + Chicken', desc: 'Spaghetti cooked in jollof sauce, with chicken.', price: 4000, cat: 'Pasta', kind: 'food', available: true, tone: '#E0701F' },
  { id: 'sp-egg', name: 'Spaghetti + Egg', desc: 'Simple, filling spaghetti with egg.', price: 2500, cat: 'Pasta', kind: 'food', available: true, tone: '#E7B04A' },
  { id: 'nd-egg', name: 'Noodles + Egg', desc: 'Stir-fried noodles with egg.', price: 2500, cat: 'Pasta', kind: 'food', available: false, tone: '#E7B04A' },
  { id: 'semo-egusi', name: 'Semo + Egusi Soup + Protein', desc: 'Smooth semo with egusi and your choice of protein.', price: 5000, cat: 'Soups', kind: 'food', available: true, tone: '#B8791F' },
  { id: 'semo-veg', name: 'Semo + Vegetable Soup + Protein', desc: 'Semo with rich vegetable soup and protein.', price: 5000, cat: 'Soups', kind: 'food', available: true, tone: '#2E7D32' },
  { id: 'amala-ewedu', name: 'Amala + Ewedu + Protein', desc: 'Amala, ewedu and gbegiri-style stew with protein.', price: 5000, cat: 'Soups', kind: 'food', available: true, tone: '#4A3426' },
  { id: 'svc-chef', name: 'Personal Chef & Catering', desc: 'Meals for individuals, families, events and special occasions.', price: 25000, cat: 'Catering', kind: 'service', available: true, tone: '#0A6A1B' },
  { id: 'svc-clean', name: 'Home Cleaning', desc: 'Keep your home clean, fresh and comfortable.', price: 15000, cat: 'Cleaning', kind: 'service', available: true, tone: '#0A6A1B' },
  { id: 'svc-errand', name: 'Errand Running', desc: "We handle the tasks you don't have time or energy for.", price: 5000, cat: 'Errands', kind: 'service', available: true, tone: '#0A6A1B' },
  { id: 'svc-org', name: 'Home Organization', desc: 'Declutter, arrange and create a more organized living space.', price: 20000, cat: 'Organization', kind: 'service', available: true, tone: '#0A6A1B' },
]
export const FOOD_CATS = ['Rice', 'Beans', 'Pasta', 'Soups']
export const ADDONS = [{ id: 'protein', label: 'Extra protein', price: 1500 }, { id: 'plantain', label: 'Extra plantain', price: 500 }, { id: 'egg', label: 'Boiled egg', price: 300 }]
export const PHONE = '07087349937'
