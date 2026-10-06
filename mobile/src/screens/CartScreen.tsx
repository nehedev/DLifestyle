import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { naira } from '../api'
import { Header } from '../components/Header'
import { useCart, useCatalog } from '../store'
import { C } from '../theme'
import type { RootStackParamList } from '../navigation'

export default function CartScreen() {
  const nav = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { lines, itemsTotalMinor, setQty, remove } = useCart()
  const { store } = useCatalog()

  const hasFood = lines.some((l) => l.kind === 'food')
  const fee = hasFood ? (store?.delivery_fee_minor ?? 0) : 0
  const total = itemsTotalMinor + fee

  if (lines.length === 0) {
    return (
      <View style={{ flex: 1, backgroundColor: C.cream }}>
        <Header />
        <View style={styles.empty}>
          <Text style={{ fontSize: 46 }}>🛒</Text>
          <Text style={styles.emptyH}>Your cart is empty</Text>
          <Text style={styles.emptyTxt}>Pick a meal or request a service to get started.</Text>
          <Pressable
            style={styles.btn}
            onPress={() => nav.navigate('Tabs', { screen: 'Menu' } as never)}
          >
            <Text style={styles.btnTxt}>Browse the menu</Text>
          </Pressable>
        </View>
      </View>
    )
  }

  return (
    <View style={{ flex: 1, backgroundColor: C.cream }}>
      <Header />
      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 60 }}>
        <Text style={styles.h2}>Your cart</Text>

        {lines.map((line) => (
          <View key={line.key} style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{line.name}</Text>
              <Text style={styles.unit}>
                {line.kind === 'service'
                  ? line.preferred_date
                    ? `Preferred date: ${line.preferred_date}`
                    : 'Service request'
                  : 'Meal'}
                {line.available === false ? ' · Currently unavailable' : ''}
              </Text>
              <View style={styles.lineActions}>
                {line.kind === 'food' && (
                  <View style={styles.qty}>
                    <Pressable style={styles.qtyBtn} onPress={() => setQty(line.key, line.qty - 1)}>
                      <Text style={styles.qtyTxt}>−</Text>
                    </Pressable>
                    <Text style={styles.qtyNum}>{line.qty}</Text>
                    <Pressable style={styles.qtyBtn} onPress={() => setQty(line.key, line.qty + 1)}>
                      <Text style={styles.qtyTxt}>+</Text>
                    </Pressable>
                  </View>
                )}
                <Pressable onPress={() => remove(line.key)}>
                  <Text style={styles.remove}>Remove</Text>
                </Pressable>
              </View>
            </View>
            <Text style={styles.lineTotal}>
              {line.kind === 'service'
                ? 'On request'
                : naira(line.unit_price_minor * line.qty)}
            </Text>
          </View>
        ))}

        <View style={styles.summary}>
          <View style={styles.sumRow}>
            <Text style={styles.sumLbl}>Subtotal</Text>
            <Text style={styles.sumVal}>{naira(itemsTotalMinor)}</Text>
          </View>
          <View style={styles.sumRow}>
            <Text style={styles.sumLbl}>Delivery fee (if chosen)</Text>
            <Text style={styles.sumVal}>{naira(fee)}</Text>
          </View>
          <View style={[styles.sumRow, styles.sumTotalRow]}>
            <Text style={styles.sumTotal}>Total</Text>
            <Text style={styles.sumTotal}>{naira(total)}</Text>
          </View>
          <Text style={styles.note}>
            Services are quoted separately. Final delivery fee is set at checkout; pickup is free.
          </Text>

          <Pressable style={styles.btn} onPress={() => nav.navigate('Checkout')}>
            <Text style={styles.btnTxt}>Proceed to checkout</Text>
          </Pressable>
          <Pressable onPress={() => nav.navigate('Tabs', { screen: 'Menu' } as never)}>
            <Text style={styles.continue}>Continue shopping</Text>
          </Pressable>
        </View>
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  h2: { fontSize: 30, fontWeight: '800', color: C.green, marginBottom: 20 },
  empty: { alignItems: 'center', paddingTop: 60, paddingHorizontal: 30, gap: 10 },
  emptyH: { fontSize: 24, fontWeight: '800', color: C.green, marginTop: 8 },
  emptyTxt: { color: C.mut, fontSize: 15, textAlign: 'center' },
  row: {
    flexDirection: 'row', alignItems: 'flex-start',
    backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 10,
    borderWidth: 1, borderColor: C.line,
  },
  name: { fontWeight: '700', fontSize: 16, color: C.ink },
  unit: { color: C.mut, fontSize: 13, marginTop: 2 },
  lineActions: { flexDirection: 'row', alignItems: 'center', gap: 16, marginTop: 10 },
  qty: {
    flexDirection: 'row', alignItems: 'center',
    borderWidth: 1.5, borderColor: C.green, borderRadius: 999, overflow: 'hidden',
  },
  qtyBtn: { width: 34, height: 34, alignItems: 'center', justifyContent: 'center' },
  qtyTxt: { fontSize: 18, color: C.green, fontWeight: '600' },
  qtyNum: { minWidth: 26, textAlign: 'center', fontWeight: '700' },
  remove: { color: C.burg, fontWeight: '600', fontSize: 14 },
  lineTotal: { fontWeight: '700', color: C.ink, marginLeft: 10 },
  summary: {
    backgroundColor: '#fff', borderRadius: 14, padding: 20, marginTop: 20,
    borderWidth: 1, borderColor: C.line,
  },
  sumRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  sumLbl: { color: C.mut, fontSize: 15 },
  sumVal: { color: C.ink, fontSize: 15 },
  sumTotalRow: {
    borderTopWidth: 2, borderTopColor: C.ink, marginTop: 8, paddingTop: 12,
  },
  sumTotal: { fontWeight: '800', fontSize: 18 },
  note: { color: C.mut, fontSize: 13, marginTop: 10 },
  btn: {
    marginTop: 16, backgroundColor: C.green, borderRadius: 999,
    paddingVertical: 14, alignItems: 'center', paddingHorizontal: 24,
  },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 16 },
  continue: {
    marginTop: 14, color: C.green, fontWeight: '600', textAlign: 'center',
    textDecorationLine: 'underline',
  },
})
