import {
  ActivityIndicator,
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
import { Plate } from '../components/Plate'
import { useCart, useCatalog } from '../store'
import { C, S } from '../theme'
import type { RootStackParamList } from '../navigation'

export default function HomeScreen() {
  const nav = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { add } = useCart()
  const { items, loading, error, reload } = useCatalog()

  const featured = items.filter((i) => i.kind === 'food').slice(0, 4)
  const services = items.filter((i) => i.kind === 'service').slice(0, 4)

  return (
    <View style={{ flex: 1, backgroundColor: C.cream }}>
      <Header />
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        {/* Hero */}
        <View style={styles.hero}>
          <View style={styles.heroOverlay} />
          <View style={styles.heroContent}>
            <Text style={styles.heroH1}>Home-cooked meals & everyday help.</Text>
            <Text style={styles.heroP}>
              Order fresh Nigerian food or book a lifestyle service — delivered or picked up.
            </Text>
            <View style={styles.ctaRow}>
              <Pressable
                style={styles.btnGold}
                onPress={() => nav.navigate('Tabs', { screen: 'Menu' } as never)}
              >
                <Text style={styles.btnGoldTxt}>Order now</Text>
              </Pressable>
              <Pressable
                style={styles.btnGhost}
                onPress={() => nav.navigate('Tabs', { screen: 'Menu', params: { svc: true } } as never)}
              >
                <Text style={styles.btnGhostTxt}>Browse services</Text>
              </Pressable>
            </View>
          </View>
        </View>

        {loading ? (
          <ActivityIndicator color={C.green} style={{ marginTop: 32 }} />
        ) : error ? (
          <View style={styles.sec}>
            <Text style={styles.errorTxt}>{error}</Text>
            <Pressable style={styles.btnGold} onPress={reload}>
              <Text style={styles.btnGoldTxt}>Try again</Text>
            </Pressable>
          </View>
        ) : (
          <>
            <View style={styles.sec}>
              <Text style={styles.h2}>Popular today</Text>
              <View style={styles.grid}>
                {featured.map((it) => (
                  <Pressable
                    key={it.key}
                    style={styles.card}
                    onPress={() => nav.navigate('ItemDetail', { item: it })}
                  >
                    <Plate item={it} />
                    <View style={styles.cardBody}>
                      <Text style={styles.cardTag}>{it.category}</Text>
                      <Text style={styles.cardTitle}>{it.name}</Text>
                      {it.desc ? (
                        <Text style={styles.cardDesc} numberOfLines={2}>
                          {it.desc}
                        </Text>
                      ) : null}
                      <View style={styles.cardFoot}>
                        <Text style={styles.price}>{naira(it.price_minor ?? 0)}</Text>
                        <Pressable
                          style={styles.addBtn}
                          onPress={() => add(it)}
                          disabled={it.sold_out}
                        >
                          <Text style={styles.addBtnTxt}>
                            {it.sold_out ? 'Sold out' : 'Add'}
                          </Text>
                        </Pressable>
                      </View>
                    </View>
                  </Pressable>
                ))}
              </View>
            </View>

            <View style={styles.darkSec}>
              <Text style={styles.darkH2}>Services we offer</Text>
              <Text style={styles.darkP}>Book a pro — we'll reach out with a quote.</Text>
              {services.map((s) => (
                <Pressable
                  key={s.key}
                  style={styles.svcRow}
                  onPress={() => nav.navigate('ItemDetail', { item: s })}
                >
                  <View style={styles.svcIcon}>
                    <Text style={{ fontSize: 24 }}>✨</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.svcTitle}>{s.name}</Text>
                    <Text style={styles.svcDesc} numberOfLines={2}>{s.desc}</Text>
                  </View>
                </Pressable>
              ))}
            </View>

            <View style={styles.ctaPad}>
              <View style={styles.ctaPanel}>
                <Text style={styles.ctaH2}>Ready to order?</Text>
                <Text style={styles.ctaP}>Fresh food, honest prices, real people.</Text>
                <Pressable
                  style={styles.btnBrown}
                  onPress={() => nav.navigate('Tabs', { screen: 'Menu' } as never)}
                >
                  <Text style={styles.btnGoldTxt}>View menu</Text>
                </Pressable>
              </View>
            </View>
          </>
        )}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  hero: { minHeight: 420, position: 'relative', backgroundColor: '#1a1a1a' },
  heroOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(10,106,27,0.7)',
  },
  heroContent: { padding: 24, paddingTop: 60, paddingBottom: 60 },
  heroH1: { color: '#fff', fontSize: 36, fontWeight: '800', lineHeight: 42 },
  heroP: { color: 'rgba(255,255,255,0.95)', fontSize: 17, marginTop: 16, marginBottom: 24 },
  ctaRow: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  btnGold: {
    backgroundColor: C.gold, paddingHorizontal: 22, paddingVertical: 12, borderRadius: 999,
  },
  btnGoldTxt: { color: C.ink, fontWeight: '700', fontSize: 15 },
  btnGhost: {
    borderColor: '#fff', borderWidth: 2, paddingHorizontal: 22, paddingVertical: 12, borderRadius: 999,
  },
  btnGhostTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
  sec: { padding: 20 },
  errorTxt: { color: C.burg, marginBottom: 12 },
  h2: { fontSize: 26, fontWeight: '800', color: C.green, marginBottom: 18 },
  grid: { gap: 14 },
  card: {
    backgroundColor: '#fff', borderRadius: 24, padding: 12, marginBottom: 14,
    ...S.shadow,
  },
  cardBody: { paddingTop: 10, gap: 4 },
  cardTag: { fontSize: 12, color: C.mut, fontWeight: '600' },
  cardTitle: { fontSize: 18, fontWeight: '700', color: C.ink },
  cardDesc: { fontSize: 14, color: C.mut },
  cardFoot: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8,
  },
  price: { fontSize: 17, fontWeight: '800', color: C.green },
  addBtn: {
    backgroundColor: C.green, paddingHorizontal: 16, paddingVertical: 8, borderRadius: 12,
  },
  addBtnTxt: { color: '#fff', fontWeight: '700', fontSize: 14 },
  darkSec: { backgroundColor: C.brown, padding: 24, gap: 12 },
  darkH2: { color: '#fff', fontSize: 26, fontWeight: '800' },
  darkP: { color: 'rgba(255,255,255,0.65)', marginBottom: 12 },
  svcRow: {
    flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16,
    backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 16,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
  },
  svcIcon: {
    width: 48, height: 48, borderRadius: 14, backgroundColor: C.green,
    alignItems: 'center', justifyContent: 'center',
  },
  svcTitle: { color: '#fff', fontSize: 17, fontWeight: '700' },
  svcDesc: { color: 'rgba(255,255,255,0.7)', fontSize: 13, marginTop: 2 },
  ctaPad: { padding: 20 },
  ctaPanel: {
    backgroundColor: C.gold, borderRadius: 28, padding: 32, alignItems: 'center',
  },
  ctaH2: { color: C.brown, fontSize: 26, fontWeight: '800' },
  ctaP: { color: 'rgba(61,40,23,0.75)', marginTop: 8, marginBottom: 18, textAlign: 'center' },
  btnBrown: {
    backgroundColor: C.brown, paddingHorizontal: 22, paddingVertical: 12, borderRadius: 999,
  },
})
