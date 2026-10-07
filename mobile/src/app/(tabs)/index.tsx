import { router } from 'expo-router'
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native'
import { naira } from '@/api'
import { Header } from '@/components/Header'
import { Plate } from '@/components/Plate'
import { toneFor } from '@/data'
import { useCart, useCatalog } from '@/store'
import { C, S } from '@/theme'

const BENEFITS = [
  { emoji: '🍲', title: 'Made by Chef Dami', desc: 'Every meal cooked fresh to order.' },
  { emoji: '🚚', title: 'Delivery or pickup', desc: 'Your choice, your schedule.' },
  { emoji: '💳', title: 'Card or transfer', desc: 'Pay the way that suits you.' },
  { emoji: '📞', title: 'Real people', desc: 'Message or call — we answer.' },
]

export default function HomeScreen() {
  const { add } = useCart()
  const { items, loading, error, reload } = useCatalog()

  const foodItems = items.filter((i) => i.kind === 'food')
  const featured = foodItems.slice(0, 4)
  const services = items.filter((i) => i.kind === 'service').slice(0, 4)

  // Derive unique categories from live data for the quick-pick row
  const categories = [...new Set(foodItems.map((i) => i.category))].slice(0, 6)

  return (
    <View style={{ flex: 1, backgroundColor: C.cream }}>
      <Header />
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>

        {/* ── Hero ── */}
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
                onPress={() => router.push('/(tabs)/menu')}
              >
                <Text style={styles.btnGoldTxt}>Order now</Text>
              </Pressable>
              <Pressable
                style={styles.btnGhost}
                onPress={() =>
                  router.push({ pathname: '/(tabs)/menu', params: { svc: '1' } })
                }
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
            {/* ── Category quick-picks ── */}
            {categories.length > 0 && (
              <View style={styles.quickSec}>
                <Text style={styles.quickLabel}>Browse by category</Text>
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.quickRow}
                >
                  {categories.map((cat) => (
                    <Pressable
                      key={cat}
                      style={[styles.quickChip, { borderColor: toneFor(cat) }]}
                      onPress={() =>
                        router.push({
                          pathname: '/(tabs)/menu',
                          params: { cat },
                        })
                      }
                    >
                      <View
                        style={[styles.quickDot, { backgroundColor: toneFor(cat) }]}
                      />
                      <Text style={styles.quickChipTxt}>{cat}</Text>
                    </Pressable>
                  ))}
                  <Pressable
                    style={[styles.quickChip, { borderColor: C.green }]}
                    onPress={() => router.push('/(tabs)/menu')}
                  >
                    <Text style={[styles.quickChipTxt, { color: C.green }]}>See all →</Text>
                  </Pressable>
                </ScrollView>
              </View>
            )}

            {/* ── Popular today ── */}
            <View style={styles.sec}>
              <Text style={styles.h2}>Popular today</Text>
              <View style={styles.grid}>
                {featured.map((it) => (
                  <Pressable
                    key={it.key}
                    style={styles.card}
                    onPress={() =>
                      router.push({
                        pathname: '/item-detail',
                        params: { item: JSON.stringify(it) },
                      })
                    }
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
                          style={[styles.addBtn, it.sold_out && { opacity: 0.4 }]}
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

            {/* ── Services ── */}
            <View style={styles.darkSec}>
              <Text style={styles.darkH2}>Services we offer</Text>
              <Text style={styles.darkP}>Book a pro — we'll reach out with a quote.</Text>
              {services.map((s) => (
                <Pressable
                  key={s.key}
                  style={styles.svcRow}
                  onPress={() =>
                    router.push({
                      pathname: '/item-detail',
                      params: { item: JSON.stringify(s) },
                    })
                  }
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

            {/* ── Why us — 2×2 benefit grid ── */}
            <View style={styles.sec}>
              <Text style={styles.h2}>Why people choose us</Text>
              <View style={styles.benefitGrid}>
                {BENEFITS.map((b) => (
                  <View key={b.title} style={styles.benefitCard}>
                    <Text style={styles.benefitEmoji}>{b.emoji}</Text>
                    <Text style={styles.benefitTitle}>{b.title}</Text>
                    <Text style={styles.benefitDesc}>{b.desc}</Text>
                  </View>
                ))}
              </View>
            </View>

            {/* ── CTA panel ── */}
            <View style={styles.ctaPad}>
              <View style={styles.ctaPanel}>
                <Text style={styles.ctaH2}>Ready to order?</Text>
                <Text style={styles.ctaP}>Fresh food, honest prices, real people.</Text>
                <Pressable
                  style={styles.btnBrown}
                  onPress={() => router.push('/(tabs)/menu')}
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
  // ── Hero
  hero: { minHeight: 380, position: 'relative', backgroundColor: '#1a1a1a' },
  heroOverlay: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(10,106,27,0.75)',
  },
  heroContent: { padding: 24, paddingTop: 48, paddingBottom: 48 },
  heroH1: { color: '#fff', fontSize: 32, fontWeight: '800', lineHeight: 38 },
  heroP: { color: 'rgba(255,255,255,0.9)', fontSize: 16, marginTop: 12, marginBottom: 22 },
  ctaRow: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  btnGold: {
    backgroundColor: C.gold, paddingHorizontal: 22, paddingVertical: 12, borderRadius: 999,
  },
  btnGoldTxt: { color: C.ink, fontWeight: '700', fontSize: 15 },
  btnGhost: {
    borderColor: '#fff', borderWidth: 2, paddingHorizontal: 22, paddingVertical: 12,
    borderRadius: 999,
  },
  btnGhostTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },

  // ── Category quick-picks
  quickSec: { paddingTop: 20, paddingBottom: 4 },
  quickLabel: {
    fontSize: 13, fontWeight: '700', color: C.mut, letterSpacing: 0.5,
    textTransform: 'uppercase', paddingHorizontal: 20, marginBottom: 10,
  },
  quickRow: { paddingHorizontal: 20, gap: 8 },
  quickChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    borderWidth: 1.5, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 8,
    backgroundColor: '#fff',
  },
  quickDot: { width: 8, height: 8, borderRadius: 4 },
  quickChipTxt: { fontWeight: '600', fontSize: 13, color: C.ink },

  // ── Sections
  sec: { padding: 20 },
  errorTxt: { color: C.burg, marginBottom: 12 },
  h2: { fontSize: 24, fontWeight: '800', color: C.green, marginBottom: 16 },

  // ── Food cards
  grid: { gap: 14 },
  card: {
    backgroundColor: '#fff', borderRadius: 20, padding: 12, marginBottom: 14,
    ...S.shadow,
  },
  cardBody: { paddingTop: 10, gap: 4 },
  cardTag: { fontSize: 12, color: C.mut, fontWeight: '600' },
  cardTitle: { fontSize: 17, fontWeight: '700', color: C.ink },
  cardDesc: { fontSize: 13, color: C.mut },
  cardFoot: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8,
  },
  price: { fontSize: 16, fontWeight: '800', color: C.green },
  addBtn: {
    backgroundColor: C.green, paddingHorizontal: 16, paddingVertical: 8, borderRadius: 12,
  },
  addBtnTxt: { color: '#fff', fontWeight: '700', fontSize: 13 },

  // ── Services dark section
  darkSec: { backgroundColor: C.brown, padding: 24, gap: 12 },
  darkH2: { color: '#fff', fontSize: 24, fontWeight: '800' },
  darkP: { color: 'rgba(255,255,255,0.65)', marginBottom: 8 },
  svcRow: {
    flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14,
    backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
  },
  svcIcon: {
    width: 44, height: 44, borderRadius: 12, backgroundColor: C.green,
    alignItems: 'center', justifyContent: 'center',
  },
  svcTitle: { color: '#fff', fontSize: 16, fontWeight: '700' },
  svcDesc: { color: 'rgba(255,255,255,0.7)', fontSize: 13, marginTop: 2 },

  // ── Benefits 2×2 grid
  benefitGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  benefitCard: {
    width: '47%', backgroundColor: '#fff', borderRadius: 16, padding: 16,
    borderWidth: 1, borderColor: C.line, gap: 4,
  },
  benefitEmoji: { fontSize: 26, marginBottom: 4 },
  benefitTitle: { fontWeight: '700', fontSize: 14, color: C.ink },
  benefitDesc: { fontSize: 12, color: C.mut, lineHeight: 17 },

  // ── CTA panel
  ctaPad: { padding: 20 },
  ctaPanel: {
    backgroundColor: C.gold, borderRadius: 24, padding: 28, alignItems: 'center',
  },
  ctaH2: { color: C.brown, fontSize: 24, fontWeight: '800' },
  ctaP: { color: 'rgba(61,40,23,0.75)', marginTop: 6, marginBottom: 16, textAlign: 'center' },
  btnBrown: {
    backgroundColor: C.brown, paddingHorizontal: 22, paddingVertical: 12, borderRadius: 999,
  },
})
