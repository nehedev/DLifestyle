import { useCallback, useEffect, useState } from 'react'
import { Alert, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import {
  adminCreateService,
  adminListServices,
  adminPatchService,
  type ServiceAdmin,
} from '../../api'
import { AdminScreenShell, Badge, Btn, Drawer, Field, ListEmpty } from './ui'
import { C } from '../../theme'

export default function AdminServicesScreen() {
  const nav = useNavigation()
  const [items, setItems] = useState<ServiceAdmin[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [editing, setEditing] = useState<ServiceAdmin | null>(null)
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    try {
      const page = await adminListServices()
      setItems(page.items)
    } catch (e) {
      Alert.alert('Could not load', e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false); setRefreshing(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  return (
    <AdminScreenShell
      title="Services"
      onBack={() => nav.goBack()}
      action={
        <Pressable onPress={() => setCreating(true)} hitSlop={10}>
          <Text style={{ color: C.gold, fontWeight: '700' }}>New</Text>
        </Pressable>
      }
    >
      <FlatList
        data={items}
        keyExtractor={(i) => String(i.id)}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} />
        }
        ListEmptyComponent={<ListEmpty loading={loading} text="No services yet." />}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        renderItem={({ item }) => (
          <Pressable style={styles.card} onPress={() => setEditing(item)}>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{item.name}</Text>
              <Text style={styles.meta} numberOfLines={2}>{item.description}</Text>
              <View style={{ marginTop: 6 }}>
                <Badge status={item.is_active ? 'active' : 'inactive'} />
              </View>
            </View>
          </Pressable>
        )}
      />

      <ServiceEditor visible={creating} onClose={() => setCreating(false)} onSaved={() => { setCreating(false); void load() }} />
      <ServiceEditor visible={Boolean(editing)} initial={editing ?? undefined} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void load() }} />
    </AdminScreenShell>
  )
}

function ServiceEditor({
  visible, initial, onClose, onSaved,
}: { visible: boolean; initial?: ServiceAdmin; onClose: () => void; onSaved: () => void }) {
  const isEdit = Boolean(initial)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [sortOrder, setSortOrder] = useState('')
  const [active, setActive] = useState(true)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!visible) return
    if (initial) {
      setName(initial.name)
      setDescription(initial.description)
      setSortOrder(String(initial.sort_order))
      setActive(initial.is_active)
    } else {
      setName(''); setDescription(''); setSortOrder(''); setActive(true)
    }
  }, [visible, initial])

  const save = async () => {
    if (!name || !description) { Alert.alert('Missing info', 'Name and description are required.'); return }
    setBusy(true)
    try {
      const body = {
        name,
        description,
        is_active: active,
        sort_order: sortOrder ? Number(sortOrder) : null,
      }
      if (isEdit && initial) await adminPatchService(initial.id, body)
      else await adminCreateService(body)
      onSaved()
    } catch (e) {
      Alert.alert('Save failed', e instanceof Error ? e.message : 'Unknown error')
    } finally { setBusy(false) }
  }

  return (
    <Drawer visible={visible} onClose={onClose} title={isEdit ? 'Edit service' : 'New service'}>
      <Field label="Name" value={name} onChangeText={setName} />
      <Field label="Description" value={description} onChangeText={setDescription} multiline />
      <Field label="Sort order" value={sortOrder} onChangeText={setSortOrder} keyboardType="number-pad" />
      <Pressable onPress={() => setActive(!active)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <View style={[styles.check, active && styles.checkOn]} />
        <Text style={{ fontWeight: '600' }}>Active</Text>
      </Pressable>
      <Btn title={isEdit ? 'Save changes' : 'Create service'} onPress={save} busy={busy} />
    </Drawer>
  )
}

const styles = StyleSheet.create({
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 10 },
  name: { fontWeight: '700', fontSize: 16, color: C.ink },
  meta: { color: C.mut, fontSize: 13, marginTop: 2 },
  check: { width: 20, height: 20, borderRadius: 6, borderWidth: 1.5, borderColor: C.line, backgroundColor: '#fff' },
  checkOn: { backgroundColor: C.green, borderColor: C.green },
})