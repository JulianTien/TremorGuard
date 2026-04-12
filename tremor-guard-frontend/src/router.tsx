import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AiDoctorPage } from './pages/ai-doctor-page'
import { LoginPage } from './pages/login-page'
import { MedicationPage } from './pages/medication-page'
import { OnboardingDeviceBindingPage } from './pages/onboarding-device-binding-page'
import { OnboardingProfilePage } from './pages/onboarding-profile-page'
import { OverviewPage } from './pages/overview-page'
import { ProfilePage } from './pages/profile-page'
import { RegisterPage } from './pages/register-page'
import { ReportsPage } from './pages/reports-page'
import { OnboardingGuard, ProtectedAppLayout, PublicOnlyLayout } from './router-guards'

export const router = createBrowserRouter([
  {
    element: <PublicOnlyLayout />,
    children: [
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
    ],
  },
  {
    path: '/onboarding/profile',
    element: (
      <OnboardingGuard requiredState="profile_required">
        <OnboardingProfilePage />
      </OnboardingGuard>
    ),
  },
  {
    path: '/onboarding/device-binding',
    element: (
      <OnboardingGuard requiredState="device_binding_required">
        <OnboardingDeviceBindingPage />
      </OnboardingGuard>
    ),
  },
  {
    path: '/',
    element: <ProtectedAppLayout />,
    children: [
      { index: true, element: <Navigate to="/overview" replace /> },
      { path: 'overview', element: <OverviewPage /> },
      { path: 'ai-doctor', element: <AiDoctorPage /> },
      { path: 'medication', element: <MedicationPage /> },
      { path: 'reports', element: <ReportsPage /> },
      { path: 'profile', element: <ProfilePage /> },
    ],
  },
  { path: '*', element: <Navigate to="/login" replace /> },
])
