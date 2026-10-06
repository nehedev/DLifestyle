import { useState } from 'react'
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { createOrder, naira } from '../api'
import { useCart } from '../cart'
import { useSession } from '../auth'
import { toE164 } from '../data'
import { C } from '../theme'
import type { RootStackParamList } from '../navigation'

const tomorrow = () => {
  const d = new Date(Date.now() + 24 * 3600 * 1000)
  return d.toISOString().slice(0, 10)
}

export default function CheckoutScreen() {
  const nav = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { lines, subtotalMinor, clear } = useCart()
  const { name } = useSession()

  const [fulfillment, setFulfillment] = useState<'delivery' | 'pickup'>('delivery')
  const [date, setDate] = useState(tomorrow())
  const [contactName, setContactName] = useState(name ?? '')
  const [phone, setPhone] = useState('')
  const [address, setAddress] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)

  const foodLines = lines.filter((l) => l.kind === 'food')

  const submit = async () => {
    if (!contactName || !phone) {
      Alert.alert('Missing info', 'Please enter your name and phone.')
      return
    }
    if (fulfillment === 'delivery' && !address) {
      Alert.alert('Missing address', 'Delivery requires an address.')
      return
    }
    const e164 = toE164(phone)
    if (!e164) {
      Alert.alert('Invalid phone', 'Please enter a valid Nigerian phone number.')
      return
    }
    setBusy(true)
    try {
      const idempotencyKey = `order-${Date.now()}-${Math.random().toString(36).slice(2)}`
      const order = await createOrder(
        {
          items: foodLines.map((l) => ({ menu_item_id: l.id, quantity: l.qty })),
          fulfillment_type: fulfillment,
          fulfillment_date: date,
          contact: {
            name: contactName,
            phone: e164,
            address: fulfillment === 'delivery' ? address : null,
          },
          notes: notes || null,
        },
        idempotencyKey,
      )
      clear()
      nav.replace('Confirmation', { order })
    } catch (e) {
      Alert.alert('Order failed', e instanceof Error ? e.message : 'Try again')
    } finally {
      setBusy(false)
    }
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: C.cream }} contentContainerStyle={{ padding: 20, paddingBottom: 60 }}>
      <View style={styles.section}>
        <Text style={styles.h2}>Fulfillment</Text>
        <View style={styles.radios}>
          {(['delivery', 'pickup'] as const).map((f) => (
            <Pressable
              key={f}
              style={[styles.radio, fulfillment === f && styles.radioOn]}
              onPress={() => setFulfillment(f)}
            >
              <View style={[styles.dot, fulfillment === f && styles.dotOn]} />
              <Text style={styles.radioTxt}>
                {f === 'delivery' ? 'Delivery' : 'Pickup'}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.fld}>Date</Text>
        <TextInput style={styles.input} value={date} onChangeText={setDate} placeholder="YYYY-MM-DD" />

        <Text style={styles.fld}>Name</Text>
        <TextInput style={styles.input} value={contactName} onChangeText={setContactName} />

        <Text style={styles.fld}>Phone</Text>
        <TextInput
          style={styles.input}
          value={phone}
          onChangeText={setPhone}
          keyboardType="phone-pad"
          placeholder="080…"
        />

        {fulfillment === 'delivery' && (
          <>
            <Text style={styles.fld}>Address</Text>
            <TextInput
              style={[styles.input, { height: 80, textAlignVertical: 'top' }]}
              value={address}
              onChangeText={setAddress}
              multiline
            />
          </>
        )}

        <Text style={styles.fld}>Notes (optional)</Text>
        <TextInput
          style={[styles.input, { height: 80, textAlignVertical: 'top' }]}
          value={notes}
          onChangeText={setNotes}
          multiline
        />
      </View>

      <View style={styles.summary}>
        <Text style={styles.h2}>Summary</Text>
        <View style={styles.row}>
          <Text style={styles.lbl}>Items ({foodLines.length})</Text>
          <Text>{naira(subtotalMinor)}</Text>
        </View>
        <View style={[styles.row, { borderTopWidth: 2, borderTopColor: C.ink, marginTop: 8, paddingTop: 12 }]}>
          <Text style={{ fontWeight: '800', fontSize: 17 }}>Total due</Text>
          <Text style={{ fontWeight: '800', fontSize: 17 }}>{naira(subtotalMinor)}</Text>
        </View>
        <Pressable
          style={[styles.btn, busy && { opacity: 0.5 }]}
          onPress={submit}
          disabled={busy}
        >
          <Text style={styles.btnTxt}>{busy ? 'Placing…' : 'Place order'}</Text>
        </Pressable>
      </View>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
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
  radioTxt: { fontWeight: '600' },
  fld: { marginTop: 12, marginBottom: 6, fontWeight: '600', fontSize: 14 },
  input: {
    borderWidth: 1.5, borderColor: '#C9C58F', borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 12, backgroundColor: '#fff',
    fontSize: 16, color: C.ink,
  },
  summary: {
    backgroundColor: '#fff', borderRadius: 14, padding: 20,
    borderWidth: 1, borderColor: C.line,
  },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  lbl: { color: C.mut, fontSize: 15 },
  btn: {
    marginTop: 16, backgroundColor: C.green, borderRadius: 999,
    paddingVertical: 14, alignItems: 'center',
  },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 16 },
})