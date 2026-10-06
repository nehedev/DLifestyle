import { useCallback, useEffect, useState } from 'react'
import { Alert, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import {
  adminListServiceRequests,
  adminPatchServiceRequest,
  naira,
  type ServiceRequestAdminResponse,
} from '../../api'
import { AdminScreenShell, Badge, Btn, Drawer, Field, ListEmpty } from './ui'
import { C } from '../../theme'

export default function AdminServiceRequestsScreen() {
  const nav = useNavigation()
  const [items, setItems] = useState<ServiceRequestAdminResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [open, setOpen] = useState<ServiceRequestAdminResponse | null>(null)

  const load = useCallback(async () => {
    try {
      const page = await adminListServiceRequests()
      setItems(page.items)
    } catch (e) {
      Alert.alert('Could not load', e instanceof Error ? e.message : 'Unknown error')
    } finally { setLoading(false); setRefreshing(false) }
  }, [])

  useEffect(() => { void load() }, [load])

  return (
    <AdminScreenShell title="Service requests" onBack={() => nav.goBack()}>
      <FlatList
        data={items}
        keyExtractor={(i) => String(i.id)}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} />
        }
        ListEmptyComponent={<ListEmpty loading={loading} text="No service requests yet." />}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        renderItem={({ item }) => (
          <Pressable style={styles.card} onPress={() => setOpen(item)}>
            <View style={styles.row}>
              <Text style={styles.title}>Request #{item.id}</Text>
              <Badge status={item.status} />
            </View>
            <Text style={styles.meta} numberOfLines={1}>{item.location}</Text>
            {item.quoted_amount_minor != null && (
              <Text style={styles.total}>Quote: {naira(item.quoted_amount_minor)}</Text>
            )}
          </Pressable>
        )}
      />

      <Editor
        visible={Boolean(open)}
        initial={open}
        onClose={() => setOpen(null)}
        onSaved={() => { setOpen(null); void load() }}
      />
    </AdminScreenShell>
  )
}

function Editor({
  visible, initial, onClose, onSaved,
}: { visible: boolean; initial: ServiceRequestAdminResponse | null; onClose: () => void; onSaved: () => void }) {
  const [status, setStatus] = useState('')
  const [quote, setQuote] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!visible || !initial) return
    setStatus(initial.status)
    setQuote(initial.quoted_amount_minor != null ? (initial.quoted_amount_minor / 100).toFixed(2) : '')
    setNote(initial.owner_note ?? '')
  }, [visible, initial])

  const save = async () => {
    if (!initial) return
    setBusy(true)
    try {
      const quoted = quote ? Math.round(Number(quote) * 100) : null
      await adminPatchServiceRequest(initial.id, {
        status: status || undefined,
        quoted_amount_minor: quoted,
        owner_note: note || null,
      })
      onSaved()
    } catch (e) {
      Alert.alert('Save failed', e instanceof Error ? e.message : 'Unknown error')
    } finally { setBusy(false) }
  }

  if (!initial) return null

  return (
    <Drawer visible={visible} onClose={onClose} title={`Request #${initial.id}`}>
      <View style={{ gap: 6, marginBottom: 14 }}>
        <Text style={{ color: C.mut }}>{initial.location}</Text>
        <Text style={{ color: C.mut }}>{initial.contact_phone}</Text>
        {initial.preferred_date ? <Text style={{ color: C.mut }}>Preferred: {initial.preferred_date}</Text> : null}
      </View>
      <Text style={{ fontWeight: '600', marginBottom: 6 }}>Details</Text>
      <Text style={{ color: C.mut, marginBottom: 16 }}>{initial.details}</Text>

      <Field label="Status" value={status} onChangeText={setStatus} hint="e.g. pending, quoted, scheduled, completed, cancelled" />
      <Field label="Quote amount (₦)" value={quote} onChangeText={setQuote} keyboardType="decimal-pad" />
      <Field label="Owner note" value={note} onChangeText={setNote} multiline />

      <Btn title="Save" onPress={save} busy={busy} />
    </Drawer>
  )
}

const styles = StyleSheet.create({
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 10 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  title: { fontWeight: '700', fontSize: 16, color: C.ink },
  meta: { color: C.mut, fontSize: 13, marginTop: 4 },
  total: { fontWeight: '800', color: C.green, marginTop: 6, fontSize: 15 },
})