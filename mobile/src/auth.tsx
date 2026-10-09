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
    offlineAccess: false,
  })
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const GOOGLE_SIGNIN_TIMEOUT_MS = 90_000
const BACKEND_TIMEOUT_MS = 60_000 // Increased from 20s to 60s for slower networks
const EXPIRY_SKEW_MS = 60_000

/** Rejects with an Error named 'TimeoutError' if `p` doesn't settle in time. */
function withTimeout<T>(p: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => {
      const e = new Error(`${label} timed out after ${Math.round(ms / 1000)}s`)
      e.name = 'TimeoutError'
      reject(e)
    }, ms)
    p.then(
      (v) => {
        clearTimeout(t)
        resolve(v)
      },
      (e) => {
        clearTimeout(t)
        reject(e)
      },
    )
  })
}

const CONFIG_HINT =
  'If you did not cancel, this is usually a configuration problem: the SHA-1 of the ' +
  'key that signed this build, the Android package name, or the Google Cloud project ' +
  'does not match your Android OAuth client.'

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

interface StoredSession {
  token: string
  expiry: number // ms since epoch
  name?: string
  picture?: string
}

async function persistSession(
  idToken: string,
  expiresAtSeconds: number,
  name?: string,
  picture?: string,
) {
  const profile: [string, string][] = [
    [EXPIRY_KEY, String(expiresAtSeconds * 1000)],
    [NAME_KEY, name ?? ''],
    [PICTURE_KEY, picture ?? ''],
  ]
  if (Platform.OS === 'web') {
    await AsyncStorage.multiSet([[TOKEN_KEY, idToken], ...profile])
  } else {
    await SecureStore.setItemAsync(TOKEN_KEY, idToken)
    await AsyncStorage.multiSet(profile)
  }
}

async function loadSession(): Promise<StoredSession | null> {
  const isWeb = Platform.OS === 'web'
  const keys = isWeb
    ? [TOKEN_KEY, EXPIRY_KEY, NAME_KEY, PICTURE_KEY]
    : [EXPIRY_KEY, NAME_KEY, PICTURE_KEY]

  const entries = await AsyncStorage.multiGet(keys)
  const map = Object.fromEntries(entries) as Record<string, string | null>
  const token = isWeb ? map[TOKEN_KEY] : await SecureStore.getItemAsync(TOKEN_KEY)
  if (!token) return null

  return {
    token,
    expiry: Number(map[EXPIRY_KEY] ?? 0),
    name: map[NAME_KEY] || undefined,
    picture: map[PICTURE_KEY] || undefined,
  }
}

async function clearSession() {
  const profileKeys = [EXPIRY_KEY, NAME_KEY, PICTURE_KEY]
  if (Platform.OS === 'web') {
    await AsyncStorage.multiRemove([TOKEN_KEY, ...profileKeys])
  } else {
    await SecureStore.deleteItemAsync(TOKEN_KEY)
    await AsyncStorage.multiRemove(profileKeys)
  }
}

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
  const loginInFlight = useRef(false)

  // Exchange a Google id_token with the backend and store the resulting session.
  const applyIdToken = useCallback(async (idToken: string) => {
    const session = await withTimeout(
      googleSignInWithToken(idToken),
      BACKEND_TIMEOUT_MS,
      'Backend sign-in',
    )
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
    try {
      await clearSession()
    } catch (e) {
      console.warn('[Auth] clearSession failed:', e)
    }
  }, [])

  // The actual refresh work. Never throws.
  const doRefresh = useCallback(async (): Promise<string | undefined> => {
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
    } catch (err) {
      // Google says the user must sign in again: the session is truly dead.
      if (isErrorWithCode(err) && err.code === statusCodes.SIGN_IN_REQUIRED) {
        await dropLocalSession()
        return undefined
      }
      // Transient failure (offline, backend down): keep the local session
      // as-is and let the caller's request fail normally.
      console.warn('[Auth] Silent refresh failed:', err)
      return undefined
    }
  }, [applyIdToken, dropLocalSession])

  // Concurrent callers share one in-flight refresh. The slot is cleared by a
  // .finally attached AFTER assignment, so it can never get stuck.
  const refresh = useCallback((): Promise<string | undefined> => {
    if (refreshing.current) return refreshing.current
    const p: Promise<string | undefined> = doRefresh().finally(() => {
      if (refreshing.current === p) refreshing.current = null
    })
    refreshing.current = p
    return p
  }, [doRefresh])

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
      try {
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
      } catch (e) {
        console.warn('[Auth] Failed to restore session:', e)
      } finally {
        // Always mark ready, otherwise the app can sit on a splash forever.
        if (!cancelled) setHydrated(true)
      }
    })()

    return () => {
      cancelled = true
      setAccessTokenGetter(async () => undefined)
    }
  }, [refresh])

  const login = useCallback(async () => {
    if (loginInFlight.current) return
    loginInFlight.current = true
    setIsLoading(true)
    setError(undefined)

    try {
      if (Platform.OS === 'android') {
        await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true })
      }

      // Timeout so a signIn() that never settles can't leave the UI stuck.
      const res = await withTimeout(
        GoogleSignin.signIn(),
        GOOGLE_SIGNIN_TIMEOUT_MS,
        'Google sign-in',
      )

      if (!isSuccessResponse(res)) {
        // Do NOT swallow this: config errors often surface as "cancelled".
        setError(`Google sign-in returned "${res.type}". ${CONFIG_HINT}`)
        return
      }

      const idToken = res.data.idToken
      if (!idToken) {
        setError('Google sign-in did not return a token. Please try again.')
        return
      }

      try {
        const session = await applyIdToken(idToken)
        setWelcome(session.user.first_name)
      } catch (backendErr) {
        // Clear Google's cached account so a retry starts from a clean state.
        try {
          await GoogleSignin.signOut()
        } catch {
          // best effort
        }
        throw backendErr
      }
    } catch (err) {
      console.error('[Auth] Sign-in error:', err)

      let message: string
      if (err instanceof Error && err.name === 'TimeoutError') {
        message =
          `${err.message}. If this was Google sign-in, fully close the app and try ` +
          'again. If it keeps happening, check your Android OAuth client setup.'
      } else if (err instanceof ApiError) {
        message = `API Error ${err.status}: ${JSON.stringify(err.detail)}`
      } else if (isErrorWithCode(err)) {
        const e = err as { code: string; message?: string }
        if (e.code === statusCodes.SIGN_IN_CANCELLED) {
          message = `Google sign-in was cancelled (code ${e.code}). ${CONFIG_HINT}`
        } else if (e.code === statusCodes.IN_PROGRESS) {
          message =
            'A previous sign-in attempt never completed. Fully close the app ' +
            '(swipe it away) and try again.'
        } else if (e.code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
          message = 'Google Play Services is missing or out of date on this device.'
        } else {
          message = `Google Error: ${e.code}${e.message ? ` - ${e.message}` : ''}`
        }
      } else if (err instanceof Error) {
        message = `Error: ${err.name} - ${err.message}`
      } else {
        message = `Unknown error: ${String(err)}`
      }

      setError(message)
    } finally {
      loginInFlight.current = false
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
      error: 'Google sign-in is not configured (EXPO_PUBLIC_GOOGLE_CLIENT_ID is missing in this build).',
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