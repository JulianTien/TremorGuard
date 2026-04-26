import { lazy, Suspense, type ReactNode } from 'react'

const AiDoctorPage = lazy(() =>
  import('./pages/ai-doctor-page').then((module) => ({ default: module.AiDoctorPage })),
)
const LoginPage = lazy(() =>
  import('./pages/login-page').then((module) => ({ default: module.LoginPage })),
)
const MedicalRecordArchivePage = lazy(() =>
  import('./pages/medical-record-archive-page').then((module) => ({
    default: module.MedicalRecordArchivePage,
  })),
)
const MedicalRecordReportPage = lazy(() =>
  import('./pages/medical-record-report-page').then((module) => ({
    default: module.MedicalRecordReportPage,
  })),
)
const MedicalRecordsPage = lazy(() =>
  import('./pages/medical-records-page').then((module) => ({ default: module.MedicalRecordsPage })),
)
const MedicationPage = lazy(() =>
  import('./pages/medication-page').then((module) => ({ default: module.MedicationPage })),
)
const OnboardingDeviceBindingPage = lazy(() =>
  import('./pages/onboarding-device-binding-page').then((module) => ({
    default: module.OnboardingDeviceBindingPage,
  })),
)
const OnboardingProfilePage = lazy(() =>
  import('./pages/onboarding-profile-page').then((module) => ({
    default: module.OnboardingProfilePage,
  })),
)
const OverviewPage = lazy(() =>
  import('./pages/overview-page').then((module) => ({ default: module.OverviewPage })),
)
const ProfilePage = lazy(() =>
  import('./pages/profile-page').then((module) => ({ default: module.ProfilePage })),
)
const RehabGuidancePage = lazy(() =>
  import('./pages/rehab-guidance-page').then((module) => ({ default: module.RehabGuidancePage })),
)
const RegisterPage = lazy(() =>
  import('./pages/register-page').then((module) => ({ default: module.RegisterPage })),
)
const ReportsPage = lazy(() =>
  import('./pages/reports-page').then((module) => ({ default: module.ReportsPage })),
)

function PageLoader() {
  return (
    <div className="flex min-h-[320px] items-center justify-center text-sm text-slate-500">
      页面加载中...
    </div>
  )
}

function LazyPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageLoader />}>{children}</Suspense>
}

export function AiDoctorRoute() {
  return (
    <LazyPage>
      <AiDoctorPage />
    </LazyPage>
  )
}

export function LoginRoute() {
  return (
    <LazyPage>
      <LoginPage />
    </LazyPage>
  )
}

export function MedicalRecordArchiveRoute() {
  return (
    <LazyPage>
      <MedicalRecordArchivePage />
    </LazyPage>
  )
}

export function MedicalRecordReportRoute() {
  return (
    <LazyPage>
      <MedicalRecordReportPage />
    </LazyPage>
  )
}

export function MedicalRecordsRoute() {
  return (
    <LazyPage>
      <MedicalRecordsPage />
    </LazyPage>
  )
}

export function MedicationRoute() {
  return (
    <LazyPage>
      <MedicationPage />
    </LazyPage>
  )
}

export function OnboardingDeviceBindingRoute() {
  return (
    <LazyPage>
      <OnboardingDeviceBindingPage />
    </LazyPage>
  )
}

export function OnboardingProfileRoute() {
  return (
    <LazyPage>
      <OnboardingProfilePage />
    </LazyPage>
  )
}

export function OverviewRoute() {
  return (
    <LazyPage>
      <OverviewPage />
    </LazyPage>
  )
}

export function ProfileRoute() {
  return (
    <LazyPage>
      <ProfilePage />
    </LazyPage>
  )
}

export function RehabGuidanceRoute() {
  return (
    <LazyPage>
      <RehabGuidancePage />
    </LazyPage>
  )
}

export function RegisterRoute() {
  return (
    <LazyPage>
      <RegisterPage />
    </LazyPage>
  )
}

export function ReportsRoute() {
  return (
    <LazyPage>
      <ReportsPage />
    </LazyPage>
  )
}
