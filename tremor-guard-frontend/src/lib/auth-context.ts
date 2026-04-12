import { createContext, useContext } from 'react'
import type { AuthSession, CurrentUser } from '../types/domain'

export interface AuthContextValue {
  session: AuthSession | null
  currentUser: CurrentUser | null
  isBootstrapping: boolean
  login: (email: string, password: string) => Promise<CurrentUser>
  register: (email: string, password: string, displayName: string) => Promise<CurrentUser>
  logout: () => Promise<void>
  refreshCurrentUser: () => Promise<CurrentUser | null>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function resolveAuthenticatedPath(user: CurrentUser) {
  if (user.onboardingState === 'profile_required') {
    return '/onboarding/profile'
  }

  if (user.onboardingState === 'device_binding_required') {
    return '/onboarding/device-binding'
  }

  return '/overview'
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
