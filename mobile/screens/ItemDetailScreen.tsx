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
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { createServiceRequest, naira } from '../api'
import { Plate } from '../components/Plate'
import { useCart } from '../cart'
import { useSession } from '../auth'
import { toE164 } from '../data'
import { C } from '../theme'
import type { RootStackParamList } from '../navigation'

export default function ItemDetailScreen() {
  const nav = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const route = useRoute<RouteProp<RootStackParamList, 'ItemDetail'>>()
  const { item } = route.params
  const { add } = useCart()
  const { isAuthenticated, login } = useSession()

  const [qty, setQty] = useState(1)
  const [date, setDate] = useState('')
  const [location, setLocation] = useState('')
  const [details, setDetails] = useState('')
  const [phone, setPhone] = useState('')
  const [busy, setBusy] = useState(false)

  const isService = item.kind === 'service'

  const handleAdd = () => {
    add(item, { qty, preferredDate: date || undefined })
    nav.goBack()
  }

  const handleBook = async () => {
    if (!isAuthenticated) { login(); return }
    if (!location || !details) {
      Alert.alert('Missing info', 'Please fill in location and details.')
      return
    }
    const e164 = toE164(phone)
    if (!e164) {
      Alert.alert('Invalid phone', 'Please enter a valid Nigerian phone number.')
      return
    }
    setBusy(true)
    try {
      await createServiceRequest({
        service_id: item.id,
        preferred_date: date || null,
        location,
        details,
        contact_phone: e164,
      })
      Alert.alert('Request sent', "We'll reach out with a quote shortly.")
      nav.goBack()
    } catch (e) {
      Alert.alert('Could not send request', e instanceof Error ? e.message : 'Try again')
    } finally {
      setBusy(false)
    }
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: C.cream }} contentContainerStyle={{ padding: 20, paddingBottom: 60 }}>
      <Plate item={item} />
      <Text style={styles.tag}>{item.category}</Text>
      <Text style={styles.title}>{item.name}</Text>
      {item.desc ? <Text style={styles.desc}>{item.desc}</Text> : null}
      <Text style={styles.price}>
        {item.price_minor != null ? naira(item.price_minor) : 'Quoted after review'}
      </Text>

      {isService ? (
        <>
          <Text style={styles.fld}>Preferred date (optional)</Text>
          <TextInput
            style={styles.input}
            placeholder="YYYY-MM-DD"
            value={date}
            onChangeText={setDate}
            placeholderTextColor={C.mut}
          />
          <Text style={styles.fld}>Location</Text>
          <TextInput
            style={styles.input}
            value={location}
            onChangeText={setLocation}
            placeholder="Where should we come?"
            placeholderTextColor={C.mut}
          />
          <Text style={styles.fld}>Details</Text>
          <TextInput
            style={[styles.input, { height: 100, textAlignVertical: 'top' }]}
            value={details}
            onChangeText={setDetails}
            placeholder="Tell us what you need…"
            multiline
            placeholderTextColor={C.mut}
          />
          <Text style={styles.fld}>Phone</Text>
          <TextInput
            style={styles.input}
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            placeholder="080…"
            placeholderTextColor={C.mut}
          />
          <Pressable style={[styles.btn, busy && { opacity: 0.5 }]} onPress={handleBook} disabled={busy}>
            <Text style={styles.btnTxt}>{busy ? 'Sending…' : 'Send booking request'}</Text>
          </Pressable>
        </>
      ) : (
        <>
          <View style={styles.qtyRow}>
            <Text style={styles.fld}>Quantity</Text>
            <View style={styles.qty}>
              <Pressable style={styles.qtyBtn} onPress={() => setQty(Math.max(1, qty - 1))}>
                <Text style={styles.qtyTxt}>−</Text>
              </Pressable>
              <Text style={styles.qtyNum}>{qty}</Text>
              <Pressable style={styles.qtyBtn} onPress={() => setQty(qty + 1)}>
                <Text style={styles.qtyTxt}>+</Text>
              </Pressable>
            </View>
          </View>
          <Pressable
            style={[styles.btn, item.sold_out && { opacity: 0.5 }]}
            onPress={handleAdd}
            disabled={item.sold_out}
          >
            <Text style={styles.btnTxt}>
              {item.sold_out ? 'Sold out' : `Add to cart · ${naira((item.price_minor ?? 0) * qty)}`}
            </Text>
          </Pressable>
        </>
      )}
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  tag: { marginTop: 16, color: C.mut, fontWeight: '600', fontSize: 13 },
  title: { fontSize: 28, fontWeight: '800', color: C.green, marginTop: 4 },
  desc: { color: C.mut, marginTop: 8, fontSize: 15, lineHeight: 22 },
  price: { fontSize: 26, fontWeight: '800', marginTop: 14, color: C.ink },
  fld: { marginTop: 18, marginBottom: 6, fontWeight: '600', fontSize: 14, color: C.ink },
  input: {
    borderWidth: 1.5, borderColor: '#C9C58F', borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 12, backgroundColor: '#fff',
    fontSize: 16, color: C.ink,
  },
  qtyRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 22 },
  qty: {
    flexDirection: 'row', alignItems: 'center', borderWidth: 1.5, borderColor: C.green,
    borderRadius: 999, overflow: 'hidden',
  },
  qtyBtn: { width: 40, height: 44, alignItems: 'center', justifyContent: 'center' },
  qtyTxt: { fontSize: 22, color: C.green, fontWeight: '600' },
  qtyNum: { minWidth: 30, textAlign: 'center', fontWeight: '700', fontSize: 16 },
  btn: {
    marginTop: 22, backgroundColor: C.green, borderRadius: 999,
    paddingVertical: 14, alignItems: 'center',
  },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 16 },
})