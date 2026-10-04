import {
  Auth0Provider,
  useAuth0,
  type User as Auth0User,
} from '@auth0/auth0-react'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from 'react'
import { setAccessTokenGetter } from './api'

const domain = import.meta.env.AUTH0_DOMAIN
const clientId = import.meta.env.AUTH0_CLIENT_ID
const audience = import.meta.env.AUTH0_AUDIENCE

export const auth0Configured = Boolean(domain && clientId)

export interface Session {
  isAuthenticated: boolean
  isLoading: boolean
  user?: Auth0User
  login: () => void
  logout: () => void
  error?: string
}

const SessionContext = createContext<Session>({
  isAuthenticated: false,
  isLoading: false,
  login: () => alert('Sign-in is not configured. Set VITE_AUTH0_* to enable it.'),
  logout: () => undefined,
})

export const useSession = () => useContext(SessionContext)

/** Keeps the API client's bearer-token source in sync with Auth0. */
function Auth0Session({ children }: { children: ReactNode }) {
  const {
    isAuthenticated,
    isLoading,
    user,
    loginWithRedirect,
    logout: auth0Logout,
    getAccessTokenSilently,
    error,
  } = useAuth0()

  useEffect(() => {
    setAccessTokenGetter(async () => {
      if (!isAuthenticated) return undefined
      try {
        return await getAccessTokenSilently()
      } catch {
        return undefined
      }
    })
    return () => setAccessTokenGetter(async () => undefined)
  }, [isAuthenticated, getAccessTokenSilently])

  const login = useCallback(
    () => loginWithRedirect({ appState: { returnTo: '/cart' } }),
    [loginWithRedirect],
  )
  const logout = useCallback(
    () => auth0Logout({ logoutParams: { returnTo: window.location.origin } }),
    [auth0Logout],
  )

  const value = useMemo<Session>(
    () => ({
      isAuthenticated,
      isLoading,
      user,
      login,
      logout,
      error: error?.message,
    }),
    [isAuthenticated, isLoading, user, login, logout, error],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

function UnconfiguredSession({ children }: { children: ReactNode }) {
  const value = useMemo<Session>(
    () => ({
      isAuthenticated: false,
      isLoading: false,
      login: () =>
        alert('Sign-in is not configured. Set VITE_AUTH0_* to enable it.'),
      logout: () => undefined,
    }),
    [],
  )
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function AppAuth({ children }: { children: ReactNode }) {
  if (!auth0Configured) return <UnconfiguredSession>{children}</UnconfiguredSession>
  return (
    <Auth0Provider
      domain={domain as string}
      clientId={clientId as string}
      cacheLocation="localstorage"
      useRefreshTokens
      authorizationParams={{
        audience,
        redirect_uri: `${window.location.origin}/`,
      }}
      onRedirectCallback={(appState) => {
        window.location.hash = appState?.returnTo ?? '/'
      }}
    >
      <Auth0Session>{children}</Auth0Session>
    </Auth0Provider>
  )
}

export type { Auth0User }
