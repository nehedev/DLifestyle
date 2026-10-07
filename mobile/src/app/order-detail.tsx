import { MaterialCommunityIcons } from '@expo/vector-icons'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { router, useLocalSearchParams } from 'expo-router'
import { useCallback, useEffect, useState } from 'react'
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native'
import { cancelOrder, getOrder, naira, type OrderResponse } from '@/api'
import { PHONE } from '@/data'
import { C } from '@/theme'

export default function OrderDetailScreen() {
  const { orderId } = useLocalSearchParams<{ orderId: string }>()
  const id = Number(orderId)

  const [order, setOrder] = useState<OrderResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cancelling, setCancelling] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setOrder(await getOrder(id))
    } catch {
      setError('We could not load that order.')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  // If we arrived from the payment callback, also clear the pending key
  useEffect(() => {
    void AsyncStorage.removeItem('damis.pending_payment_order')
  }, [])

  const handleCancel = () => {
    Alert.alert('Cancel this order?', 'This cannot be undone.', [
      { text: 'Keep it', style: 'cancel' },
      {
        text: 'Cancel order',
        style: 'destructive',
        onPress: async () => {
          setCancelling(true)
          try {
            setOrder(await cancelOrder(id))
          } catch {
            Alert.alert('Could not cancel', 'That order can no longer be cancelled.')
          } finally {
            setCancelling(false)
          }
        },
      },
    ])
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={C.green} size="large" />
      </View>
    )
  }

  if (error || !order) {
    return (
      <View style={styles.center}>
        <Text style={styles.errTxt}>{error || 'Order not found.'}</Text>
        <Pressable style={styles.btn} onPress={() => router.back()}>
          <Text style={styles.btnTxt}>Go back</Text>
        </Pressable>
      </View>
    )
  }

  const isPaid = !['pending', 'cancelled'].includes(order.status)
  const isCancelled = order.status === 'cancelled'
  const canCancel = order.status === 'pending'

  const statusIcon = isPaid ? '✓' : isCancelled ? '✕' : '⏳'
  const statusBg = isPaid ? C.green : isCancelled ? C.burg : '#B8791F'
  const headline = isPaid
    ? `Payment confirmed — thank you, ${order.contact.name.split(' ')[0]}!`
    : isCancelled
      ? 'This order was cancelled'
      : `Order #${order.id} received`

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: C.cream }}
      contentContainerStyle={{ padding: 20, paddingBottom: 60 }}
    >
      {/* Status banner */}
      <View style={[styles.banner, { backgroundColor: statusBg }]}>
        <Text style={styles.bannerIcon}>{statusIcon}</Text>
        <View style={{ flex: 1 }}>
          <Text style={styles.bannerTitle}>{headline}</Text>
          <Text style={styles.bannerSub}>
            {isPaid
              ? "We're preparing your order."
              : isCancelled
                ? 'No payment was taken.'
                : 'Confirming your payment — this page updates automatically.'}
          </Text>
        </View>
      </View>

      {/* Items */}
      <View style={styles.section}>
        <Text style={styles.sectionH}>Items</Text>
        {order.items.map((item, i) => (
          <View key={i} style={styles.row}>
            <Text style={styles.rowLbl} numberOfLines={2}>
              {item.quantity} × {item.name}
            </Text>
            <Text style={styles.rowVal}>{naira(item.unit_price_minor * item.quantity)}</Text>
          </View>
        ))}

        <View style={styles.divider} />

        <View style={styles.row}>
          <Text style={styles.rowLbl}>Subtotal</Text>
          <Text style={styles.rowVal}>{naira(order.items_total_minor)}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLbl}>Delivery fee</Text>
          <Text style={styles.rowVal}>{naira(order.delivery_fee_minor)}</Text>
        </View>
        <View style={[styles.row, styles.totalRow]}>
          <Text style={styles.totalLbl}>Total</Text>
          <Text style={styles.totalVal}>{naira(order.total_minor)}</Text>
        </View>
      </View>

      {/* Fulfillment details */}
      <View style={styles.section}>
        <Text style={styles.sectionH}>Delivery details</Text>
        <Detail label="Status" value={order.status} accent={statusBg} />
        <Detail
          label={order.fulfillment_type === 'pickup' ? 'Fulfillment' : 'Type'}
          value={order.fulfillment_type === 'pickup' ? 'Pickup' : 'Delivery'}
        />
        <Detail label="Date" value={order.fulfillment_date} />
        {order.fulfillment_type === 'delivery' && order.contact.address ? (
          <Detail label="Address" value={order.contact.address} />
        ) : order.fulfillment_type === 'pickup' ? (
          <Detail label="Note" value="We will message you when ready." />
        ) : null}
        {order.notes ? <Detail label="Notes" value={order.notes} /> : null}
      </View>

      {/* What happens next */}
      {!isCancelled && (
        <View style={[styles.section, { backgroundColor: C.cream2, borderColor: C.line }]}>
          <Text style={styles.sectionH}>What happens next</Text>
          <Text style={styles.nextTxt}>
            {order.fulfillment_type === 'pickup'
              ? `We'll message ${order.contact.phone} when your order is ready for pickup.`
              : `We'll contact ${order.contact.phone} to arrange delivery.`}
          </Text>
        </View>
      )}

      {/* Actions */}
      <View style={styles.actions}>
        <Pressable style={styles.btnOutline} onPress={load} disabled={loading}>
          <MaterialCommunityIcons name="refresh" size={18} color={C.green} />
          <Text style={styles.btnOutlineTxt}>Refresh status</Text>
        </Pressable>

        <Pressable
          style={styles.btnPhone}
          onPress={() => void Linking.openURL(`tel:${PHONE}`)}
          accessibilityLabel={`Call ${PHONE}`}
        >
          <MaterialCommunityIcons name="phone" size={18} color="#fff" />
          <Text style={styles.btnTxt}>Call us</Text>
        </Pressable>

        {canCancel && (
          <Pressable
            style={[styles.btnDanger, cancelling && { opacity: 0.5 }]}
            onPress={handleCancel}
            disabled={cancelling}
          >
            <Text style={styles.btnDangerTxt}>
              {cancelling ? 'Cancelling…' : 'Cancel this order'}
            </Text>
          </Pressable>
        )}

        <Pressable onPress={() => router.push('/(tabs)/menu')}>
          <Text style={styles.linkTxt}>Order something else</Text>
        </Pressable>
      </View>
    </ScrollView>
  )
}

function Detail({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLbl}>{label}</Text>
      <Text style={[styles.detailVal, accent ? { color: accent, fontWeight: '700' } : null]}>
        {value}
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  center: {
    flex: 1, backgroundColor: C.cream, alignItems: 'center',
    justifyContent: 'center', padding: 30, gap: 16,
  },
  errTxt: { color: C.burg, fontSize: 15, textAlign: 'center' },
  banner: {
    borderRadius: 16, padding: 18, flexDirection: 'row', alignItems: 'center',
    gap: 14, marginBottom: 16,
  },
  bannerIcon: { fontSize: 28, color: '#fff' },
  bannerTitle: { color: '#fff', fontWeight: '800', fontSize: 16, flexShrink: 1 },
  bannerSub: { color: 'rgba(255,255,255,0.85)', fontSize: 13, marginTop: 3, flexShrink: 1 },
  section: {
    backgroundColor: '#fff', borderRadius: 14, padding: 18, marginBottom: 14,
    borderWidth: 1, borderColor: C.line,
  },
  sectionH: { fontWeight: '800', fontSize: 15, color: C.green, marginBottom: 12 },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 5, gap: 10 },
  rowLbl: { color: C.mut, flex: 1, fontSize: 14 },
  rowVal: { color: C.ink, fontWeight: '600', fontSize: 14 },
  divider: { borderTopWidth: 1, borderTopColor: C.line, marginVertical: 8 },
  totalRow: { borderTopWidth: 2, borderTopColor: C.ink, paddingTop: 12, marginTop: 4 },
  totalLbl: { fontWeight: '800', fontSize: 16 },
  totalVal: { fontWeight: '800', fontSize: 16, color: C.green },
  detailRow: {
    flexDirection: 'row', justifyContent: 'space-between',
    paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: C.line, gap: 10,
  },
  detailLbl: { color: C.mut, fontSize: 14 },
  detailVal: { color: C.ink, fontSize: 14, flex: 1, textAlign: 'right' },
  nextTxt: { color: C.mut, fontSize: 14, lineHeight: 20 },
  actions: { gap: 12, marginTop: 4 },
  btn: {
    backgroundColor: C.green, borderRadius: 999, paddingVertical: 14,
    alignItems: 'center', paddingHorizontal: 24,
  },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
  btnOutline: {
    borderWidth: 2, borderColor: C.green, borderRadius: 999, paddingVertical: 13,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
  },
  btnOutlineTxt: { color: C.green, fontWeight: '700', fontSize: 15 },
  btnPhone: {
    backgroundColor: C.green, borderRadius: 999, paddingVertical: 14,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
  },
  btnDanger: {
    borderWidth: 2, borderColor: C.burg, borderRadius: 999,
    paddingVertical: 13, alignItems: 'center',
  },
  btnDangerTxt: { color: C.burg, fontWeight: '700', fontSize: 15 },
  linkTxt: {
    color: C.green, fontWeight: '600', fontSize: 14, textAlign: 'center',
    textDecorationLine: 'underline',
  },
})
