import { router, useLocalSearchParams } from 'expo-router'
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
import { naira } from '@/api'
import { Header } from '@/components/Header'
import { Plate } from '@/components/Plate'
import { useCart, useCatalog } from '@/store'
import { C } from '@/theme'
import type { CatalogItem, Kind } from '@/types'

type KindFilter = 'all' | Kind

export default function MenuScreen() {
  const params = useLocalSearchParams<{ svc?: string }>()
  const { add } = useCart()
  const { items, loading, error, reload } = useCatalog()
  const [kind, setKind] = useState<KindFilter>(params.svc === '1' ? 'service' : 'all')
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('All')

  useEffect(() => {
    if (params.svc === '1') setKind('service')
  }, [params.svc])

  const categories = useMemo(() => {
    const foodCats = [...new Set(items.filter((i) => i.kind === 'food').map((i) => i.category))]
    const hasServices = items.some((i) => i.kind === 'service')
    return ['All', ...foodCats, ...(hasServices ? ['Services'] : [])]
  }, [items])

  const visibleCategories = categories.filter(
    (c) =>
      c === 'All' ||
      (kind === 'all' && (c !== 'Services' || items.some((i) => i.kind === 'service'))) ||
      (kind === 'food' && c !== 'Services') ||
      (kind === 'service' && c === 'Services'),
  )

  const list = useMemo(
    () =>
      items.filter(
        (i) =>
          (kind === 'all' || i.kind === kind) &&
          (cat === 'All' || i.category === cat) &&
          (i.name + i.desc).toLowerCase().includes(q.toLowerCase()),
      ),
    [items, q, kind, cat],
  )

  return (
    <View style={{ flex: 1, backgroundColor: C.cream }}>
      <Header />
      <FlatList
        data={list}
        keyExtractor={(i) => i.key}
        ListHeaderComponent={
          <View style={{ padding: 20 }}>
            <Text style={styles.h2}>Menu & services</Text>

            <TextInput
              placeholder="Search jollof, egusi, cleaning…"
              value={q}
              onChangeText={setQ}
              style={styles.input}
              placeholderTextColor={C.mut}
            />

            <View style={styles.seg}>
              {(['all', 'food', 'service'] as const).map((k) => (
                <Pressable
                  key={k}
                  style={[styles.segBtn, kind === k && styles.segOn]}
                  onPress={() => {
                    setKind(k)
                    setCat('All')
                  }}
                >
                  <Text style={[styles.segTxt, kind === k && styles.segTxtOn]}>
                    {k === 'all' ? 'All' : k === 'food' ? 'Food' : 'Services'}
                  </Text>
                </Pressable>
              ))}
            </View>

            <View style={styles.chips}>
              {visibleCategories.map((c) => (
                <Pressable
                  key={c}
                  style={[styles.chip, cat === c && styles.chipOn]}
                  onPress={() => setCat(c)}
                >
                  <Text style={[styles.chipTxt, cat === c && styles.chipTxtOn]}>{c}</Text>
                </Pressable>
              ))}
            </View>

            {loading && <ActivityIndicator color={C.green} style={{ marginTop: 20 }} />}
            {error && !loading && (
              <View>
                <Text style={styles.errTxt}>{error}</Text>
                <Pressable onPress={reload}>
                  <Text style={styles.retry}>Try again</Text>
                </Pressable>
              </View>
            )}
          </View>
        }
        renderItem={({ item }) => (
          <Card
            item={item}
            onOpen={() =>
              router.push({ pathname: '/item-detail', params: { item: JSON.stringify(item) } })
            }
            onAdd={() => add(item)}
          />
        )}
        contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40 }}
        ListEmptyComponent={
          !loading && !error ? (
            <Text style={{ textAlign: 'center', color: C.mut, padding: 40 }}>
              Nothing found.
            </Text>
          ) : null
        }
      />
    </View>
  )
}

function Card({
  item,
  onOpen,
  onAdd,
}: {
  item: CatalogItem
  onOpen: () => void
  onAdd: () => void
}) {
  const svc = item.kind === 'service'
  return (
    <Pressable style={styles.card} onPress={onOpen}>
      <Plate item={item} />
      <View style={styles.cardBody}>
        <Text style={styles.cardTag}>{item.category}</Text>
        <Text style={styles.cardTitle}>{item.name}</Text>
        {item.desc ? (
          <Text style={styles.cardDesc} numberOfLines={2}>{item.desc}</Text>
        ) : null}
        <View style={styles.cardFoot}>
          <Text style={styles.price}>
            {svc ? 'On request' : naira(item.price_minor ?? 0)}
          </Text>
          <Pressable
            style={styles.addBtn}
            onPress={svc ? onOpen : onAdd}
            disabled={!svc && item.sold_out}
          >
            <Text style={styles.addBtnTxt}>
              {svc ? 'Book' : item.sold_out ? 'Sold out' : 'Add'}
            </Text>
          </Pressable>
        </View>
      </View>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  h2: { fontSize: 30, fontWeight: '800', color: C.green, marginBottom: 16 },
  input: {
    borderWidth: 1.5, borderColor: '#C9C58F', borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 12, backgroundColor: '#fff',
    fontSize: 16, color: C.ink, marginBottom: 12,
  },
  seg: {
    flexDirection: 'row', borderWidth: 1.5, borderColor: C.green, borderRadius: 999,
    overflow: 'hidden', alignSelf: 'flex-start', marginBottom: 16,
  },
  segBtn: { paddingHorizontal: 18, paddingVertical: 10 },
  segOn: { backgroundColor: C.green },
  segTxt: { color: C.green, fontWeight: '600', fontSize: 14 },
  segTxtOn: { color: '#fff' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  chip: {
    borderWidth: 1.5, borderColor: C.line, backgroundColor: '#fff',
    borderRadius: 999, paddingHorizontal: 14, paddingVertical: 7,
  },
  chipOn: { backgroundColor: C.gold, borderColor: C.gold },
  chipTxt: { fontWeight: '600', fontSize: 13, color: C.green },
  chipTxtOn: { color: C.ink },
  errTxt: { color: C.burg },
  retry: { color: C.green, fontWeight: '700', marginTop: 8, textDecorationLine: 'underline' },
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
