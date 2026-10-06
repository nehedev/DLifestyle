import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  FlatList,
  Image,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native'
import { useNavigation } from '@react-navigation/native'
import {
  adminCreateMenuItem,
  adminListMenuItems,
  adminPatchMenuItem,
  naira,
  type MenuItemAdmin,
} from '../../api'
import { AdminScreenShell, Badge, Btn, Drawer, Field, ListEmpty, WeekdayPicker } from './ui'
import { C } from '../../theme'

export default function AdminMenuScreen() {
  const nav = useNavigation()
  const [items, setItems] = useState<MenuItemAdmin[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [editing, setEditing] = useState<MenuItemAdmin | null>(null)
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    try {
      const page = await adminListMenuItems()
      setItems(page.items)
    } catch (e) {
      Alert.alert('Could not load', e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  return (
    <AdminScreenShell
      title="Menu items"
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
        ListEmptyComponent={<ListEmpty loading={loading} text="No menu items yet." />}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        renderItem={({ item }) => (
          <Pressable style={styles.card} onPress={() => setEditing(item)}>
            <View style={styles.rowTop}>
              {item.image_url ? (
                <Image source={{ uri: item.image_url }} style={styles.thumb} />
              ) : (
                <View style={[styles.thumb, { backgroundColor: C.cream2 }]} />
              )}
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{item.name}</Text>
                <Text style={styles.meta}>
                  {item.category} · {naira(item.price_minor)}
                </Text>
                <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
                  <Badge status={item.is_active ? 'active' : 'inactive'} />
                  {item.is_sold_out && <Badge status="sold out" />}
                </View>
              </View>
            </View>
          </Pressable>
        )}
      />

      <MenuEditor
        visible={creating}
        onClose={() => setCreating(false)}
        onSaved={() => { setCreating(false); void load() }}
      />
      <MenuEditor
        visible={Boolean(editing)}
        initial={editing ?? undefined}
        onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); void load() }}
      />
    </AdminScreenShell>
  )
}

function MenuEditor({
  visible, initial, onClose, onSaved,
}: {
  visible: boolean
  initial?: MenuItemAdmin
  onClose: () => void
  onSaved: () => void
}) {
  const isEdit = Boolean(initial)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [imageAlt, setImageAlt] = useState('')
  const [priceNaira, setPriceNaira] = useState('')
  const [weekdays, setWeekdays] = useState<number[]>([0, 1, 2, 3, 4, 5, 6])
  const [active, setActive] = useState(true)
  const [soldOut, setSoldOut] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!visible) return
    if (initial) {
      setName(initial.name)
      setDescription(initial.description ?? '')
      setCategory(initial.category)
      setImageUrl(initial.image_url ?? '')
      setImageAlt(initial.image_alt ?? '')
      setPriceNaira((initial.price_minor / 100).toFixed(2))
      setWeekdays(initial.weekdays)
      setActive(initial.is_active)
      setSoldOut(initial.is_sold_out)
    } else {
      setName(''); setDescription(''); setCategory(''); setImageUrl('')
      setImageAlt(''); setPriceNaira(''); setWeekdays([1, 2, 3, 4, 5, 6, 7])
      setActive(true); setSoldOut(false)
    }
  }, [visible, initial])

  const save = async () => {
    const price = Math.round(Number(priceNaira) * 100)
    if (!name || !category || !Number.isFinite(price) || price < 0) {
      Alert.alert('Missing info', 'Name, category and a valid price are required.')
      return
    }
    setBusy(true)
    try {
      const body = {
        name,
        description: description || null,
        category,
        image_url: imageUrl || null,
        image_alt: imageAlt || null,
        price_minor: price,
        weekdays,
        is_active: active,
        is_sold_out: soldOut,
      }
      if (isEdit && initial) await adminPatchMenuItem(initial.id, body)
      else await adminCreateMenuItem(body)
      onSaved()
    } catch (e) {
      Alert.alert('Save failed', e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Drawer visible={visible} onClose={onClose} title={isEdit ? 'Edit menu item' : 'New menu item'}>
      <Field label="Name" value={name} onChangeText={setName} />
      <Field label="Description" value={description} onChangeText={setDescription} multiline />
      <Field label="Category" value={category} onChangeText={setCategory} hint="e.g. Rice, Beans, Pasta" />
      <Field label="Price (₦)" value={priceNaira} onChangeText={setPriceNaira} keyboardType="decimal-pad" />
      <Field label="Image URL" value={imageUrl} onChangeText={setImageUrl} keyboardType="url" hint="Leave blank for the illustrated fallback" />
      <Field label="Image alt" value={imageAlt} onChangeText={setImageAlt} />
      <WeekdayPicker value={weekdays} onChange={setWeekdays} />

      <View style={{ flexDirection: 'row', gap: 20, marginBottom: 14 }}>
        <Pressable onPress={() => setActive(!active)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <View style={[styles.check, active && styles.checkOn]} />
          <Text style={{ fontWeight: '600' }}>Active</Text>
        </Pressable>
        <Pressable onPress={() => setSoldOut(!soldOut)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <View style={[styles.check, soldOut && styles.checkOn]} />
          <Text style={{ fontWeight: '600' }}>Sold out</Text>
        </Pressable>
      </View>

      <Btn title={isEdit ? 'Save changes' : 'Create item'} onPress={save} busy={busy} />
    </Drawer>
  )
}

const styles = StyleSheet.create({
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 10 },
  rowTop: { flexDirection: 'row', gap: 12, alignItems: 'center' },
  thumb: { width: 56, height: 56, borderRadius: 10 },
  name: { fontWeight: '700', fontSize: 16, color: C.ink },
  meta: { color: C.mut, fontSize: 13, marginTop: 2 },
  check: {
    width: 20, height: 20, borderRadius: 6,
    borderWidth: 1.5, borderColor: C.line, backgroundColor: '#fff',
  },
  checkOn: { backgroundColor: C.green, borderColor: C.green },
})