import { useCallback, useEffect, useState } from 'react'
import { Alert, FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import { adminListPayments, naira, type AdminPaymentListItem } from '../../api'
import { AdminScreenShell, Badge, ListEmpty } from './ui'
import { C } from '../../theme'

export default function AdminPaymentsScreen() {
  const nav = useNavigation()
  const [items, setItems] = useState<AdminPaymentListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    try {
      const page = await adminListPayments()
      setItems(page.items)
    } catch (e) {
      Alert.alert('Could not load', e instanceof Error ? e.message : 'Unknown error')
    } finally { setLoading(false); setRefreshing(false) }
  }, [])

  useEffect(() => { void load() }, [load])

  return (
    <AdminScreenShell title="Payments" onBack={() => nav.goBack()}>
      <FlatList
        data={items}
        keyExtractor={(i) => String(i.id)}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} />
        }
        ListEmptyComponent={<ListEmpty loading={loading} text="No payments recorded." />}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.row}>
              <Text style={styles.ref}>{item.reference}</Text>
              <Badge status={item.status} />
            </View>
            <Text style={styles.meta}>Order #{item.order_id}</Text>
            <Text style={styles.total}>{naira(item.amount_minor)}</Text>
          </View>
        )}
      />
    </AdminScreenShell>
  )
}

const styles = StyleSheet.create({
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 10 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  ref: { fontWeight: '700', fontSize: 14, color: C.ink },
  meta: { color: C.mut, fontSize: 13, marginTop: 4 },
  total: { fontWeight: '800', color: C.green, marginTop: 6, fontSize: 16 },
})