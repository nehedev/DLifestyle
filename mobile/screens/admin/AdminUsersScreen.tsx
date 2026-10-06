import { useCallback, useEffect, useState } from 'react'
import { Alert, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import {
  adminListUsers,
  adminSetUserRole,
  type UserAdminResponse,
} from '../../api'
import { AdminScreenShell, Badge, ListEmpty } from './ui'
import { C } from '../../theme'

export default function AdminUsersScreen() {
  const nav = useNavigation()
  const [items, setItems] = useState<UserAdminResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    try {
      const page = await adminListUsers()
      setItems(page.items)
    } catch (e) {
      Alert.alert('Could not load', e instanceof Error ? e.message : 'Unknown error')
    } finally { setLoading(false); setRefreshing(false) }
  }, [])

  useEffect(() => { void load() }, [load])

  const toggleRole = async (u: UserAdminResponse) => {
    const next = u.role === 'admin' ? 'user' : 'admin'
    Alert.alert(
      `${next === 'admin' ? 'Promote' : 'Demote'} user?`,
      `${u.first_name} ${u.last_name ?? ''} → ${next}`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Confirm',
          onPress: async () => {
            try { await adminSetUserRole(u.id, next); void load() }
            catch (e) { Alert.alert('Failed', e instanceof Error ? e.message : 'Unknown error') }
          },
        },
      ],
    )
  }

  return (
    <AdminScreenShell title="Users" onBack={() => nav.goBack()}>
      <FlatList
        data={items}
        keyExtractor={(i) => String(i.id)}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load() }} />
        }
        ListEmptyComponent={<ListEmpty loading={loading} text="No users yet." />}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        renderItem={({ item }) => (
          <Pressable style={styles.card} onPress={() => toggleRole(item)}>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{item.first_name} {item.last_name ?? ''}</Text>
              <Text style={styles.meta}>{item.email}</Text>
            </View>
            <Badge status={item.role} />
          </Pressable>
        )}
      />
    </AdminScreenShell>
  )
}

const styles = StyleSheet.create({
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 10, flexDirection: 'row', alignItems: 'center', gap: 12 },
  name: { fontWeight: '700', fontSize: 15, color: C.ink },
  meta: { color: C.mut, fontSize: 13, marginTop: 2 },
})