import {
  useEffect,
  useState,
  type PropsWithChildren,
} from 'react'
import { useAuth as useClerkAuth, useUser } from '@clerk/react'
import type { AuthSession, CurrentUser } from '../types/domain'
import {
  clearStoredSession,
  configureClerkRequests,
  getCurrentUser,
} from './api'
import { AuthContext } from './auth-context'

export function AuthProvider({ children }: PropsWithChildren) {
  const {
    getToken,
    isLoaded: isClerkLoaded,
    isSignedIn,
    signOut,
  } = useClerkAuth()
  const { user: clerkUser } = useUser()
  const clerkEmail =
    clerkUser?.primaryEmailAddress?.emailAddress ??
    clerkUser?.emailAddresses[0]?.emailAddress
  const clerkDisplayName =
    clerkUser?.fullName ??
    clerkUser?.username ??
    clerkEmail?.split('@')[0] ??
    '患者账号'
  const [session, setSession] = useState<AuthSession | null>(null)
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [isBootstrapping, setIsBootstrapping] = useState(true)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      if (!isClerkLoaded) {
        return
      }

      if (!isSignedIn) {
        clearStoredSession()
        configureClerkRequests(null)
        if (!cancelled) {
          setSession(null)
          setCurrentUser(null)
          setAuthError(null)
          setIsBootstrapping(false)
        }
        return
      }

      try {
        if (!clerkEmail) {
          throw new Error('Clerk 用户缺少邮箱，无法建立 TremorGuard 会话。')
        }

        clearStoredSession()
        configureClerkRequests({
          getToken,
          getUserProfile: () => ({
            email: clerkEmail,
            displayName: clerkDisplayName,
          }),
        })

        const user = await getCurrentUser()
        if (!cancelled) {
          setSession({
            accessToken: 'clerk-session',
            refreshToken: '',
            userId: user.id,
            accessTokenExpiresAt: '',
            refreshTokenExpiresAt: '',
          })
          setCurrentUser(user)
          setAuthError(null)
        }
      } catch (error) {
        clearStoredSession()
        configureClerkRequests(null)
        if (!cancelled) {
          setCurrentUser(null)
          setSession(null)
          setAuthError(error instanceof Error ? error.message : '无法建立 TremorGuard 工作台会话。')
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
  }, [
    clerkDisplayName,
    clerkEmail,
    getToken,
    isClerkLoaded,
    isSignedIn,
  ])

  async function logout() {
    clearStoredSession()
    configureClerkRequests(null)
    setSession(null)
    setCurrentUser(null)
    setAuthError(null)
    await signOut()
  }

  async function refreshCurrentUser() {
    if (!isSignedIn) {
      setSession(null)
      setCurrentUser(null)
      setAuthError(null)
      return null
    }

    const user = await getCurrentUser()
    setSession({
      accessToken: 'clerk-session',
      refreshToken: '',
      userId: user.id,
      accessTokenExpiresAt: '',
      refreshTokenExpiresAt: '',
    })
    setCurrentUser(user)
    setAuthError(null)
    return user
  }

  const value = {
    session,
    currentUser,
    isBootstrapping,
    authError,
    logout,
    refreshCurrentUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
