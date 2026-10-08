import { MaterialCommunityIcons } from '@expo/vector-icons'
import { router } from 'expo-router'
import { useEffect, useState } from 'react'
import {
  Image,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useSession } from '@/auth'
import { useCart } from '@/store'
import { C } from '@/theme'

type Tab = 'index' | 'menu' | 'cart' | 'orders'

const TAB_ROUTES: Record<Tab, string> = {
  index: '/(tabs)/',
  menu: '/(tabs)/menu',
  cart: '/(tabs)/cart',
  orders: '/(tabs)/orders',
}

export function Header() {
  const insets = useSafeAreaInsets()
  const { count } = useCart()
  const { isAuthenticated, isLoading, name, picture, login, logout, error } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)

  // Close the account menu if the user signs out while it's open.
  useEffect(() => {
    if (!isAuthenticated && menuOpen) setMenuOpen(false)
  }, [isAuthenticated, menuOpen])

  const goToTab = (tab: Tab) => router.push(TAB_ROUTES[tab] as never)

  const initial = (name ?? '?')[0].toUpperCase()

  return (
    <>
      <View style={[styles.hdr, { paddingTop: insets.top + 10 }]}>
        <View style={styles.hdrIn}>
          <Pressable style={styles.brand} onPress={() => goToTab('index')} hitSlop={6}>
            <Image
              source={require('@/assets/images/logo.png')}
              style={styles.logo}
              resizeMode="contain"
            />
            <View>
              <Text style={styles.wm}>DAMI'S</Text>
              <Text style={styles.wm}>LIFESTYLE</Text>
            </View>
          </Pressable>

          <View style={styles.hdrRight}>
            <Pressable
              style={styles.cartBtn}
              onPress={() => goToTab('cart')}
              hitSlop={6}
              accessibilityLabel={`Cart, ${count} items`}
            >
              <MaterialCommunityIcons name="cart-outline" size={24} color={C.ink} />
              {count > 0 && (
                <View style={styles.badge}>
                  <Text style={styles.badgeTxt}>{count}</Text>
                </View>
              )}
            </Pressable>

            {isAuthenticated ? (
              <Pressable
                style={styles.avatar}
                onPress={() => setMenuOpen(true)}
                accessibilityLabel="Account menu"
              >
                {picture ? (
                  <Image source={{ uri: picture }} style={styles.photo} />
                ) : (
                  <Text style={styles.initial}>{initial}</Text>
                )}
              </Pressable>
            ) : (
              <Pressable
                style={[styles.signIn, isLoading && { opacity: 0.5 }]}
                onPress={login}
                disabled={isLoading}
              >
                <Text style={styles.signInTxt}>Sign in</Text>
              </Pressable>
            )}
          </View>
        </View>
      </View>

      {error && (
        <View style={styles.errorBanner}>
          <MaterialCommunityIcons name="alert-circle" size={18} color={C.burg} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      <Modal
        transparent
        visible={menuOpen}
        animationType="fade"
        onRequestClose={() => setMenuOpen(false)}
      >
        <Pressable style={styles.backdrop} onPress={() => setMenuOpen(false)}>
          <Pressable style={styles.menu} onPress={(e) => e.stopPropagation()}>
            <View style={styles.menuTop}>
              {picture ? (
                <Image source={{ uri: picture }} style={styles.menuPhoto} />
              ) : (
                <View style={styles.menuInitial}>
                  <Text style={styles.initial}>{initial}</Text>
                </View>
              )}
              <Text style={styles.menuName} numberOfLines={1}>
                {name ?? 'Account'}
              </Text>
            </View>

            <Pressable
              style={styles.menuItem}
              onPress={() => {
                setMenuOpen(false)
                goToTab('orders')
              }}
            >
              <MaterialCommunityIcons name="receipt" size={18} color={C.mut} />
              <Text style={styles.menuItemTxt}>My orders</Text>
            </Pressable>

            <Pressable
              style={styles.menuItem}
              onPress={() => {
                setMenuOpen(false)
                logout()
              }}
            >
              <MaterialCommunityIcons name="logout" size={18} color={C.burg} />
              <Text style={[styles.menuItemTxt, { color: C.burg }]}>Sign out</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  )
}

const styles = StyleSheet.create({
  hdr: {
    backgroundColor: C.cream,
    borderBottomWidth: 1,
    borderBottomColor: '#d8d4a8',
    paddingBottom: 12,
    paddingHorizontal: 20,
  },
  hdrIn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  logo: {
    width: 34,
    height: 34,
  },
  wm: { fontWeight: '800', fontSize: 12, color: C.ink, letterSpacing: 0.5 },
  hdrRight: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  cartBtn: { padding: 4 },
  badge: {
    position: 'absolute',
    top: -2,
    right: -6,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: C.burg,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 4,
  },
  badgeTxt: { color: '#fff', fontWeight: '700', fontSize: 11 },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 2,
    borderColor: C.gold,
    backgroundColor: C.green,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  photo: { width: '100%', height: '100%' },
  initial: { color: '#fff', fontWeight: '700', fontSize: 15 },
  signIn: {
    backgroundColor: C.burg,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
  },
  signInTxt: { color: '#fff', fontWeight: '600', fontSize: 13 },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.15)',
    alignItems: 'flex-end',
  },
  menu: {
    marginTop: 70,
    marginRight: 16,
    backgroundColor: '#fff',
    borderRadius: 16,
    minWidth: 210,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 6,
  },
  menuTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: 14,
    backgroundColor: C.cream2,
    borderBottomWidth: 1,
    borderBottomColor: C.line,
  },
  menuPhoto: { width: 38, height: 38, borderRadius: 19 },
  menuInitial: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: C.green,
    alignItems: 'center',
    justifyContent: 'center',
  },
  menuName: {
    flex: 1,
    fontWeight: '700',
    fontSize: 15,
    color: C.ink,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 14,
  },
  menuItemTxt: { fontWeight: '600', fontSize: 14, color: C.ink },
  errorBanner: {
    backgroundColor: '#FEE',
    borderBottomWidth: 1,
    borderBottomColor: C.burg,
    paddingHorizontal: 20,
    paddingVertical: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  errorText: {
    flex: 1,
    color: C.burg,
    fontSize: 13,
    fontWeight: '600',
  },
})
