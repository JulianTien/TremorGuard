import type { ReactElement } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './lib/auth-context'
import { resolveAuthenticatedPath } from './lib/auth-context'
import { AppShell } from './components/layout/app-shell'

export function FullPageStatus({ message }: { message: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="rounded-2xl border border-slate-200 bg-white px-6 py-5 text-sm text-slate-500 shadow-sm">
        {message}
      </div>
    </div>
  )
}

export function PublicOnlyLayout() {
  const { currentUser, isBootstrapping, session } = useAuth()

  if (isBootstrapping) {
    return <FullPageStatus message="正在恢复登录状态..." />
  }

  if (session && currentUser) {
    return <Navigate to={resolveAuthenticatedPath(currentUser)} replace />
  }

  return <Outlet />
}

export function ProtectedAppLayout() {
  const { currentUser, isBootstrapping, session } = useAuth()

  if (isBootstrapping) {
    return <FullPageStatus message="正在加载患者工作台..." />
  }

  if (!session || !currentUser) {
    return <Navigate to="/login" replace />
  }

  if (currentUser.onboardingState !== 'active') {
    return <Navigate to={resolveAuthenticatedPath(currentUser)} replace />
  }

  return <AppShell />
}

export function OnboardingGuard({
  requiredState,
  children,
}: {
  requiredState: 'profile_required' | 'device_binding_required'
  children: ReactElement
}) {
  const { currentUser, isBootstrapping, session } = useAuth()

  if (isBootstrapping) {
    return <FullPageStatus message="正在准备引导流程..." />
  }

  if (!session || !currentUser) {
    return <Navigate to="/login" replace />
  }

  if (currentUser.onboardingState === 'active') {
    return <Navigate to="/overview" replace />
  }

  if (
    requiredState === 'profile_required' &&
    currentUser.onboardingState === 'device_binding_required'
  ) {
    return children
  }

  if (currentUser.onboardingState !== requiredState) {
    return <Navigate to={resolveAuthenticatedPath(currentUser)} replace />
  }

  return children
}
