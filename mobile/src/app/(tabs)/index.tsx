import { MaterialCommunityIcons } from '@expo/vector-icons'
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
import type { CatalogItem } from '@/types'

// Maps service name keywords → MaterialCommunityIcons icon name + accent colour.
// Falls back to a generic icon for any unlisted service.
type MCIcon = React.ComponentProps<typeof MaterialCommunityIcons>['name']

function serviceIcon(name: string): { icon: MCIcon; color: string } {
  const n = name.toLowerCase()
  if (n.includes('chef') || n.includes('cater')) return { icon: 'chef-hat', color: C.green }
  if (n.includes('clean')) return { icon: 'broom', color: '#1565C0' }
  if (n.includes('errand')) return { icon: 'moped', color: C.burg }
  if (n.includes('organiz')) return { icon: 'home-edit-outline', color: '#6A1B9A' }
  return { icon: 'briefcase-outline', color: C.mut }
}

export default function HomeScreen() {
  const { add } = useCart()
  const { items, loading, error, reload } = useCatalog()

  const foodItems = items.filter((i) => i.kind === 'food')
  const featured = foodItems.slice(0, 4)
  const services = items.filter((i) => i.kind === 'service')

  // Derive unique categories from live data for the quick-pick row
  const categories = [...new Set(foodItems.map((i) => i.category))].slice(0, 6)

  return (
    <View style={{ flex: 1, backgroundColor: C.cream }}>
      <Header />
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>

        {/* ── Hero ── */}
        <View style={styles.hero}>
          <View style={styles.heroAccent} />
          <View style={styles.heroContent}>
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
            <View style={styles.factRow}>
              {['Cooked to order', 'Delivery or pickup', 'Card or transfer'].map((f) => (
                <View key={f} style={styles.factPill}>
                  <Text style={styles.factTxt}>{f}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>

        {/* ── Category quick-picks ── */}
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
                <FoodCard key={it.key} item={it} onAdd={() => add(it)} />
              ))}
            </View>
          )}
        </View>

        {/* ── Services grid — live data, icon-based cards ── */}
        <View style={styles.sec}>
          <View style={styles.secHead}>
            <Text style={styles.h2}>Services</Text>
            <Pressable
              onPress={() => router.push({ pathname: '/(tabs)/menu', params: { svc: '1' } })}
            >
              <Text style={styles.seeAll}>See all →</Text>
            </Pressable>
          </View>

          {loading ? (
            <ActivityIndicator color={C.green} style={{ marginTop: 16 }} />
          ) : services.length === 0 ? (
            <Text style={{ color: C.mut, fontSize: 14 }}>No services listed yet.</Text>
          ) : (
            <View style={styles.svcGrid}>
              {services.map((s) => {
                const { icon, color } = serviceIcon(s.name)
                return (
                  <Pressable
                    key={s.key}
                    style={({ pressed }) => [styles.svcCard, pressed && { opacity: 0.75 }]}
                    onPress={() =>
                      router.push({ pathname: '/item-detail', params: { item: JSON.stringify(s) } })
                    }
                    accessibilityRole="button"
                    accessibilityLabel={s.name}
                  >
                    <View style={[styles.svcIconWrap, { backgroundColor: color + '18' }]}>
                      <MaterialCommunityIcons name={icon} size={28} color={color} />
                    </View>
                    <Text style={styles.svcCardTitle} numberOfLines={2}>{s.name}</Text>
                    <Text style={styles.svcCardDesc} numberOfLines={2}>{s.desc}</Text>
                    <Text style={[styles.svcCardCta, { color }]}>Book →</Text>
                  </Pressable>
                )
              })}
            </View>
          )}
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

      </ScrollView>
    </View>
  )
}

// ── Extracted food card component ────────────────────────────────────────────

function FoodCard({ item, onAdd }: { item: CatalogItem; onAdd: () => void }) {
  return (
    <Pressable
      style={styles.card}
      onPress={() =>
        router.push({ pathname: '/item-detail', params: { item: JSON.stringify(item) } })
      }
    >
      <Plate item={item} />
      <View style={styles.cardBody}>
        <Text style={styles.cardTag}>{item.category}</Text>
        <Text style={styles.cardTitle}>{item.name}</Text>
        {item.desc ? (
          <Text style={styles.cardDesc} numberOfLines={2}>{item.desc}</Text>
        ) : null}
        <View style={styles.cardFoot}>
          <Text style={styles.price}>{naira(item.price_minor ?? 0)}</Text>
          <Pressable
            style={[styles.addBtn, item.sold_out && { opacity: 0.4 }]}
            onPress={onAdd}
            disabled={item.sold_out}
          >
            <Text style={styles.addBtnTxt}>{item.sold_out ? 'Sold out' : 'Add'}</Text>
          </Pressable>
        </View>
      </View>
    </Pressable>
  )
}

// ── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  // ── Hero
  hero: { backgroundColor: C.green, overflow: 'hidden' },
  heroAccent: {
    position: 'absolute', top: 0, right: -40, width: 220, height: 220,
    borderRadius: 110, backgroundColor: 'rgba(255,255,255,0.06)',
  },
  heroContent: { padding: 24, paddingTop: 36, paddingBottom: 28 },
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
  secHead: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 16,
  },
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
  card: { backgroundColor: '#fff', borderRadius: 20, padding: 12, ...S.shadow },
  cardBody: { paddingTop: 10, gap: 4 },
  cardTag: { fontSize: 12, color: C.mut, fontWeight: '600' },
  cardTitle: { fontSize: 17, fontWeight: '700', color: C.ink },
  cardDesc: { fontSize: 13, color: C.mut },
  cardFoot: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginTop: 8,
  },
  price: { fontSize: 16, fontWeight: '800', color: C.green },
  addBtn: {
    backgroundColor: C.green, paddingHorizontal: 16, paddingVertical: 8, borderRadius: 12,
  },
  addBtnTxt: { color: '#fff', fontWeight: '700', fontSize: 13 },

  // ── Services 2×2 icon grid
  svcGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  svcCard: {
    width: '47%', backgroundColor: '#fff', borderRadius: 16, padding: 16,
    borderWidth: 1, borderColor: C.line, gap: 6,
  },
  svcIconWrap: {
    width: 52, height: 52, borderRadius: 14,
    alignItems: 'center', justifyContent: 'center', marginBottom: 4,
  },
  svcCardTitle: { fontWeight: '700', fontSize: 14, color: C.ink },
  svcCardDesc: { fontSize: 12, color: C.mut, lineHeight: 17 },
  svcCardCta: { fontSize: 12, fontWeight: '700', marginTop: 2 },

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
