import {
  useEffect,
  useState,
  type PropsWithChildren,
} from 'react'
import type { AuthSession, CurrentUser } from '../types/domain'
import {
  AUTH_EVENT,
  clearStoredSession,
  getCurrentUser,
  loadStoredSession,
  loginUser,
  logoutUser,
  registerUser,
} from './api'
import { AuthContext } from './auth-context'

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<AuthSession | null>(() => loadStoredSession())
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [isBootstrapping, setIsBootstrapping] = useState(true)

  useEffect(() => {
    function syncSessionFromStorage() {
      setSession(loadStoredSession())
    }

    window.addEventListener(AUTH_EVENT, syncSessionFromStorage)
    return () => {
      window.removeEventListener(AUTH_EVENT, syncSessionFromStorage)
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      if (!session) {
        if (!cancelled) {
          setCurrentUser(null)
          setIsBootstrapping(false)
        }
        return
      }

      try {
        const user = await getCurrentUser()
        if (!cancelled) {
          setCurrentUser(user)
        }
      } catch {
        clearStoredSession()
        if (!cancelled) {
          setCurrentUser(null)
          setSession(null)
        }
      } finally {
        if (!cancelled) {
          setIsBootstrapping(false)
        }
      }
    }

    setIsBootstrapping(true)
    void bootstrap()

    return () => {
      cancelled = true
    }
  }, [session])

  async function login(email: string, password: string) {
    const result = await loginUser(email, password)
    setSession(result.session)
    setCurrentUser(result.currentUser)
    return result.currentUser
  }

  async function register(email: string, password: string, displayName: string) {
    const result = await registerUser(email, password, displayName)
    setSession(result.session)
    setCurrentUser(result.currentUser)
    return result.currentUser
  }

  async function logout() {
    await logoutUser(session?.refreshToken)
    setSession(null)
    setCurrentUser(null)
  }

  async function refreshCurrentUser() {
    const nextSession = loadStoredSession()
    if (!nextSession) {
      setSession(null)
      setCurrentUser(null)
      return null
    }

    const user = await getCurrentUser()
    setSession(nextSession)
    setCurrentUser(user)
    return user
  }

  const value = {
    session,
    currentUser,
    isBootstrapping,
    login,
    register,
    logout,
    refreshCurrentUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
