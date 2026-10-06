import { MaterialCommunityIcons } from '@expo/vector-icons'
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useAdmin, useSession } from '../../auth'
import { C } from '../../theme'
import type { AdminStackParamList } from '../../navigation'

type Nav = NativeStackNavigationProp<AdminStackParamList>

const SECTIONS: {
  key: keyof AdminStackParamList
  label: string
  icon: keyof typeof MaterialCommunityIcons.glyphMap
  tint: string
}[] = [
  { key: 'AdminOrders', label: 'Orders', icon: 'receipt-text-outline', tint: '#0A6A1B' },
  { key: 'AdminMenu', label: 'Menu items', icon: 'silverware-fork-knife', tint: '#D9541E' },
  { key: 'AdminServices', label: 'Services', icon: 'sparkles', tint: '#3D2817' },
  { key: 'AdminServiceRequests', label: 'Service requests', icon: 'clipboard-text-outline', tint: '#B8791F' },
  { key: 'AdminPayments', label: 'Payments', icon: 'credit-card-outline', tint: '#A71930' },
  { key: 'AdminUsers', label: 'Users', icon: 'account-group-outline', tint: '#064E12' },
  { key: 'AdminStore', label: 'Store settings', icon: 'cog-outline', tint: '#566357' },
]

export default function AdminHomeScreen() {
  const insets = useSafeAreaInsets()
  const nav = useNavigation<Nav>()
  const { isAuthenticated, login, logout, name } = useSession()
  const { isAdmin, loading } = useAdmin()

  if (!isAuthenticated) {
    return (
      <View style={[styles.gate, { paddingTop: insets.top + 40 }]}>
        <MaterialCommunityIcons name="shield-lock-outline" size={56} color={C.green} />
        <Text style={styles.gateH}>Admin sign-in required</Text>
        <Text style={styles.gateP}>
          Sign in with your admin Google account to manage the store.
        </Text>
        <Pressable style={styles.btn} onPress={login}>
          <Text style={styles.btnTxt}>Sign in</Text>
        </Pressable>
        <Pressable onPress={() => nav.getParent()?.goBack()}>
          <Text style={styles.link}>Back to store</Text>
        </Pressable>
      </View>
    )
  }

  if (loading) {
    return (
      <View style={styles.gate}>
        <ActivityIndicator color={C.green} />
      </View>
    )
  }

  if (!isAdmin) {
    return (
      <View style={[styles.gate, { paddingTop: insets.top + 40 }]}>
        <MaterialCommunityIcons name="account-alert-outline" size={56} color={C.burg} />
        <Text style={styles.gateH}>Not authorized</Text>
        <Text style={styles.gateP}>
          Signed in as {name ?? 'user'} — this account doesn't have admin access.
        </Text>
        <Pressable style={styles.ghost} onPress={logout}>
          <Text style={styles.ghostTxt}>Sign out</Text>
        </Pressable>
        <Pressable onPress={() => nav.getParent()?.goBack()}>
          <Text style={styles.link}>Back to store</Text>
        </Pressable>
      </View>
    )
  }

  return (
    <View style={{ flex: 1, backgroundColor: C.greenDark }}>
      <View style={[styles.header, { paddingTop: insets.top + 14 }]}>
        <View>
          <Text style={styles.hi}>Admin console</Text>
          <Text style={styles.sub}>Signed in as {name}</Text>
        </View>
        <Pressable onPress={logout} hitSlop={10}>
          <MaterialCommunityIcons name="logout" size={22} color="#fff" />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.grid} showsVerticalScrollIndicator={false}>
        {SECTIONS.map((s) => (
          <Pressable
            key={s.key as string}
            style={styles.tile}
            onPress={() => nav.navigate(s.key as never)}
          >
            <View style={[styles.tileIcon, { backgroundColor: s.tint }]}>
              <MaterialCommunityIcons name={s.icon} size={26} color="#fff" />
            </View>
            <Text style={styles.tileLabel}>{s.label}</Text>
            <MaterialCommunityIcons name="chevron-right" size={22} color={C.mut} />
          </Pressable>
        ))}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingBottom: 20,
  },
  hi: { color: '#fff', fontSize: 22, fontWeight: '800' },
  sub: { color: 'rgba(255,255,255,0.7)', marginTop: 2, fontSize: 13 },
  grid: { padding: 16, gap: 10, paddingBottom: 40 },
  tile: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    backgroundColor: '#fff', borderRadius: 16, padding: 16,
  },
  tileIcon: {
    width: 44, height: 44, borderRadius: 12,
    alignItems: 'center', justifyContent: 'center',
  },
  tileLabel: { flex: 1, fontSize: 16, fontWeight: '700', color: C.ink },
  gate: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    padding: 30, gap: 12, backgroundColor: C.cream,
  },
  gateH: { fontSize: 22, fontWeight: '800', color: C.green, marginTop: 8 },
  gateP: { color: C.mut, textAlign: 'center', maxWidth: 320 },
  btn: {
    marginTop: 8, backgroundColor: C.green, borderRadius: 999,
    paddingHorizontal: 24, paddingVertical: 14,
  },
  btnTxt: { color: '#fff', fontWeight: '700' },
  ghost: {
    marginTop: 8, borderWidth: 2, borderColor: C.green,
    borderRadius: 999, paddingHorizontal: 24, paddingVertical: 12,
  },
  ghostTxt: { color: C.green, fontWeight: '700' },
  link: { color: C.green, fontWeight: '600', marginTop: 16, textDecorationLine: 'underline' },
})