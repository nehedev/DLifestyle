import { useEffect, useMemo, useState } from 'react'
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native'
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { getMenu, getServices, naira, type MenuItem, type Service } from '../api'
import { Header } from '../components/Header'
import { Plate } from '../components/Plate'
import { useCart } from '../cart'
import { C } from '../theme'
import { foodKey, serviceKey, type CatalogItem, type Kind } from '../types'
import type { RootStackParamList, TabParamList } from '../navigation'

const toItem = (kind: Kind, x: MenuItem | Service): CatalogItem => {
  if (kind === 'food') {
    const m = x as MenuItem
    return {
      kind, id: m.id, key: foodKey(m.id), name: m.name,
      desc: m.description ?? '', price_minor: m.price_minor,
      category: m.category, image_url: m.image_url, image_alt: m.image_alt,
      sold_out: m.is_sold_out, weekdays: m.weekdays,
    }
  }
  const s = x as Service
  return {
    kind, id: s.id, key: serviceKey(s.id), name: s.name,
    desc: s.description, price_minor: null, category: 'Services',
    image_url: null, image_alt: null, sold_out: false,
    weekdays: [0, 1, 2, 3, 4, 5, 6],
  }
}

export default function MenuScreen() {
  const nav = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const route = useRoute<RouteProp<TabParamList, 'Menu'>>()
  const { add } = useCart()
  const [kind, setKind] = useState<Kind>(route.params?.svc ? 'service' : 'food')
  const [menu, setMenu] = useState<MenuItem[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [q, setQ] = useState('')
  const [category, setCategory] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getMenu(), getServices()])
      .then(([m, s]) => { setMenu(m); setServices(s) })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (route.params?.svc) setKind('service')
  }, [route.params?.svc])

  const categories = useMemo(() => {
    if (kind === 'service') return []
    return Array.from(new Set(menu.map((m) => m.category)))
  }, [kind, menu])

  const items: CatalogItem[] = useMemo(() => {
    const raw: CatalogItem[] =
      kind === 'food' ? menu.map((m) => toItem('food', m)) : services.map((s) => toItem('service', s))
    return raw.filter((i) => {
      if (category && i.category !== category) return false
      if (q && !i.name.toLowerCase().includes(q.toLowerCase())) return false
      return true
    })
  }, [kind, menu, services, category, q])

  return (
    <View style={{ flex: 1, backgroundColor: C.cream }}>
      <Header />
      <FlatList
        data={items}
        keyExtractor={(i) => i.key}
        ListHeaderComponent={
          <View style={{ padding: 20 }}>
            <Text style={styles.h2}>{kind === 'food' ? 'Menu' : 'Services'}</Text>

            <View style={styles.seg}>
              <Pressable
                style={[styles.segBtn, kind === 'food' && styles.segOn]}
                onPress={() => { setKind('food'); setCategory(null) }}
              >
                <Text style={[styles.segTxt, kind === 'food' && styles.segTxtOn]}>Food</Text>
              </Pressable>
              <Pressable
                style={[styles.segBtn, kind === 'service' && styles.segOn]}
                onPress={() => { setKind('service'); setCategory(null) }}
              >
                <Text style={[styles.segTxt, kind === 'service' && styles.segTxtOn]}>Services</Text>
              </Pressable>
            </View>

            {kind === 'food' && (
              <>
                <TextInput
                  placeholder="Search menu…"
                  value={q}
                  onChangeText={setQ}
                  style={styles.input}
                  placeholderTextColor={C.mut}
                />
                <View style={styles.chips}>
                  <Pressable
                    style={[styles.chip, !category && styles.chipOn]}
                    onPress={() => setCategory(null)}
                  >
                    <Text style={[styles.chipTxt, !category && styles.chipTxtOn]}>All</Text>
                  </Pressable>
                  {categories.map((c) => (
                    <Pressable
                      key={c}
                      style={[styles.chip, category === c && styles.chipOn]}
                      onPress={() => setCategory(c)}
                    >
                      <Text style={[styles.chipTxt, category === c && styles.chipTxtOn]}>{c}</Text>
                    </Pressable>
                  ))}
                </View>
              </>
            )}

            {loading && <ActivityIndicator color={C.green} style={{ marginTop: 20 }} />}
          </View>
        }
        renderItem={({ item }) => (
          <Pressable
            style={styles.card}
            onPress={() => nav.navigate('ItemDetail', { item })}
          >
            <Plate item={item} />
            <View style={styles.cardBody}>
              <Text style={styles.cardTag}>{item.category}</Text>
              <Text style={styles.cardTitle}>{item.name}</Text>
              {item.desc ? (
                <Text style={styles.cardDesc} numberOfLines={2}>{item.desc}</Text>
              ) : null}
              <View style={styles.cardFoot}>
                <Text style={styles.price}>
                  {item.price_minor != null ? naira(item.price_minor) : 'Quoted'}
                </Text>
                <Pressable
                  style={styles.addBtn}
                  onPress={() => add(item)}
                  disabled={item.sold_out || item.kind === 'service'}
                >
                  <Text style={styles.addBtnTxt}>
                    {item.sold_out ? 'Sold out' : item.kind === 'service' ? 'Book' : 'Add'}
                  </Text>
                </Pressable>
              </View>
            </View>
          </Pressable>
        )}
        contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40 }}
        ListEmptyComponent={
          !loading ? (
            <Text style={{ textAlign: 'center', color: C.mut, padding: 40 }}>
              Nothing found.
            </Text>
          ) : null
        }
      />
    </View>
  )
}

const styles = StyleSheet.create({
  h2: { fontSize: 30, fontWeight: '800', color: C.green, marginBottom: 16 },
  seg: {
    flexDirection: 'row', borderWidth: 1.5, borderColor: C.green, borderRadius: 999,
    overflow: 'hidden', alignSelf: 'flex-start', marginBottom: 16,
  },
  segBtn: { paddingHorizontal: 18, paddingVertical: 10 },
  segOn: { backgroundColor: C.green },
  segTxt: { color: C.green, fontWeight: '600', fontSize: 14 },
  segTxtOn: { color: '#fff' },
  input: {
    borderWidth: 1.5, borderColor: '#C9C58F', borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 12, backgroundColor: '#fff',
    fontSize: 16, color: C.ink, marginBottom: 12,
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  chip: {
    borderWidth: 1.5, borderColor: C.line, backgroundColor: '#fff',
    borderRadius: 999, paddingHorizontal: 14, paddingVertical: 7,
  },
  chipOn: { backgroundColor: C.gold, borderColor: C.gold },
  chipTxt: { fontWeight: '600', fontSize: 13, color: C.green },
  chipTxtOn: { color: C.ink },
  card: {
    backgroundColor: '#fff', borderRadius: 24, padding: 12, marginBottom: 14,
    shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 }, elevation: 2,
  },
  cardBody: { paddingTop: 10, gap: 4 },
  cardTag: { fontSize: 12, color: C.mut, fontWeight: '600' },
  cardTitle: { fontSize: 18, fontWeight: '700', color: C.ink },
  cardDesc: { fontSize: 14, color: C.mut },
  cardFoot: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 },
  price: { fontSize: 17, fontWeight: '800', color: C.green },
  addBtn: { backgroundColor: C.green, paddingHorizontal: 16, paddingVertical: 8, borderRadius: 12 },
  addBtnTxt: { color: '#fff', fontWeight: '700', fontSize: 14 },
})