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
import { getMe, setAccessTokenGetter } from './api'
import type { MeResponse } from './api'

const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

export const googleConfigured = Boolean(clientId)

// ─── Session context ─────────────────────────────────────────────────────────

export interface Session {
  isAuthenticated: boolean
  isLoading: boolean
  name?: string           // first name from /me, available after sign-in
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

// ─── Token storage ────────────────────────────────────────────────────────────

const TOKEN_KEY = 'damis.google_token'
const EXPIRY_KEY = 'damis.google_expiry'

function storeToken(token: string, expiresIn: number) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(EXPIRY_KEY, String(Date.now() + expiresIn * 1000))
}

function loadToken(): string | null {
  const token = localStorage.getItem(TOKEN_KEY)
  const expiry = Number(localStorage.getItem(EXPIRY_KEY) ?? 0)
  if (!token || Date.now() > expiry - 60_000) return null
  return token
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(EXPIRY_KEY)
}

// ─── Inner session component (must be inside GoogleOAuthProvider) ─────────────

function GoogleSession({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(loadToken)
  const [name, setName] = useState<string | undefined>()
  const [error, setError] = useState<string | undefined>()
  const [isLoading, setIsLoading] = useState(false)
  const tokenRef = useRef(token)
  tokenRef.current = token

  // Wire the access token into the API client
  useEffect(() => {
    setAccessTokenGetter(async () => tokenRef.current ?? undefined)
    return () => setAccessTokenGetter(async () => undefined)
  }, [])

  // Fetch first name once we have a token
  useEffect(() => {
    if (!token) { setName(undefined); return }
    getMe()
      .then(me => setName(me.first_name))
      .catch(() => undefined)
  }, [token])

  const handleSuccess = useCallback((response: { access_token: string; expires_in: number }) => {
    storeToken(response.access_token, response.expires_in)
    setToken(response.access_token)
    setError(undefined)
    setIsLoading(false)
  }, [])

  const googleLogin = useGoogleLogin({
    onSuccess: handleSuccess,
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
    clearToken()
    setToken(null)
    setName(undefined)
    setError(undefined)
  }, [])

  const value = useMemo<Session>(
    () => ({ isAuthenticated: Boolean(token), isLoading, name, login, logout, error }),
    [token, isLoading, name, login, logout, error],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
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
