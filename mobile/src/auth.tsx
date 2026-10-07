import AsyncStorage from '@react-native-async-storage/async-storage'
import * as AuthSession from 'expo-auth-session'
import * as Crypto from 'expo-crypto'
import * as WebBrowser from 'expo-web-browser'
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
  StyleSheet,
  Text,
  View,
} from 'react-native'
import { ApiError, googleSignInWithToken, setAccessTokenGetter } from './api'
import { C } from './theme'

WebBrowser.maybeCompleteAuthSession()

const CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID as string | undefined
export const googleConfigured = Boolean(CLIENT_ID)

// Implicit flow: the id_token is returned directly in the redirect fragment.
// No redirect URI needs to be registered in Google Cloud Console for this flow —
// Google only validates that the client ID is correct.
export const GOOGLE_REDIRECT_URI = AuthSession.makeRedirectUri({
  scheme: 'damis',
  path: 'oauth',
})

const discovery = {
  authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
  tokenEndpoint: 'https://oauth2.googleapis.com/token',
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

const TOKEN_KEY = 'damis.google_token'
const EXPIRY_KEY = 'damis.google_expiry'
const NAME_KEY = 'damis.user_name'
const PICTURE_KEY = 'damis.user_picture'

async function persistSession(
  idToken: string,
  expiresAt: number,
  name?: string,
  picture?: string,
) {
  await AsyncStorage.multiSet([
    [TOKEN_KEY, idToken],
    [EXPIRY_KEY, String(expiresAt * 1000)],
    [NAME_KEY, name ?? ''],
    [PICTURE_KEY, picture ?? ''],
  ])
}

async function loadSession() {
  const entries = await AsyncStorage.multiGet([
    TOKEN_KEY,
    EXPIRY_KEY,
    NAME_KEY,
    PICTURE_KEY,
  ])
  const map = Object.fromEntries(entries)
  const token = map[TOKEN_KEY]
  const expiry = Number(map[EXPIRY_KEY] ?? 0)
  if (!token || Date.now() > expiry - 60_000) return null
  return {
    token,
    name: map[NAME_KEY] || undefined,
    picture: map[PICTURE_KEY] || undefined,
  }
}

async function clearSession() {
  await AsyncStorage.multiRemove([TOKEN_KEY, EXPIRY_KEY, NAME_KEY, PICTURE_KEY])
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
  const [ready, setReady] = useState(false)
  const [welcome, setWelcome] = useState<string | null>(null)
  const tokenRef = useRef(token)
  tokenRef.current = token

  // Restore persisted session on mount, then wire the token getter.
  // ready is only set true after hydration so ready && hydrated is never split.
  useEffect(() => {
    loadSession().then((s) => {
      if (s) {
        setToken(s.token)
        setName(s.name)
        setPicture(s.picture)
      }
      setHydrated(true)
      setAccessTokenGetter(async () => tokenRef.current ?? undefined)
      setReady(true)
    })
    return () => {
      setAccessTokenGetter(async () => undefined)
      setReady(false)
    }
  }, [])

  // Generate a fresh nonce for every auth request.
  // Google requires a nonce with id_token requests; we send the SHA-256 hash
  // so the raw value is never transmitted. The backend only verifies the token
  // signature — nonce checking happens client-side if needed.
  const [nonce, setNonce] = useState<string>('')
  const [nonceHash, setNonceHash] = useState<string>('')

  useEffect(() => {
    Crypto.getRandomBytesAsync(16).then((bytes) => {
      const raw = Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('')
      setNonce(raw)
      return Crypto.digestStringAsync(
        Crypto.CryptoDigestAlgorithm.SHA256,
        raw,
        { encoding: Crypto.CryptoEncoding.HEX },
      )
    }).then(setNonceHash)
  }, [])

  // Implicit flow: responseType = IdToken means Google returns the id_token
  // directly in the redirect fragment. No redirect URI registration required
  // in Google Cloud Console — only the client ID is validated.
  const [, response, promptAsync] = AuthSession.useAuthRequest(
    {
      clientId: CLIENT_ID ?? '',
      scopes: ['openid', 'profile', 'email'],
      responseType: AuthSession.ResponseType.IdToken,
      redirectUri: GOOGLE_REDIRECT_URI,
      usePKCE: false,
      extraParams: {
        nonce: nonceHash,
        prompt: 'consent',
      },
    },
    discovery,
  )

  const handleIdToken = useCallback(async (idToken: string) => {
    setIsLoading(true)
    setError(undefined)
    try {
      const session = await googleSignInWithToken(idToken)
      await persistSession(
        session.id_token,
        session.expires_at,
        session.user.first_name,
        session.picture ?? undefined,
      )
      setName(session.user.first_name)
      setPicture(session.picture ?? undefined)
      setToken(session.id_token)
      setWelcome(session.user.first_name)
    } catch (err) {
      const message =
        err instanceof ApiError && err.status === 409
          ? 'An account already exists for that email. Please sign in with your original method.'
          : 'We could not verify your Google sign-in. Please try again.'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!response) return
    if (response.type === 'success') {
      const idToken = response.params.id_token
      if (idToken) {
        void handleIdToken(idToken)
      } else {
        setError('Google sign-in did not return a token. Please try again.')
        setIsLoading(false)
      }
    } else if (response.type === 'error') {
      setError('Google sign-in failed. Please try again.')
      setIsLoading(false)
    } else if (response.type === 'cancel' || response.type === 'dismiss') {
      setIsLoading(false)
    }
  }, [response, handleIdToken])

  const login = useCallback(() => {
    if (!nonceHash) return // nonce not ready yet
    setIsLoading(true)
    setError(undefined)
    void promptAsync()
  }, [promptAsync, nonceHash])

  const logout = useCallback(() => {
    void clearSession()
    setToken(null)
    setName(undefined)
    setPicture(undefined)
    setError(undefined)
    setWelcome(null)
    // Regenerate nonce so the next login gets a fresh one
    Crypto.getRandomBytesAsync(16).then((bytes) => {
      const raw = Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('')
      setNonce(raw)
      return Crypto.digestStringAsync(
        Crypto.CryptoDigestAlgorithm.SHA256,
        raw,
        { encoding: Crypto.CryptoEncoding.HEX },
      )
    }).then(setNonceHash)
  }, [])

  const dismissWelcome = useCallback(() => setWelcome(null), [])

  // Suppress nonce from renders — it's only used in the auth request
  void nonce

  const value = useMemo<Session>(
    () => ({
      isAuthenticated: Boolean(token),
      isLoading,
      ready: ready && hydrated,
      name,
      picture,
      login,
      logout,
      error,
    }),
    [token, isLoading, ready, hydrated, name, picture, login, logout, error],
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
  if (!googleConfigured || !CLIENT_ID) {
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
