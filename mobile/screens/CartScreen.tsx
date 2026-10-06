import { useState } from 'react'
import {
  Alert,
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
import { useCart } from '../cart'
import { useSession } from '../auth'
import { C } from '../theme'
import type { RootStackParamList } from '../navigation'

export default function CartScreen() {
  const nav = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { lines, subtotalMinor, updateQty, remove, clear } = useCart()
  const { isAuthenticated, login } = useSession()
  const [busy, setBusy] = useState(false)

  const foodLines = lines.filter((l) => l.kind === 'food')
  const serviceLines = lines.filter((l) => l.kind === 'service')

  const proceed = () => {
    if (!isAuthenticated) { login(); return }
    if (foodLines.length === 0) {
      Alert.alert('No food items', 'Add a dish to place an order.')
      return
    }
    nav.navigate('Checkout')
  }

  const confirmClear = () => {
    Alert.alert('Clear cart?', 'This removes all items.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear', style: 'destructive', onPress: clear },
    ])
  }

  return (
    <View style={{ flex: 1, backgroundColor: C.cream }}>
      <Header />
      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 60 }}>
        <Text style={styles.h2}>Your cart</Text>

        {lines.length === 0 ? (
          <View style={styles.empty}>
            <Text style={{ fontSize: 46 }}>🛒</Text>
            <Text style={styles.emptyTxt}>Your cart is empty.</Text>
            <Pressable
              style={styles.btn}
              onPress={() => nav.navigate('Tabs', { screen: 'Menu' } as never)}
            >
              <Text style={styles.btnTxt}>Browse menu</Text>
            </Pressable>
          </View>
        ) : (
          <>
            {foodLines.map((l) => (
              <View key={l.key} style={styles.row}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.name}>{l.name}</Text>
                  <Text style={styles.unit}>{naira(l.unit_price_minor)} each</Text>
                </View>
                <View style={styles.qty}>
                  <Pressable style={styles.qtyBtn} onPress={() => updateQty(l.key, l.qty - 1)}>
                    <Text style={styles.qtyTxt}>−</Text>
                  </Pressable>
                  <Text style={styles.qtyNum}>{l.qty}</Text>
                  <Pressable style={styles.qtyBtn} onPress={() => updateQty(l.key, l.qty + 1)}>
                    <Text style={styles.qtyTxt}>+</Text>
                  </Pressable>
                </View>
                <Pressable onPress={() => remove(l.key)} style={{ marginLeft: 10 }}>
                  <Text style={styles.remove}>✕</Text>
                </Pressable>
              </View>
            ))}

            {serviceLines.length > 0 && (
              <>
                <Text style={styles.subH}>Service bookings</Text>
                {serviceLines.map((l) => (
                  <View key={l.key} style={styles.row}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.name}>{l.name}</Text>
                      <Text style={styles.unit}>
                        {l.preferred_date ? `Preferred: ${l.preferred_date}` : 'No preferred date'}
                      </Text>
                    </View>
                    <Pressable onPress={() => remove(l.key)}>
                      <Text style={styles.remove}>✕</Text>
                    </Pressable>
                  </View>
                ))}
              </>
            )}

            <View style={styles.summary}>
              <View style={styles.sumRow}>
                <Text style={styles.sumLbl}>Subtotal</Text>
                <Text style={styles.sumVal}>{naira(subtotalMinor)}</Text>
              </View>
              <View style={[styles.sumRow, { borderTopWidth: 2, borderTopColor: C.ink, marginTop: 8, paddingTop: 12 }]}>
                <Text style={styles.sumTotalLbl}>Total</Text>
                <Text style={styles.sumTotalVal}>{naira(subtotalMinor)}</Text>
              </View>
              <Text style={styles.note}>Delivery fees (if any) are added at checkout.</Text>

              <Pressable style={styles.btn} onPress={proceed} disabled={busy}>
                <Text style={styles.btnTxt}>Proceed to checkout</Text>
              </Pressable>
              <Pressable style={styles.clearBtn} onPress={confirmClear}>
                <Text style={styles.clearTxt}>Clear cart</Text>
              </Pressable>
            </View>
          </>
        )}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  h2: { fontSize: 30, fontWeight: '800', color: C.green, marginBottom: 20 },
  empty: { alignItems: 'center', paddingTop: 40, gap: 14 },
  emptyTxt: { color: C.mut, fontSize: 16 },
  row: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 10,
    borderWidth: 1, borderColor: C.line,
  },
  name: { fontWeight: '700', fontSize: 16, color: C.ink },
  unit: { color: C.mut, fontSize: 13, marginTop: 2 },
  qty: {
    flexDirection: 'row', alignItems: 'center',
    borderWidth: 1.5, borderColor: C.green, borderRadius: 999, overflow: 'hidden',
  },
  qtyBtn: { width: 34, height: 36, alignItems: 'center', justifyContent: 'center' },
  qtyTxt: { fontSize: 18, color: C.green, fontWeight: '600' },
  qtyNum: { minWidth: 26, textAlign: 'center', fontWeight: '700' },
  remove: { color: C.mut, fontSize: 18, paddingHorizontal: 6 },
  subH: { marginTop: 16, marginBottom: 8, fontWeight: '700', color: C.mut },
  summary: {
    backgroundColor: '#fff', borderRadius: 14, padding: 20, marginTop: 20,
    borderWidth: 1, borderColor: C.line,
  },
  sumRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  sumLbl: { color: C.mut, fontSize: 15 },
  sumVal: { color: C.ink, fontSize: 15 },
  sumTotalLbl: { fontWeight: '800', fontSize: 18 },
  sumTotalVal: { fontWeight: '800', fontSize: 18 },
  note: { color: C.mut, fontSize: 13, marginTop: 10 },
  btn: {
    marginTop: 16, backgroundColor: C.green, borderRadius: 999,
    paddingVertical: 14, alignItems: 'center',
  },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 16 },
  clearBtn: { marginTop: 12, alignItems: 'center' },
  clearTxt: { color: C.burg, fontWeight: '600', fontSize: 14 },
})