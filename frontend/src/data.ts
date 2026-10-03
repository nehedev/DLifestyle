export const PHONE = '07087349937'

const TONES: Record<string, string> = {
  Rice: '#D9541E',
  Beans: '#8A4B22',
  Pasta: '#E0701F',
  Soups: '#B8791F',
}

export const toneFor = (category: string) => TONES[category] ?? '#0A6A1B'

/** Convert common Nigerian phone formats to E.164 for the backend. */
export function toE164(input: string): string | null {
  const digits = input.replace(/[^\d+]/g, '')
  if (/^\+[1-9]\d{7,14}$/.test(digits)) return digits
  if (/^0\d{10}$/.test(digits)) return '+234' + digits.slice(1)
  if (/^234\d{10}$/.test(digits)) return '+' + digits
  return null
}
