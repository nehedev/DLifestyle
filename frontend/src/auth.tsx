import { GoogleOAuthProvider, useGoogleLogin } from '@react-oauth/google'
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
import { ApiError, getMe, googleSignIn, setAccessTokenGetter } from './api'
import type { MeResponse } from './api'

const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

export const googleConfigured = Boolean(clientId)

// ─── Session context ─────────────────────────────────────────────────────────

export interface Session {
  isAuthenticated: boolean
  isLoading: boolean
  name?: string      // first name, available after the backend verifies the token
  picture?: string   // Google profile photo URL
  login: () => void
  logout: () => void
  error?: string
}

const SessionContext = createContext<Session>({
  isAuthenticated: false,
  isLoading: false,
  login: () => alert('Sign-in is not configured. Set VITE_GOOGLE_CLIENT_ID to enable it.'),
  logout: () => undefined,
})
export const useSession = () => useContext(SessionContext)

// ─── Session storage ──────────────────────────────────────────────────────────
//
// The session only exists after the backend has verified the Google token and
// provisioned the user. Until then nothing is persisted, so a failed or
// interrupted sign-in leaves the visitor signed out.

const TOKEN_KEY = 'damis.google_token'
const EXPIRY_KEY = 'damis.google_expiry'
const NAME_KEY = 'damis.user_name'
const PICTURE_KEY = 'damis.user_picture'

function persistSession(idToken: string, expiresAt: number, name?: string, picture?: string) {
  localStorage.setItem(TOKEN_KEY, idToken)
  localStorage.setItem(EXPIRY_KEY, String(expiresAt * 1000))
  if (name) localStorage.setItem(NAME_KEY, name)
  else localStorage.removeItem(NAME_KEY)
  if (picture) localStorage.setItem(PICTURE_KEY, picture)
  else localStorage.removeItem(PICTURE_KEY)
}

function loadSession(): { token: string; name?: string; picture?: string } | null {
  const token = localStorage.getItem(TOKEN_KEY)
  const expiry = Number(localStorage.getItem(EXPIRY_KEY) ?? 0)
  if (!token || Date.now() > expiry - 60_000) return null
  return {
    token,
    name: localStorage.getItem(NAME_KEY) ?? undefined,
    picture: localStorage.getItem(PICTURE_KEY) ?? undefined,
  }
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(EXPIRY_KEY)
  localStorage.removeItem(NAME_KEY)
  localStorage.removeItem(PICTURE_KEY)
}

// ─── Welcome animation ────────────────────────────────────────────────────────

function WelcomeOverlay({ name, onDone }: { name: string; onDone: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDone, 2800)
    return () => clearTimeout(timer)
  }, [onDone])

  return (
    <div className="welcome-overlay" role="status" aria-live="polite">
      <div className="welcome-card">
        <span className="welcome-mark">
          <iconify-icon icon="lucide:party-popper" />
        </span>
        <p className="welcome-hi">Welcome</p>
        <p className="welcome-name">{name}</p>
      </div>
    </div>
  )
}

// ─── Inner session component (must be inside GoogleOAuthProvider) ─────────────

function GoogleSession({ children }: { children: ReactNode }) {
  const [initial] = useState(loadSession)
  const [token, setToken] = useState<string | null>(initial?.token ?? null)
  const [name, setName] = useState<string | undefined>(initial?.name)
  const [picture, setPicture] = useState<string | undefined>(initial?.picture)
  const [error, setError] = useState<string | undefined>()
  const [isLoading, setIsLoading] = useState(false)
  const [welcome, setWelcome] = useState<string | null>(null)
  const tokenRef = useRef(token)
  tokenRef.current = token

  // Wire the verified ID token into the API client
  useEffect(() => {
    setAccessTokenGetter(async () => tokenRef.current ?? undefined)
    return () => setAccessTokenGetter(async () => undefined)
  }, [])

  // The Google code is useless on its own: it must be verified by the backend
  // before a session can be created.
  const handleCode = useCallback(async (code: string) => {
    setIsLoading(true)
    setError(undefined)
    try {
      const session = await googleSignIn(code)
      persistSession(
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

  const googleLogin = useGoogleLogin({
    flow: 'auth-code',
    onSuccess: (response) => { void handleCode(response.code) },
    onError: () => {
      setError('Google sign-in failed. Please try again.')
      setIsLoading(false)
    },
    onNonOAuthError: () => {
      setIsLoading(false)
    },
  })

  const login = useCallback(() => {
    setIsLoading(true)
    setError(undefined)
    googleLogin()
  }, [googleLogin])

  const logout = useCallback(() => {
    clearSession()
    setToken(null)
    setName(undefined)
    setPicture(undefined)
    setError(undefined)
    setWelcome(null)
  }, [])

  const dismissWelcome = useCallback(() => setWelcome(null), [])

  const value = useMemo<Session>(
    () => ({ isAuthenticated: Boolean(token), isLoading, name, picture, login, logout, error }),
    [token, isLoading, name, picture, login, logout, error],
  )

  return (
    <SessionContext.Provider value={value}>
      {children}
      {welcome && <WelcomeOverlay name={welcome} onDone={dismissWelcome} />}
    </SessionContext.Provider>
  )
}

// ─── Unconfigured fallback ────────────────────────────────────────────────────

function UnconfiguredSession({ children }: { children: ReactNode }) {
  const value = useMemo<Session>(
    () => ({
      isAuthenticated: false,
      isLoading: false,
      login: () => alert('Sign-in is not configured. Set VITE_GOOGLE_CLIENT_ID to enable it.'),
      logout: () => undefined,
    }),
    [],
  )
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

// ─── Root auth provider ───────────────────────────────────────────────────────

export function AppAuth({ children }: { children: ReactNode }) {
  if (!googleConfigured || !clientId) {
    return <UnconfiguredSession>{children}</UnconfiguredSession>
  }
  return (
    <GoogleOAuthProvider clientId={clientId}>
      <GoogleSession>{children}</GoogleSession>
    </GoogleOAuthProvider>
  )
}

// ─── Admin hook ───────────────────────────────────────────────────────────────

export function useAdmin(): { isAdmin: boolean; me: MeResponse | null; loading: boolean } {
  const { isAuthenticated, isLoading } = useSession()
  const [me, setMe] = useState<MeResponse | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!isAuthenticated) { setMe(null); return }
    setLoading(true)
    getMe()
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setLoading(false))
  }, [isAuthenticated])

  return { isAdmin: me?.role === 'admin', me, loading: isLoading || loading }
}
