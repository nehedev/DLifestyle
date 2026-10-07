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
          {/* top accent strip */}
          <View style={styles.heroAccent} />
          <View style={styles.heroContent}>
            <View style={styles.heroBadge}>
              <Text style={styles.heroBadgeTxt}>🍽  Dami's Lifestyle</Text>
            </View>
            <Text style={styles.heroH1}>Home-cooked meals & everyday help.</Text>
            <Text style={styles.heroP}>
              Fresh Nigerian food or lifestyle services — delivered or picked up.
            </Text>
            <View style={styles.ctaRow}>
              <Pressable
                style={styles.btnGold}
                onPress={() => router.push('/(tabs)/menu')}
              >
                <Text style={styles.btnGoldTxt}>Order food</Text>
              </Pressable>
              <Pressable
                style={styles.btnGhost}
                onPress={() =>
                  router.push({ pathname: '/(tabs)/menu', params: { svc: '1' } })
                }
              >
                <Text style={styles.btnGhostTxt}>Book a service</Text>
              </Pressable>
            </View>
            {/* fact pills */}
            <View style={styles.factRow}>
              {['Cooked to order', 'Delivery or pickup', 'Card or transfer'].map((f) => (
                <View key={f} style={styles.factPill}>
                  <Text style={styles.factTxt}>{f}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>

        {/* ── Category quick-picks (shown once data loads) ── */}
        {!loading && !error && categories.length > 0 && (
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
                    router.push({ pathname: '/(tabs)/menu', params: { cat } })
                  }
                >
                  <View style={[styles.quickDot, { backgroundColor: toneFor(cat) }]} />
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

        {/* ── Featured food ── */}
        <View style={styles.sec}>
          <View style={styles.secHead}>
            <Text style={styles.h2}>Popular today</Text>
            <Pressable onPress={() => router.push('/(tabs)/menu')}>
              <Text style={styles.seeAll}>See menu →</Text>
            </Pressable>
          </View>

          {loading ? (
            <ActivityIndicator color={C.green} style={{ marginTop: 16 }} />
          ) : error ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorTxt}>{error}</Text>
              <Pressable style={styles.retryBtn} onPress={reload}>
                <Text style={styles.retryTxt}>Try again</Text>
              </Pressable>
            </View>
          ) : featured.length === 0 ? (
            <Text style={{ color: C.mut, fontSize: 14 }}>No items yet — check back soon.</Text>
          ) : (
            <View style={styles.grid}>
              {featured.map((it) => (
                <Pressable
                  key={it.key}
                  style={styles.card}
                  onPress={() =>
                    router.push({ pathname: '/item-detail', params: { item: JSON.stringify(it) } })
                  }
                >
                  <Plate item={it} />
                  <View style={styles.cardBody}>
                    <Text style={styles.cardTag}>{it.category}</Text>
                    <Text style={styles.cardTitle}>{it.name}</Text>
                    {it.desc ? (
                      <Text style={styles.cardDesc} numberOfLines={2}>{it.desc}</Text>
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
          )}
        </View>

        {/* ── Services (always shown; just shows empty state if data not ready) ── */}
        {(services.length > 0 || !loading) && (
          <View style={styles.darkSec}>
            <Text style={styles.darkH2}>Services we offer</Text>
            <Text style={styles.darkP}>Book a pro — we'll reach out with a quote.</Text>
            {loading ? (
              <ActivityIndicator color={C.gold} style={{ marginTop: 8 }} />
            ) : services.length === 0 ? (
              <Text style={{ color: 'rgba(255,255,255,0.5)', fontSize: 14 }}>
                No services listed yet.
              </Text>
            ) : (
              services.map((s) => (
                <Pressable
                  key={s.key}
                  style={styles.svcRow}
                  onPress={() =>
                    router.push({ pathname: '/item-detail', params: { item: JSON.stringify(s) } })
                  }
                >
                  <View style={styles.svcIcon}>
                    <Text style={{ fontSize: 22 }}>✨</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.svcTitle}>{s.name}</Text>
                    <Text style={styles.svcDesc} numberOfLines={2}>{s.desc}</Text>
                  </View>
                </Pressable>
              ))
            )}
          </View>
        )}

        {/* ── Benefits 2×2 — always visible, no API dependency ── */}
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

        {/* ── CTA panel — always visible ── */}
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

      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  // ── Hero — solid green brand block, no image dependency
  hero: { backgroundColor: C.green, overflow: 'hidden' },
  heroAccent: {
    position: 'absolute', top: 0, right: -40, width: 220, height: 220,
    borderRadius: 110, backgroundColor: 'rgba(255,255,255,0.06)',
  },
  heroContent: { padding: 24, paddingTop: 36, paddingBottom: 28 },
  heroBadge: {
    alignSelf: 'flex-start', backgroundColor: 'rgba(255,255,255,0.18)',
    borderRadius: 999, paddingHorizontal: 12, paddingVertical: 5, marginBottom: 14,
  },
  heroBadgeTxt: { color: '#fff', fontSize: 12, fontWeight: '700', letterSpacing: 0.5 },
  heroH1: { color: '#fff', fontSize: 30, fontWeight: '800', lineHeight: 36 },
  heroP: { color: 'rgba(255,255,255,0.85)', fontSize: 15, marginTop: 10, marginBottom: 20 },
  ctaRow: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  btnGold: {
    backgroundColor: C.gold, paddingHorizontal: 22, paddingVertical: 12, borderRadius: 999,
  },
  btnGoldTxt: { color: C.ink, fontWeight: '700', fontSize: 15 },
  btnGhost: {
    borderColor: 'rgba(255,255,255,0.6)', borderWidth: 2,
    paddingHorizontal: 22, paddingVertical: 12, borderRadius: 999,
  },
  btnGhostTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
  factRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 18 },
  factPill: {
    backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: 999,
    paddingHorizontal: 10, paddingVertical: 4,
  },
  factTxt: { color: 'rgba(255,255,255,0.9)', fontSize: 11, fontWeight: '600' },

  // ── Category quick-picks
  quickSec: { paddingTop: 18, paddingBottom: 4 },
  quickLabel: {
    fontSize: 12, fontWeight: '700', color: C.mut, letterSpacing: 0.5,
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
  secHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  h2: { fontSize: 22, fontWeight: '800', color: C.green },
  seeAll: { fontSize: 13, color: C.green, fontWeight: '600' },
  errorBox: {
    backgroundColor: '#fff', borderRadius: 12, padding: 16,
    borderWidth: 1, borderColor: C.line, gap: 12,
  },
  errorTxt: { color: C.burg, fontSize: 14 },
  retryBtn: {
    alignSelf: 'flex-start', backgroundColor: C.green, borderRadius: 999,
    paddingHorizontal: 18, paddingVertical: 8,
  },
  retryTxt: { color: '#fff', fontWeight: '700', fontSize: 13 },

  // ── Food cards
  grid: { gap: 14 },
  card: {
    backgroundColor: '#fff', borderRadius: 20, padding: 12,
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
  darkH2: { color: '#fff', fontSize: 22, fontWeight: '800' },
  darkP: { color: 'rgba(255,255,255,0.65)', marginBottom: 4 },
  svcRow: {
    flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14,
    backgroundColor: 'rgba(255,255,255,0.07)', borderRadius: 14,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
  },
  svcIcon: {
    width: 44, height: 44, borderRadius: 12, backgroundColor: C.green,
    alignItems: 'center', justifyContent: 'center',
  },
  svcTitle: { color: '#fff', fontSize: 16, fontWeight: '700' },
  svcDesc: { color: 'rgba(255,255,255,0.7)', fontSize: 13, marginTop: 2 },

  // ── Benefits 2×2 grid
  benefitGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 4 },
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
  ctaH2: { color: C.brown, fontSize: 22, fontWeight: '800' },
  ctaP: { color: 'rgba(61,40,23,0.75)', marginTop: 6, marginBottom: 16, textAlign: 'center' },
  btnBrown: {
    backgroundColor: C.brown, paddingHorizontal: 22, paddingVertical: 12, borderRadius: 999,
  },
})
