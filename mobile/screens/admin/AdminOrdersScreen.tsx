import { useCallback, useEffect, useState } from 'react'
import { Alert, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import {
  adminGetOrder,
  adminListOrders,
  adminSetOrderStatus,
  naira,
  type AdminOrderDetail,
  type AdminOrderListItem,
} from '../../api'
import { AdminScreenShell, Badge, Btn, Drawer, ListEmpty } from './ui'
import { C } from '../../theme'

const STATUSES: { value: AdminOrderListItem['status'] | 'preparing' | 'ready' | 'completed' | 'cancelled'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'paid', label: 'Paid' },
  { value: 'preparing', label: 'Preparing' },
  { value: 'ready', label: 'Ready' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
]

export default function AdminOrdersScreen() {
  const nav = useNavigation()
  const [items, setItems] = useState<AdminOrderListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [filter, setFilter] = useState<string>('all')
  const [open, setOpen] = useState<AdminOrderDetail | null>(null)

  const load = useCallback(async () => {
    try {
      const page = await adminListOrders(filter === 'all' ? {} : { status: filter })
      setItems(page.items)
    } catch (e) {
      Alert.alert('Could not load', e instanceof Error ? e.message : 'Unknown error')
    } finally { setLoading(false); setRefreshing(false) }
  }, [filter])

  useEffect(() => { void load() }, [load])

  const openOrder = async (id: number) => {
    try { setOpen(await adminGetOrder(id)) }
    catch (e) { Alert.alert('Could not load', e instanceof Error ? e.message : 'Unknown error') }
  }

  const setStatus = async (status: 'preparing' | 'ready' | 'completed' | 'cancelled') => {
    if (!open) return
    try {
      const updated = await adminSetOrderStatus(open.id, status)
      setOpen(updated); void load()
    } catch (e) {
      Alert.alert('Update failed', e instanceof Error ? e.message : 'Unknown error')
    }
  }

  return (
    <AdminScreenShell title="Orders" onBack={() => nav.goBack()}>
      <View style={styles.chips}>
        {STATUSES.map((s) => (
          <Pressable
            key={s.value}
            onPress={() => setFilter(s.value)}
            style={[styles.chip, filter === s.value && styles.chipOn]}
          >
            <Text style={[styles.chipTxt, filter === s.value && styles.chipTxtOn]}>{s.label}</Text>
          </Pressable>
        ))}
      </View>

      <FlatList
        data={items}
        keyExtractor={(i) => String(i.id)}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} />
        }
        ListEmptyComponent={<ListEmpty loading={loading} text="No orders." />}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        renderItem={({ item }) => (
          <Pressable style={styles.card} onPress={() => openOrder(item.id)}>
            <View style={styles.row}>
              <Text style={styles.title}>Order #{item.id}</Text>
              <Badge status={item.status} />
            </View>
            <Text style={styles.meta}>
              {item.fulfillment_type} · {item.fulfillment_date}
            </Text>
            <Text style={styles.total}>{naira(item.total_minor)}</Text>
          </Pressable>
        )}
      />

      <Drawer visible={Boolean(open)} onClose={() => setOpen(null)} title={open ? `Order #${open.id}` : ''}>
        {open && (
          <>
            <View style={{ marginBottom: 12, gap: 6 }}>
              <View style={styles.metaRow}><Text style={styles.metaLbl}>Status</Text><Badge status={open.status} /></View>
              <View style={styles.metaRow}><Text style={styles.metaLbl}>Fulfillment</Text><Text>{open.fulfillment_type}</Text></View>
              <View style={styles.metaRow}><Text style={styles.metaLbl}>Date</Text><Text>{open.fulfillment_date}</Text></View>
              <View style={styles.metaRow}><Text style={styles.metaLbl}>User</Text><Text>#{open.user_id}</Text></View>
            </View>

            <Text style={styles.sectionH}>Contact</Text>
            <View style={{ marginBottom: 12, gap: 4 }}>
              <Text style={{ fontWeight: '600' }}>{open.contact.name}</Text>
              <Text style={{ color: C.mut }}>{open.contact.phone}</Text>
              {open.contact.address ? <Text style={{ color: C.mut }}>{open.contact.address}</Text> : null}
            </View>

            {open.notes ? (
              <>
                <Text style={styles.sectionH}>Notes</Text>
                <Text style={{ color: C.mut, marginBottom: 12 }}>{open.notes}</Text>
              </>
            ) : null}

            <Text style={styles.sectionH}>Items</Text>
            <View style={{ marginBottom: 12 }}>
              {open.items.map((it) => (
                <View key={it.id} style={styles.itemRow}>
                  <Text style={{ flex: 1 }}>{it.quantity}× {it.name}</Text>
                  <Text>{naira(it.unit_price_minor * it.quantity)}</Text>
                </View>
              ))}
              <View style={[styles.itemRow, { borderTopWidth: 1, borderTopColor: C.line, marginTop: 6, paddingTop: 8 }]}>
                <Text style={{ flex: 1, color: C.mut }}>Delivery</Text>
                <Text>{naira(open.delivery_fee_minor)}</Text>
              </View>
              <View style={[styles.itemRow, { borderTopWidth: 2, borderTopColor: C.ink, marginTop: 6, paddingTop: 8 }]}>
                <Text style={{ flex: 1, fontWeight: '800' }}>Total</Text>
                <Text style={{ fontWeight: '800' }}>{naira(open.total_minor)}</Text>
              </View>
            </View>

            {open.payments.length > 0 && (
              <>
                <Text style={styles.sectionH}>Payments</Text>
                {open.payments.map((p) => (
                  <View key={p.id} style={styles.itemRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontWeight: '600' }}>{p.reference}</Text>
                      <Text style={{ color: C.mut, fontSize: 12 }}>{p.status}</Text>
                    </View>
                    <Text>{naira(p.amount_minor)}</Text>
                  </View>
                ))}
              </>
            )}

            <Text style={styles.sectionH}>Update status</Text>
            <View style={{ gap: 8 }}>
              <Btn title="Mark preparing" onPress={() => setStatus('preparing')} variant="ghost" />
              <Btn title="Mark ready" onPress={() => setStatus('ready')} variant="ghost" />
              <Btn title="Mark completed" onPress={() => setStatus('completed')} />
              <Btn title="Cancel order" onPress={() => setStatus('cancelled')} variant="danger" />
            </View>
          </>
        )}
      </Drawer>
    </AdminScreenShell>
  )
}

const styles = StyleSheet.create({
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, padding: 12 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, borderWidth: 1.5, borderColor: C.line, backgroundColor: '#fff' },
  chipOn: { backgroundColor: C.green, borderColor: C.green },
  chipTxt: { fontWeight: '600', fontSize: 13, color: C.green },
  chipTxtOn: { color: '#fff' },
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 10 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  title: { fontWeight: '700', fontSize: 16, color: C.ink },
  meta: { color: C.mut, fontSize: 13, marginTop: 4 },
  total: { fontWeight: '800', color: C.green, marginTop: 6, fontSize: 16 },
  metaRow: { flexDirection: 'row', justifyContent: 'space-between' },
  metaLbl: { color: C.mut },
  sectionH: { fontWeight: '700', color: C.green, marginTop: 12, marginBottom: 8 },
  itemRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
})