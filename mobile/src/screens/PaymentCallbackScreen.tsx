import { MaterialCommunityIcons } from '@expo/vector-icons'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { useEffect, useRef, useState } from 'react'
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native'
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { getOrder, naira, type OrderResponse } from '../api'
import { C } from '../theme'
import type { RootStackParamList } from '../navigation'

const LAST_ORDER_KEY = 'damis.lastOrderId'
const PAID_STATES = ['paid', 'confirmed', 'completed', 'preparing', 'ready']
const FAIL_STATES = ['cancelled', 'failed', 'payment_failed']

export default function PaymentCallbackScreen() {
  const nav = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const route = useRoute<RouteProp<RootStackParamList, 'PaymentCallback'>>()

  const [orderId, setOrderId] = useState<number | undefined>(route.params?.orderId)
  const [status, setStatus] = useState<'pending' | 'ok' | 'fail' | 'timeout'>('pending')
  const [order, setOrder] = useState<OrderResponse | null>(null)
  const [attempt, setAttempt] = useState(0)
  const attemptsRef = useRef(0)

  // Resolve order id from params or the persisted last order
  useEffect(() => {
    if (orderId) return
    AsyncStorage.getItem(LAST_ORDER_KEY).then((raw) => {
      const id = raw ? Number(raw) : NaN
      if (Number.isFinite(id)) setOrderId(id)
      else setStatus('fail')
    })
  }, [orderId])

  // Poll for the final status
  useEffect(() => {
    if (!orderId) return
    let cancelled = false
    attemptsRef.current = 0

    const tick = async () => {
      if (cancelled) return
      attemptsRef.current += 1
      try {
        const o = await getOrder(orderId)
        if (cancelled) return
        setOrder(o)
        const s = o.status.toLowerCase()
        if (PAID_STATES.includes(s)) {
          setStatus('ok')
          await AsyncStorage.removeItem(LAST_ORDER_KEY)
          return
        }
        if (FAIL_STATES.includes(s)) {
          setStatus('fail')
          return
        }
      } catch { /* keep trying */ }

      if (attemptsRef.current >= 15) {
        setStatus('timeout')
        return
      }
      setTimeout(tick, 2000)
    }

    void tick()
    return () => { cancelled = true }
  }, [orderId, attempt])

  // ── UI ────────────────────────────────────────────────────────────────────

  const renderIcon = () => {
    if (status === 'ok') return (
      <View style={[styles.icon, styles.iconOk]}>
        <MaterialCommunityIcons name="check" size={34} color={C.gold} />
      </View>
    )
    if (status === 'fail') return (
      <View style={[styles.icon, styles.iconFail]}>
        <MaterialCommunityIcons name="close" size={34} color="#fff" />
      </View>
    )
    if (status === 'timeout') return (
      <View style={[styles.icon, styles.iconWarn]}>
        <MaterialCommunityIcons name="clock-outline" size={32} color={C.brown} />
      </View>
    )
    return <View style={styles.spinner} />
  }

  const title =
    status === 'ok' ? 'Payment confirmed'
    : status === 'fail' ? 'Payment not completed'
    : status === 'timeout' ? 'Still processing'
    : 'Verifying payment…'

  const sub =
    status === 'ok' ? "Thanks! We're preparing your order."
    : status === 'fail' ? 'No charge was made. You can try again from your orders.'
    : status === 'timeout' ? "We haven't heard back yet — your order will update automatically."
    : 'This usually takes a few seconds.'

  return (
    <View style={styles.backdrop}>
      <View style={styles.card}>
        {renderIcon()}
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.sub}>{sub}</Text>

        {order && (
          <View style={styles.summary}>
            <View style={styles.row}>
              <Text style={styles.rowLbl}>Order</Text>
              <Text>#{order.id}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.rowLbl}>Status</Text>
              <Text>{order.status}</Text>
            </View>
            <View style={[styles.row, styles.rowTotal]}>
              <Text style={{ fontWeight: '800', fontSize: 16 }}>Total</Text>
              <Text style={{ fontWeight: '800', fontSize: 16 }}>{naira(order.total_minor)}</Text>
            </View>
          </View>
        )}

        <View style={styles.actions}>
          {status === 'pending' && (
            <View style={styles.helperRow}>
              <ActivityIndicator color={C.green} />
              <Text style={styles.helperTxt}>Checking…</Text>
            </View>
          )}

          {(status === 'timeout' || status === 'fail') && (
            <Pressable style={styles.btn} onPress={() => setAttempt((n) => n + 1)}>
              <Text style={styles.btnTxt}>Check again</Text>
            </Pressable>
          )}

          <Pressable
            style={[styles.btn, styles.btnGhost]}
            onPress={() => nav.navigate('Tabs', { screen: 'Orders' } as never)}
          >
            <Text style={[styles.btnTxt, { color: C.green }]}>Go to my orders</Text>
          </Pressable>

          <Pressable onPress={() => nav.navigate('Tabs', { screen: 'Home' } as never)}>
            <Text style={styles.link}>Back to home</Text>
          </Pressable>
        </View>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1, backgroundColor: C.cream,
    alignItems: 'center', justifyContent: 'center', padding: 20,
  },
  card: {
    width: '100%', maxWidth: 440, backgroundColor: '#fff', borderRadius: 24,
    padding: 28, alignItems: 'center', gap: 12,
    shadowColor: '#000', shadowOpacity: 0.12, shadowRadius: 24,
    shadowOffset: { width: 0, height: 12 }, elevation: 6,
  },
  icon: { width: 72, height: 72, borderRadius: 36, alignItems: 'center', justifyContent: 'center' },
  iconOk: { backgroundColor: C.green },
  iconFail: { backgroundColor: C.burg },
  iconWarn: { backgroundColor: C.gold },
  spinner: {
    width: 56, height: 56, borderRadius: 28,
    borderWidth: 5, borderColor: C.line, borderTopColor: C.green,
  },
  title: { fontSize: 22, fontWeight: '800', color: C.ink, textAlign: 'center' },
  sub: { color: C.mut, textAlign: 'center', fontSize: 15 },
  summary: {
    width: '100%', backgroundColor: C.cream2, borderRadius: 12,
    padding: 14, marginTop: 6, gap: 6,
  },
  row: { flexDirection: 'row', justifyContent: 'space-between' },
  rowLbl: { color: C.mut },
  rowTotal: { borderTopWidth: 1.5, borderTopColor: C.line, paddingTop: 8, marginTop: 4 },
  actions: { width: '100%', gap: 10, marginTop: 8, alignItems: 'stretch' },
  btn: {
    backgroundColor: C.green, borderRadius: 999,
    paddingVertical: 13, alignItems: 'center',
  },
  btnGhost: { backgroundColor: 'transparent', borderWidth: 2, borderColor: C.green },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
  helperRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  helperTxt: { color: C.mut },
  link: { color: C.green, textAlign: 'center', fontWeight: '600', marginTop: 6, textDecorationLine: 'underline' },
})