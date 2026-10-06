import { useCallback, useEffect, useState } from 'react'
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native'
import { useFocusEffect, useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import {
  listOrders,
  listServiceRequests,
  naira,
  type OrderResponse,
  type ServiceRequestResponse,
} from '../api'
import { Header } from '../components/Header'
import { useSession } from '../auth'
import { C } from '../theme'
import type { RootStackParamList } from '../navigation'

type Row =
  | { kind: 'order'; data: OrderResponse }
  | { kind: 'service'; data: ServiceRequestResponse }

export default function RequestsScreen() {
  const nav = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const { isAuthenticated, login, ready, name } = useSession()
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)

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
            {loading && <ActivityIndicator color={C.green} style={{ marginTop: 20 }} />}
          </View>
        }
        renderItem={({ item }) => {
          if (item.kind === 'order') {
            const o = item.data
            return (
              <View style={styles.card}>
                <View style={styles.cardTop}>
                  <Text style={styles.cardTitle}>Order #{o.id}</Text>
                  <Text style={[styles.badge, badgeColor(o.status)]}>{o.status}</Text>
                </View>
                <Text style={styles.cardMeta}>
                  {o.fulfillment_type} · {o.fulfillment_date}
                </Text>
                <Text style={styles.cardTotal}>{naira(o.total_minor)}</Text>
              </View>
            )
          }
          const s = item.data
          return (
            <View style={styles.card}>
              <View style={styles.cardTop}>
                <Text style={styles.cardTitle}>Service #{s.id}</Text>
                <Text style={[styles.badge, badgeColor(s.status)]}>{s.status}</Text>
              </View>
              <Text style={styles.cardMeta}>{s.location}</Text>
              {s.quoted_amount_minor != null && (
                <Text style={styles.cardTotal}>Quote: {naira(s.quoted_amount_minor)}</Text>
              )}
            </View>
          )
        }}
        ListEmptyComponent={
          !loading ? (
            <Text style={{ textAlign: 'center', color: C.mut, padding: 40 }}>
              No activity yet.
            </Text>
          ) : null
        }
        contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40 }}
      />
    </View>
  )
}

const badgeColor = (status: string) => {
  const s = status.toLowerCase()
  if (s.includes('cancel')) return { backgroundColor: C.burg }
  if (s.includes('complete') || s.includes('paid')) return { backgroundColor: C.green }
  if (s.includes('pending') || s.includes('preparing')) return { backgroundColor: '#B8791F' }
  return { backgroundColor: C.mut }
}

const styles = StyleSheet.create({
  h2: { fontSize: 26, fontWeight: '800', color: C.green },
  sub: { color: C.mut, marginTop: 4, marginBottom: 16 },
  card: {
    backgroundColor: '#fff', borderRadius: 14, padding: 16, marginBottom: 10,
    borderWidth: 1, borderColor: C.line,
  },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardTitle: { fontWeight: '700', fontSize: 16 },
  badge: {
    color: '#fff', fontSize: 12, fontWeight: '700',
    paddingHorizontal: 10, paddingVertical: 3, borderRadius: 999, overflow: 'hidden',
  },
  cardMeta: { color: C.mut, marginTop: 6, fontSize: 13 },
  cardTotal: { fontWeight: '800', color: C.green, marginTop: 6, fontSize: 16 },
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