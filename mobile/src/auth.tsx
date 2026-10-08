import AsyncStorage from '@react-native-async-storage/async-storage'
import {
  GoogleSignin,
  isErrorWithCode,
  isNoSavedCredentialFoundResponse,
  isSuccessResponse,
  statusCodes,
} from '@react-native-google-signin/google-signin'
import * as SecureStore from 'expo-secure-store'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  Animated,
  Modal,
  Platform,
  StyleSheet,
  Text,
  View,
} from 'react-native'
import { ApiError, googleSignInWithToken, setAccessTokenGetter } from './api'
import { C } from './theme'

// The WEB client ID is required on both platforms: it becomes the `aud` of the
// id_token, so your backend must verify tokens against this client ID.
const WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID as string | undefined
// Optional on iOS if GoogleService-Info.plist is present; harmless to pass.
const IOS_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID as string | undefined

export const googleConfigured = Boolean(WEB_CLIENT_ID)

if (WEB_CLIENT_ID) {
  GoogleSignin.configure({
    webClientId: WEB_CLIENT_ID,
    iosClientId: IOS_CLIENT_ID,
    scopes: ['profile', 'email'],
  })
}

// ─── Session context ─────────────────────────────────────────────────────────

export interface Session {
  isAuthenticated: boolean
  isLoading: boolean
  ready: boolean
  name?: string
  picture?: string
  login: () => void
  logout: () => void
  error?: string
}

const SessionContext = createContext<Session>({
  isAuthenticated: false,
  isLoading: false,
  ready: false,
  login: () => {},
  logout: () => {},
})
export const useSession = () => useContext(SessionContext)

// ─── Persistence ─────────────────────────────────────────────────────────────
// Token goes in the encrypted keychain/keystore on native; AsyncStorage on web.
// Non-sensitive profile bits stay in AsyncStorage.

const TOKEN_KEY = 'damis.google_token'
const EXPIRY_KEY = 'damis.google_expiry'
const NAME_KEY = 'damis.user_name'
const PICTURE_KEY = 'damis.user_picture'

async function persistSession(
  idToken: string,
  expiresAt: number, // seconds since epoch
  name?: string,
  picture?: string,
) {
  if (Platform.OS === 'web') {
    // Web: store everything in AsyncStorage (no SecureStore support)
    await AsyncStorage.multiSet([
      [TOKEN_KEY, idToken],
      [EXPIRY_KEY, String(expiresAt * 1000)],
      [NAME_KEY, name ?? ''],
      [PICTURE_KEY, picture ?? ''],
    ])
  } else {
    // Native: token in SecureStore, profile in AsyncStorage
    await SecureStore.setItemAsync(TOKEN_KEY, idToken)
    await AsyncStorage.multiSet([
      [EXPIRY_KEY, String(expiresAt * 1000)],
      [NAME_KEY, name ?? ''],
      [PICTURE_KEY, picture ?? ''],
    ])
  }
}

async function loadSession() {
  let token: string | null
  
  if (Platform.OS === 'web') {
    // Web: load everything from AsyncStorage
    const entries = await AsyncStorage.multiGet([TOKEN_KEY, EXPIRY_KEY, NAME_KEY, PICTURE_KEY])
    const map = Object.fromEntries(entries)
    token = map[TOKEN_KEY] || null
    if (!token) return null
    return {
      token,
      expiry: Number(map[EXPIRY_KEY] ?? 0),
      name: map[NAME_KEY] || undefined,
      picture: map[PICTURE_KEY] || undefined,
    }
  } else {
    // Native: load token from SecureStore, profile from AsyncStorage
    token = await SecureStore.getItemAsync(TOKEN_KEY)
    const entries = await AsyncStorage.multiGet([EXPIRY_KEY, NAME_KEY, PICTURE_KEY])
    const map = Object.fromEntries(entries)
    if (!token) return null
    return {
      token,
      expiry: Number(map[EXPIRY_KEY] ?? 0),
      name: map[NAME_KEY] || undefined,
      picture: map[PICTURE_KEY] || undefined,
    }
  }
}

async function clearSession() {
  if (Platform.OS === 'web') {
    await AsyncStorage.multiRemove([TOKEN_KEY, EXPIRY_KEY, NAME_KEY, PICTURE_KEY])
  } else {
    await SecureStore.deleteItemAsync(TOKEN_KEY)
    await AsyncStorage.multiRemove([EXPIRY_KEY, NAME_KEY, PICTURE_KEY])
  }
}

const EXPIRY_SKEW_MS = 60_000

// ─── Welcome overlay ─────────────────────────────────────────────────────────

function WelcomeOverlay({ name, onDone }: { name: string; onDone: () => void }) {
  const scale = useRef(new Animated.Value(0.6)).current

  useEffect(() => {
    Animated.spring(scale, {
      toValue: 1,
      friction: 5,
      tension: 90,
      useNativeDriver: true,
    }).start()
    const t = setTimeout(onDone, 2400)
    return () => clearTimeout(t)
  }, [scale, onDone])

  return (
    <Modal transparent animationType="fade" visible>
      <View style={styles.welcomeOverlay}>
        <Animated.View style={[styles.welcomeCard, { transform: [{ scale }] }]}>
          <View style={styles.welcomeMark}>
            <Text style={{ fontSize: 36 }}>🎉</Text>
          </View>
          <Text style={styles.welcomeHi}>WELCOME</Text>
          <Text style={styles.welcomeName}>{name}</Text>
        </Animated.View>
      </View>
    </Modal>
  )
}

// ─── Google session ──────────────────────────────────────────────────────────

function GoogleSession({ children }: { children: ReactNode }) {
  const [hydrated, setHydrated] = useState(false)
  const [token, setToken] = useState<string | null>(null)
  const [name, setName] = useState<string | undefined>()
  const [picture, setPicture] = useState<string | undefined>()
  const [error, setError] = useState<string | undefined>()
  const [isLoading, setIsLoading] = useState(false)
  const [welcome, setWelcome] = useState<string | null>(null)

  // Refs so the token getter always sees current values without re-registering.
  const tokenRef = useRef<string | null>(null)
  const expiryRef = useRef(0)
  const refreshing = useRef<Promise<string | undefined> | null>(null)

  // Exchange a Google id_token with the backend and store the resulting session.
  const applyIdToken = useCallback(async (idToken: string) => {
    const session = await googleSignInWithToken(idToken)
    await persistSession(
      session.id_token,
      session.expires_at,
      session.user.first_name,
      session.picture ?? undefined,
    )
    tokenRef.current = session.id_token
    expiryRef.current = session.expires_at * 1000
    setToken(session.id_token)
    setName(session.user.first_name)
    setPicture(session.picture ?? undefined)
    return session
  }, [])

  const dropLocalSession = useCallback(async () => {
    tokenRef.current = null
    expiryRef.current = 0
    setToken(null)
    setName(undefined)
    setPicture(undefined)
    await clearSession()
  }, [])

  // Silently get a fresh id_token from Google and re-exchange it. Concurrent
  // callers share one in-flight refresh.
  const refresh = useCallback((): Promise<string | undefined> => {
    if (refreshing.current) return refreshing.current
    const p = (async () => {
      try {
        if (!GoogleSignin.hasPreviousSignIn()) {
          await dropLocalSession()
          return undefined
        }
        const res = await GoogleSignin.signInSilently()
        if (isNoSavedCredentialFoundResponse(res) || !res.data.idToken) {
          await dropLocalSession()
          return undefined
        }
        const session = await applyIdToken(res.data.idToken)
        return session.id_token
      } catch {
        // Transient failure (offline, backend down): keep the local session
        // as-is and let the caller's request fail normally.
        return undefined
      } finally {
        refreshing.current = null
      }
    })()
    refreshing.current = p
    return p
  }, [applyIdToken, dropLocalSession])

  // Restore persisted session on mount, refresh if stale, then wire the getter.
  useEffect(() => {
    let cancelled = false

    setAccessTokenGetter(async () => {
      if (tokenRef.current && Date.now() < expiryRef.current - EXPIRY_SKEW_MS) {
        return tokenRef.current
      }
      return refresh()
    })

    ;(async () => {
      const s = await loadSession()
      if (cancelled) return
      if (s) {
        tokenRef.current = s.token
        expiryRef.current = s.expiry
        setToken(s.token)
        setName(s.name)
        setPicture(s.picture)
        if (Date.now() >= s.expiry - EXPIRY_SKEW_MS) {
          await refresh()
        }
      }
      if (!cancelled) setHydrated(true)
    })()

    return () => {
      cancelled = true
      setAccessTokenGetter(async () => undefined)
    }
  }, [refresh])

  const login = useCallback(async () => {
    setIsLoading(true)
    setError(undefined)
    try {
      console.log('[Auth] Starting Google sign-in...')
      await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true })
      console.log('[Auth] Play Services available')
      const res = await GoogleSignin.signIn()
      console.log('[Auth] Google sign-in response:', res)
      if (!isSuccessResponse(res)) {
        console.log('[Auth] User cancelled or non-success response')
        return // user cancelled
      }
      const idToken = res.data.idToken
      if (!idToken) {
        console.error('[Auth] No idToken in response')
        setError('Google sign-in did not return a token. Please try again.')
        return
      }
      console.log('[Auth] Got idToken, calling backend...')
      const session = await applyIdToken(idToken)
      console.log('[Auth] Backend returned session:', session.user.email)
      setWelcome(session.user.first_name)
    } catch (err) {
      console.error('[Auth] Sign-in error:', err)
      if (err instanceof ApiError) {
        setError(
          err.status === 409
            ? 'An account already exists for that email. Please sign in with your original method.'
            : 'We could not verify your Google sign-in. Please try again.',
        )
      } else if (isErrorWithCode(err)) {
        switch (err.code) {
          case statusCodes.SIGN_IN_CANCELLED:
          case statusCodes.IN_PROGRESS:
            break
          case statusCodes.PLAY_SERVICES_NOT_AVAILABLE:
            setError('Google Play Services is unavailable or out of date on this device.')
            break
          default:
            setError('Google sign-in failed. Please try again.')
        }
      } else {
        setError('Google sign-in failed. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }, [applyIdToken])

  const logout = useCallback(async () => {
    setError(undefined)
    setWelcome(null)
    try {
      // Clears Google's cached account so the account picker shows next time.
      await GoogleSignin.signOut()
    } catch {
      // Not fatal: still clear the local session below.
    }
    await dropLocalSession()
  }, [dropLocalSession])

  const dismissWelcome = useCallback(() => setWelcome(null), [])

  const value = useMemo<Session>(
    () => ({
      isAuthenticated: Boolean(token),
      isLoading,
      ready: hydrated,
      name,
      picture,
      login: () => void login(),
      logout: () => void logout(),
      error,
    }),
    [token, isLoading, hydrated, name, picture, login, logout, error],
  )

  return (
    <SessionContext.Provider value={value}>
      {children}
      {welcome && <WelcomeOverlay name={welcome} onDone={dismissWelcome} />}
    </SessionContext.Provider>
  )
}

// ─── Unconfigured fallback ───────────────────────────────────────────────────

function UnconfiguredSession({ children }: { children: ReactNode }) {
  const value = useMemo<Session>(
    () => ({
      isAuthenticated: false,
      isLoading: false,
      ready: true,
      login: () => {},
      logout: () => {},
    }),
    [],
  )
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

// ─── Root provider ───────────────────────────────────────────────────────────

export function AppAuth({ children }: { children: ReactNode }) {
  if (!googleConfigured) {
    return <UnconfiguredSession>{children}</UnconfiguredSession>
  }
  return <GoogleSession>{children}</GoogleSession>
}

// ─── Welcome overlay styles ──────────────────────────────────────────────────

const styles = StyleSheet.create({
  welcomeOverlay: {
    flex: 1,
    backgroundColor: 'rgba(10,106,27,0.9)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  welcomeCard: {
    backgroundColor: C.cream,
    borderColor: C.gold,
    borderWidth: 3,
    borderRadius: 28,
    paddingVertical: 48,
    paddingHorizontal: 44,
    alignItems: 'center',
  },
  welcomeMark: {
    width: 74,
    height: 74,
    borderRadius: 37,
    backgroundColor: C.green,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  welcomeHi: {
    fontSize: 13,
    letterSpacing: 3,
    color: C.mut,
    fontWeight: '700',
  },
  welcomeName: {
    fontSize: 40,
    fontWeight: '800',
    color: C.green,
    marginTop: 4,
  },
})