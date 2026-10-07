import { MaterialCommunityIcons } from '@expo/vector-icons'
import { router, useFocusEffect } from 'expo-router'
import { useCallback, useState } from 'react'
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native'
import {
  listOrders,
  listServiceRequests,
  naira,
  type OrderResponse,
  type ServiceRequestResponse,
} from '@/api'
import { Header } from '@/components/Header'
import { useSession } from '@/auth'
import { C } from '@/theme'

type Row =
  | { kind: 'order'; data: OrderResponse }
  | { kind: 'service'; data: ServiceRequestResponse }

export default function OrdersScreen() {
  const { isAuthenticated, login, ready, name } = useSession()
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [orders, services] = await Promise.all([
        listOrders().catch(() => ({ items: [], next_cursor: null })),
        listServiceRequests().catch(() => ({ items: [], next_cursor: null })),
      ])
      const merged: Row[] = [
        ...orders.items.map((d) => ({ kind: 'order' as const, data: d })),
        ...services.items.map((d) => ({ kind: 'service' as const, data: d })),
      ].sort((a, b) => (b.data.created_at ?? '').localeCompare(a.data.created_at ?? ''))
      setRows(merged)
      setError('')
    } catch {
      setError('We could not load your orders and requests.')
    } finally {
      setLoading(false)
    }
  }, [])

  useFocusEffect(
    useCallback(() => {
      if (ready && isAuthenticated) void load()
    }, [ready, isAuthenticated, load]),
  )

  if (!ready) {
    return (
      <View style={{ flex: 1, backgroundColor: C.cream }}>
        <Header />
        <ActivityIndicator color={C.green} style={{ marginTop: 40 }} />
      </View>
    )
  }

  if (!isAuthenticated) {
    return (
      <View style={{ flex: 1, backgroundColor: C.cream }}>
        <Header />
        <View style={styles.gate}>
          <Text style={{ fontSize: 46 }}>👤</Text>
          <Text style={styles.gateH}>Sign in to view your account</Text>
          <Text style={styles.gateP}>Track orders and service requests in one place.</Text>
          <Pressable style={styles.btn} onPress={login}>
            <Text style={styles.btnTxt}>Sign in with Google</Text>
          </Pressable>
        </View>
      </View>
    )
  }

  return (
    <View style={{ flex: 1, backgroundColor: C.cream }}>
      <Header />
      <FlatList
        data={rows}
        keyExtractor={(r) => `${r.kind}-${r.data.id}`}
        ListHeaderComponent={
          <View style={{ padding: 20 }}>
            <Text style={styles.h2}>Hi{name ? `, ${name}` : ''}</Text>
            <Text style={styles.sub}>Your recent orders and service requests.</Text>
            {error ? <Text style={styles.err}>{error}</Text> : null}
            {loading && <ActivityIndicator color={C.green} style={{ marginTop: 20 }} />}
          </View>
        }
        renderItem={({ item }) => {
          if (item.kind === 'order') {
            const o = item.data
            return (
              <Pressable
                style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
                onPress={() =>
                  router.push({ pathname: '/order-detail', params: { orderId: String(o.id) } })
                }
                accessibilityRole="button"
                accessibilityLabel={`Order ${o.id}, ${o.status}`}
              >
                <View style={styles.cardTop}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.cardTitle}>Order #{o.id}</Text>
                    <Text style={styles.cardMeta}>
                      {o.fulfillment_type} · {o.fulfillment_date}
                    </Text>
                    <Text style={styles.cardTotal}>{naira(o.total_minor)}</Text>
                  </View>
                  <View style={styles.cardRight}>
                    <Text style={[styles.badge, { backgroundColor: badgeBg(o.status) }]}>
                      {o.status}
                    </Text>
                    <MaterialCommunityIcons
                      name="chevron-right"
                      size={20}
                      color={C.mut}
                      style={{ marginTop: 8 }}
                    />
                  </View>
                </View>
              </Pressable>
            )
          }

          const s = item.data
          return (
            <Pressable
              style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
              onPress={() =>
                router.push({
                  pathname: '/service-detail',
                  params: { requestId: String(s.id) },
                })
              }
              accessibilityRole="button"
              accessibilityLabel={`Service request ${s.id}, ${s.status}`}
            >
              <View style={styles.cardTop}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.cardTitle}>Service #{s.id}</Text>
                  <Text style={styles.cardMeta} numberOfLines={1}>
                    {s.location}
                  </Text>
                  {s.preferred_date ? (
                    <Text style={styles.cardMeta}>Preferred: {s.preferred_date}</Text>
                  ) : null}
                  {s.quoted_amount_minor != null && (
                    <Text style={styles.cardTotal}>
                      Quote: {naira(s.quoted_amount_minor)}
                    </Text>
                  )}
                </View>
                <View style={styles.cardRight}>
                  <Text style={[styles.badge, { backgroundColor: badgeBg(s.status) }]}>
                    {s.status}
                  </Text>
                  <MaterialCommunityIcons
                    name="chevron-right"
                    size={20}
                    color={C.mut}
                    style={{ marginTop: 8 }}
                  />
                </View>
              </View>
            </Pressable>
          )
        }}
        ListEmptyComponent={
          !loading ? (
            <View style={{ alignItems: 'center', padding: 30 }}>
              <Text style={{ color: C.mut, marginBottom: 12 }}>No activity yet.</Text>
              <Pressable
                style={styles.btn}
                onPress={() => router.push('/(tabs)/menu')}
              >
                <Text style={styles.btnTxt}>Order something</Text>
              </Pressable>
            </View>
          ) : null
        }
        contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40 }}
      />
    </View>
  )
}

const badgeBg = (status: string) => {
  const s = status.toLowerCase()
  if (s.includes('cancel')) return C.burg
  if (s.includes('complete') || s.includes('paid')) return C.green
  if (s.includes('pending') || s.includes('preparing')) return '#B8791F'
  return C.mut
}

const styles = StyleSheet.create({
  h2: { fontSize: 26, fontWeight: '800', color: C.green },
  sub: { color: C.mut, marginTop: 4, marginBottom: 16 },
  err: { color: C.burg, marginBottom: 8 },
  card: {
    backgroundColor: '#fff', borderRadius: 14, padding: 16, marginBottom: 10,
    borderWidth: 1, borderColor: C.line,
  },
  cardPressed: { opacity: 0.7 },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  cardRight: { alignItems: 'flex-end' },
  cardTitle: { fontWeight: '700', fontSize: 16, color: C.ink },
  badge: {
    color: '#fff', fontSize: 11, fontWeight: '700',
    paddingHorizontal: 9, paddingVertical: 3, borderRadius: 999, overflow: 'hidden',
  },
  cardMeta: { color: C.mut, marginTop: 4, fontSize: 13 },
  cardTotal: { fontWeight: '800', color: C.green, marginTop: 5, fontSize: 15 },
  gate: {
    flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 30,
  },
  gateH: { fontSize: 20, fontWeight: '800', color: C.green, textAlign: 'center' },
  gateP: { color: C.mut, textAlign: 'center', marginBottom: 10 },
  btn: {
    backgroundColor: C.green, borderRadius: 999, paddingHorizontal: 22, paddingVertical: 14,
  },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
})
