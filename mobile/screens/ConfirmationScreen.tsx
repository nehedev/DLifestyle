import AsyncStorage from '@react-native-async-storage/async-storage'
import { MaterialCommunityIcons } from '@expo/vector-icons'
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { naira, payOrder } from '../api'
import * as WebBrowser from 'expo-web-browser'
import { Alert } from 'react-native'
import { C } from '../theme'
import type { RootStackParamList } from '../navigation'

// The Paystack hosted page redirects back here after payment. On mobile we use
// the in-app browser session so we can intercept the redirect immediately.
const WEB_CALLBACK =
  (process.env.EXPO_PUBLIC_WEB_CALLBACK_URL as string | undefined) ??
  'https://d-lifestyle-blond.vercel.app/payment/callback'

export default function ConfirmationScreen() {
  const nav = useNavigation<NativeStackNavigationProp<RootStackParamList>>()
  const route = useRoute<RouteProp<RootStackParamList, 'Confirmation'>>()
  const { order } = route.params

  const startPayment = async () => {
    try {
        await AsyncStorage.setItem('damis.pending_payment_order', String(order.id))
        const { authorization_url } = await payOrder(order.id)
        const result = await WebBrowser.openAuthSessionAsync(authorization_url, WEB_CALLBACK)
        // Whether the user completed or dismissed, hand off to the poller.
        // It reads the pending order id from storage.
        nav.replace('PaymentCallback', { orderId: order.id })
        void result
    } catch (e) {
        Alert.alert('Payment failed', e instanceof Error ? e.message : 'Try again')
    }
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: C.cream }} contentContainerStyle={{ padding: 24, paddingTop: 60 }}>
      <View style={{ alignItems: 'center' }}>
        <View style={styles.ok}>
          <MaterialCommunityIcons name="check" size={40} color={C.gold} />
        </View>
        <Text style={styles.h1}>Order placed</Text>
        <Text style={styles.lead}>
          Order #{order.id} · {order.fulfillment_type}
        </Text>
      </View>

      <View style={styles.sum}>
        {order.items.map((it, i) => (
          <View key={i} style={styles.row}>
            <Text style={{ flex: 1 }}>
              {it.quantity}× {it.name}
            </Text>
            <Text>{naira(it.unit_price_minor * it.quantity)}</Text>
          </View>
        ))}
        <View style={styles.row}>
          <Text style={styles.lbl}>Items total</Text>
          <Text>{naira(order.items_total_minor)}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.lbl}>Delivery</Text>
          <Text>{naira(order.delivery_fee_minor)}</Text>
        </View>
        <View style={[styles.row, { borderTopWidth: 2, borderTopColor: C.ink, marginTop: 8, paddingTop: 12 }]}>
          <Text style={{ fontWeight: '800', fontSize: 17 }}>Total</Text>
          <Text style={{ fontWeight: '800', fontSize: 17 }}>{naira(order.total_minor)}</Text>
        </View>
      </View>

      <Pressable style={styles.btn} onPress={startPayment}>
        <Text style={styles.btnTxt}>Pay now</Text>
      </Pressable>
      <Pressable style={styles.ghost} onPress={() => nav.navigate('Tabs', { screen: 'Orders' } as never)}>
        <Text style={styles.ghostTxt}>I'll pay later</Text>
      </Pressable>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  ok: {
    width: 72, height: 72, borderRadius: 36, backgroundColor: C.green,
    alignItems: 'center', justifyContent: 'center', marginBottom: 12,
  },
  h1: { fontSize: 28, fontWeight: '800', color: C.green },
  lead: { color: C.mut, marginTop: 6, textAlign: 'center' },
  sum: {
    backgroundColor: '#fff', borderRadius: 14, padding: 20, marginTop: 24,
    borderWidth: 1, borderColor: C.line, gap: 6,
  },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  lbl: { color: C.mut },
  btn: {
    marginTop: 20, backgroundColor: C.green, borderRadius: 999,
    paddingVertical: 14, alignItems: 'center',
  },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 16 },
  ghost: { marginTop: 12, paddingVertical: 14, alignItems: 'center' },
  ghostTxt: { color: C.green, fontWeight: '600' },
})