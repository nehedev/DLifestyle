import AsyncStorage from '@react-native-async-storage/async-storage'
import * as Crypto from 'expo-crypto'
import * as WebBrowser from 'expo-web-browser'
import { useEffect, useRef, useState } from 'react'
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { ApiError, createOrder, createServiceRequest, naira, payOrder } from '../api'
import { useCart, useCatalog } from '../store'
import { useSession } from '../auth'
import { toE164 } from '../data'
import { C } from '../theme'
import type { RootStackParamList } from '../navigation'

const WEB_CALLBACK =
  (process.env.EXPO_PUBLIC_WEB_CALLBACK_URL as string | undefined) ??
  'https://d-lifestyle-blond.vercel.app/payment/callback'

function friendlyError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.detail === 'ordering_closed_for_date')
      return 'That date is closed. Pick another day or check the cutoff time.'
    if (error.detail === 'store_not_configured')
      return 'Ordering is not open yet. Please check back soon.'
    if (typeof error.detail === 'string') return error.detail.replace(/_/g, ' ')
    if (error.detail && typeof error.detail === 'object')
      return 'Some items are no longer available. Please review your cart.'
    return `Request failed (${error.status}).`
  }
  return 'Something went wrong. Please try again.'
}

function tomorrow(): string {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  return date.toISOString().slice(0, 10)
}

/** Today's date as YYYY-MM-DD in an IANA timezone, falling back to UTC. */
function todayIn(timezone: string): string {
  try {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date())
  } catch {
    return new Date().toISOString().slice(0, 10)
  }
}

function addDays(isoDate: string, days: number): string {
  const date = new Date(isoDate + 'T00:00:00Z')
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

export default function CheckoutScreen() {
  const nav = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { lines, itemsTotalMinor, clear } = useCart()
  const { store } = useCatalog()
  const { isAuthenticated, login, isLoading, name } = useSession()
  const idempotencyKey = useRef(Crypto.randomUUID())

  const [form, setForm] = useState({
    name: name ?? '',
    phone: '',
    address: '',
    location: '',
    details: '',
    notes: '',
  })
  const [mode, setMode] = useState<'delivery' | 'pickup'>('delivery')
  const [date, setDate] = useState(tomorrow())
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const minDate = store ? todayIn(store.timezone) : undefined
  const maxDate = store ? addDays(todayIn(store.timezone), store.max_advance_days) : undefined

  useEffect(() => {
    if (!minDate || !maxDate) return
    setDate((current) => (current < minDate ? minDate : current > maxDate ? maxDate : current))
  }, [minDate, maxDate])

  const foodLines = lines.filter((l) => l.kind === 'food')
  const serviceLines = lines.filter((l) => l.kind === 'service')
  const fee = mode === 'delivery' && foodLines.length ? (store?.delivery_fee_minor ?? 0) : 0
  const total = itemsTotalMinor + fee

  const set = (key: keyof typeof form) => (value: string) =>
    setForm((current) => ({ ...current, [key]: value }))

  if (!lines.length) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyTxt}>Your cart is empty.</Text>
        <Pressable
          style={styles.btn}
          onPress={() => nav.navigate('Tabs', { screen: 'Menu' } as never)}
        >
          <Text style={styles.btnTxt}>Browse the menu</Text>
        </Pressable>
      </View>
    )
  }

  const submit = async () => {
    setErr('')
    if (!form.name.trim()) return setErr('Enter your full name.')
    const phone = toE164(form.phone)
    if (!phone) return setErr('Enter a valid Nigerian phone number, e.g. 0708 734 9937.')
    if (foodLines.length && mode === 'delivery' && !form.address.trim())
      return setErr('Enter your address so we know where to deliver.')
    if (serviceLines.length && !form.location.trim())
      return setErr('Tell us the location for the service.')
    if (serviceLines.length && !form.details.trim())
      return setErr('Describe what you need done.')
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date))
      return setErr('Enter the fulfillment date as YYYY-MM-DD.')
    if (!isAuthenticated) {
      login()
      return
    }

    setBusy(true)
    try {
      for (const line of serviceLines) {
        await createServiceRequest({
          service_id: line.id,
          preferred_date: line.preferred_date ?? null,
          location: form.location,
          details: form.details,
          contact_phone: phone,
        })
      }

      if (foodLines.length) {
        const order = await createOrder(
          {
            items: foodLines.map((l) => ({ menu_item_id: l.id, quantity: l.qty })),
            fulfillment_type: mode,
            fulfillment_date: date,
            contact: {
              name: form.name,
              phone,
              address: mode === 'delivery' ? form.address : null,
            },
            notes: form.notes || null,
          },
          idempotencyKey.current,
        )
        const { authorization_url } = await payOrder(order.id)
        await AsyncStorage.multiSet([
          ['damis.lastOrderId', String(order.id)],
          ['damis.pending_payment_order', String(order.id)],
        ])
        clear()
        await WebBrowser.openAuthSessionAsync(authorization_url, WEB_CALLBACK)
        nav.replace('PaymentCallback', { orderId: order.id })
        return
      }

      clear()
      nav.navigate('Tabs', { screen: 'Orders' } as never)
    } catch (error) {
      setErr(friendlyError(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: C.cream }}
      contentContainerStyle={{ padding: 20, paddingBottom: 60 }}
    >
      <View style={styles.section}>
        <Text style={styles.h2}>Your details</Text>
        <Text style={styles.fld}>Full name</Text>
        <TextInput style={styles.input} value={form.name} onChangeText={set('name')} />
        <Text style={styles.fld}>Phone number</Text>
        <TextInput
          style={styles.input}
          value={form.phone}
          onChangeText={set('phone')}
          keyboardType="phone-pad"
          placeholder="0708 734 9937"
          placeholderTextColor={C.mut}
        />
      </View>

      {foodLines.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.h2}>Delivery</Text>
          <View style={styles.radios}>
            {(['delivery', 'pickup'] as const).map((f) => (
              <Pressable
                key={f}
                style={[styles.radio, mode === f && styles.radioOn]}
                onPress={() => setMode(f)}
              >
                <View style={[styles.dot, mode === f && styles.dotOn]} />
                <Text style={styles.radioTxt}>{f === 'delivery' ? 'Delivery' : 'Pickup'}</Text>
                <Text style={styles.radioPrice}>
                  {f === 'delivery' ? naira(store?.delivery_fee_minor ?? 0) : 'Free'}
                </Text>
              </Pressable>
            ))}
          </View>

          {mode === 'delivery' && (
            <>
              <Text style={styles.fld}>Address</Text>
              <TextInput
                style={[styles.input, { height: 80, textAlignVertical: 'top' }]}
                value={form.address}
                onChangeText={set('address')}
                multiline
              />
            </>
          )}

          <Text style={styles.fld}>Fulfillment date</Text>
          <TextInput
            style={styles.input}
            value={date}
            onChangeText={setDate}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={C.mut}
          />
          {store && (
            <Text style={styles.hint}>
              Order by {store.order_cutoff_time} · up to {store.max_advance_days} days ahead
            </Text>
          )}

          <Text style={styles.fld}>Notes for Dami (optional)</Text>
          <TextInput
            style={[styles.input, { height: 80, textAlignVertical: 'top' }]}
            value={form.notes}
            onChangeText={set('notes')}
            placeholder="Spice level, gate code…"
            placeholderTextColor={C.mut}
            multiline
          />
        </View>
      )}

      {serviceLines.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.h2}>Service details</Text>
          <Text style={styles.fld}>Location</Text>
          <TextInput style={styles.input} value={form.location} onChangeText={set('location')} />
          <Text style={styles.fld}>What do you need done?</Text>
          <TextInput
            style={[styles.input, { height: 90, textAlignVertical: 'top' }]}
            value={form.details}
            onChangeText={set('details')}
            multiline
          />
        </View>
      )}

      <View style={styles.summary}>
        <Text style={styles.h2}>Order summary</Text>
        {foodLines.map((l) => (
          <View key={l.key} style={styles.row}>
            <Text style={styles.lbl}>{l.qty} × {l.name}</Text>
            <Text>{naira(l.unit_price_minor * l.qty)}</Text>
          </View>
        ))}
        {serviceLines.map((l) => (
          <View key={l.key} style={styles.row}>
            <Text style={styles.lbl}>{l.name}</Text>
            <Text>On request</Text>
          </View>
        ))}
        <View style={styles.divider} />
        <View style={styles.row}>
          <Text style={styles.lbl}>Subtotal</Text>
          <Text>{naira(itemsTotalMinor)}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.lbl}>Delivery fee</Text>
          <Text>{naira(fee)}</Text>
        </View>
        <View style={[styles.row, styles.rowTotal]}>
          <Text style={{ fontWeight: '800', fontSize: 17 }}>Total</Text>
          <Text style={{ fontWeight: '800', fontSize: 17 }}>{naira(total)}</Text>
        </View>

        {err ? (
          <Text style={styles.err} accessibilityRole="alert">
            {err}
          </Text>
        ) : null}

        <Pressable
          style={[styles.btn, (busy || isLoading) && { opacity: 0.5 }]}
          onPress={submit}
          disabled={busy || isLoading}
        >
          <Text style={styles.btnTxt}>
            {busy
              ? 'Working…'
              : foodLines.length
                ? `Pay ${naira(total)}`
                : 'Send request'}
          </Text>
        </Pressable>
        <Text style={styles.note}>
          {isAuthenticated
            ? 'Secure payment by card or transfer. You will get a confirmation.'
            : 'You will be asked to sign in before we take your order.'}
        </Text>
      </View>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  empty: {
    flex: 1, backgroundColor: C.cream, alignItems: 'center',
    justifyContent: 'center', padding: 30, gap: 14,
  },
  emptyTxt: { color: C.mut, fontSize: 16 },
  section: {
    backgroundColor: '#fff', borderRadius: 14, padding: 20, marginBottom: 14,
    borderWidth: 1, borderColor: C.line,
  },
  h2: { fontSize: 22, fontWeight: '800', color: C.green, marginBottom: 12 },
  radios: { gap: 10, marginBottom: 8 },
  radio: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    borderWidth: 1.5, borderColor: C.line, borderRadius: 12, padding: 14,
  },
  radioOn: { borderColor: C.green, backgroundColor: '#F1F9E8' },
  dot: {
    width: 18, height: 18, borderRadius: 9, borderWidth: 2, borderColor: C.line,
  },
  dotOn: { borderColor: C.green, backgroundColor: C.green },
  radioTxt: { fontWeight: '600', flex: 1 },
  radioPrice: { color: C.mut, fontSize: 13 },
  fld: { marginTop: 12, marginBottom: 6, fontWeight: '600', fontSize: 14 },
  hint: { color: C.mut, fontSize: 12, marginTop: 6 },
  input: {
    borderWidth: 1.5, borderColor: '#C9C58F', borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 12, backgroundColor: '#fff',
    fontSize: 16, color: C.ink,
  },
  summary: {
    backgroundColor: '#fff', borderRadius: 14, padding: 20,
    borderWidth: 1, borderColor: C.line,
  },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4, gap: 10 },
  lbl: { color: C.mut, fontSize: 15, flex: 1 },
  divider: { borderTopWidth: 1, borderTopColor: C.line, marginVertical: 8 },
  rowTotal: { borderTopWidth: 2, borderTopColor: C.ink, marginTop: 8, paddingTop: 12 },
  err: { color: C.burg, marginTop: 12 },
  btn: {
    marginTop: 16, backgroundColor: C.green, borderRadius: 999,
    paddingVertical: 14, alignItems: 'center',
  },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 16 },
  note: { color: C.mut, fontSize: 12, marginTop: 12, textAlign: 'center' },
})
