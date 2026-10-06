import { useState } from 'react'
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native'
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { naira } from '../api'
import { Plate } from '../components/Plate'
import { useCart, useCatalog } from '../store'
import { C } from '../theme'
import type { RootStackParamList } from '../navigation'

export default function ItemDetailScreen() {
  const nav = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const route = useRoute<RouteProp<RootStackParamList, 'ItemDetail'>>()
  const { item } = route.params
  const { add } = useCart()
  const { items } = useCatalog()

  const [qty, setQty] = useState(1)
  const [date, setDate] = useState('')

  const svc = item.kind === 'service'
  const related = items
    .filter((i) => i.kind === item.kind && i.key !== item.key)
    .slice(0, 4)

  const addToCart = () => {
    add(item, svc ? 1 : qty, svc ? date || undefined : undefined)
    nav.navigate('Tabs', { screen: 'Cart' } as never)
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: C.cream }}
      contentContainerStyle={{ padding: 20, paddingBottom: 60 }}
    >
      <Plate item={item} />
      <Text style={styles.tag}>{svc ? 'Service' : item.category}</Text>
      <Text style={styles.title}>{item.name}</Text>
      {item.desc ? <Text style={styles.desc}>{item.desc}</Text> : null}
      <Text style={styles.price}>
        {svc ? 'Price on request' : naira(item.price_minor ?? 0)}
      </Text>

      {svc ? (
        <>
          <Text style={styles.fld}>Preferred date</Text>
          <TextInput
            style={styles.input}
            placeholder="YYYY-MM-DD"
            value={date}
            onChangeText={setDate}
            placeholderTextColor={C.mut}
          />
          <Text style={styles.note}>
            Final price is confirmed after we talk through your needs. You pay only after we agree.
          </Text>
        </>
      ) : (
        <Text style={styles.note}>
          Tell us about spice level, protein choices or anything else in the notes at checkout.
        </Text>
      )}

      <View style={styles.buy}>
        {!svc && (
          <View style={styles.qty}>
            <Pressable style={styles.qtyBtn} onPress={() => setQty(Math.max(1, qty - 1))}>
              <Text style={styles.qtyTxt}>−</Text>
            </Pressable>
            <Text style={styles.qtyNum}>{qty}</Text>
            <Pressable style={styles.qtyBtn} onPress={() => setQty(qty + 1)}>
              <Text style={styles.qtyTxt}>+</Text>
            </Pressable>
          </View>
        )}
        <Pressable
          style={[styles.btn, item.sold_out && { opacity: 0.5 }]}
          onPress={addToCart}
          disabled={item.sold_out}
        >
          <Text style={styles.btnTxt}>
            {item.sold_out
              ? 'Sold out'
              : svc
                ? 'Request this service'
                : `Add to cart · ${naira((item.price_minor ?? 0) * qty)}`}
          </Text>
        </Pressable>
      </View>

      {related.length > 0 && (
        <>
          <Text style={styles.sub}>You may also like</Text>
          {related.map((i) => (
            <Pressable
              key={i.key}
              style={styles.related}
              onPress={() => nav.replace('ItemDetail', { item: i })}
            >
              <View style={{ width: 72 }}>
                <Plate item={i} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.cardTitle}>{i.name}</Text>
                <Text style={styles.price}>
                  {i.kind === 'service' ? 'On request' : naira(i.price_minor ?? 0)}
                </Text>
              </View>
            </Pressable>
          ))}
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
  note: { color: C.mut, marginTop: 12, fontSize: 14, lineHeight: 20 },
  fld: { marginTop: 18, marginBottom: 6, fontWeight: '600', fontSize: 14, color: C.ink },
  input: {
    borderWidth: 1.5, borderColor: '#C9C58F', borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 12, backgroundColor: '#fff',
    fontSize: 16, color: C.ink,
  },
  buy: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 22 },
  qty: {
    flexDirection: 'row', alignItems: 'center', borderWidth: 1.5, borderColor: C.green,
    borderRadius: 999, overflow: 'hidden',
  },
  qtyBtn: { width: 40, height: 46, alignItems: 'center', justifyContent: 'center' },
  qtyTxt: { fontSize: 22, color: C.green, fontWeight: '600' },
  qtyNum: { minWidth: 30, textAlign: 'center', fontWeight: '700', fontSize: 16 },
  btn: {
    flex: 1, backgroundColor: C.green, borderRadius: 999,
    paddingVertical: 14, alignItems: 'center',
  },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
  sub: { fontSize: 20, fontWeight: '800', color: C.green, marginTop: 32, marginBottom: 12 },
  related: {
    flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#fff',
    borderRadius: 14, padding: 10, marginBottom: 10, borderWidth: 1, borderColor: C.line,
  },
  cardTitle: { fontWeight: '700', fontSize: 16, color: C.ink },
})
