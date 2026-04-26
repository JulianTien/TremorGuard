import { createBrowserRouter, Navigate } from 'react-router-dom'
import {
  AiDoctorRoute,
  LoginRoute,
  MedicalRecordArchiveRoute,
  MedicalRecordReportRoute,
  MedicalRecordsRoute,
  MedicationRoute,
  OnboardingDeviceBindingRoute,
  OnboardingProfileRoute,
  OverviewRoute,
  ProfileRoute,
  RehabGuidanceRoute,
  RegisterRoute,
  ReportsRoute,
} from './route-pages'
import { OnboardingGuard, ProtectedAppLayout, PublicOnlyLayout } from './router-guards'

export const router = createBrowserRouter([
  {
    element: <PublicOnlyLayout />,
    children: [
      { path: '/login', element: <LoginRoute /> },
      { path: '/register', element: <RegisterRoute /> },
    ],
  },
  {
    path: '/onboarding/profile',
    element: (
      <OnboardingGuard requiredState="profile_required">
        <OnboardingProfileRoute />
      </OnboardingGuard>
    ),
  },
  {
    path: '/onboarding/device-binding',
    element: (
      <OnboardingGuard requiredState="device_binding_required">
        <OnboardingDeviceBindingRoute />
      </OnboardingGuard>
    ),
  },
  {
    path: '/',
    element: <ProtectedAppLayout />,
    children: [
      { index: true, element: <Navigate to="/overview" replace /> },
      { path: 'overview', element: <OverviewRoute /> },
      { path: 'ai-doctor', element: <AiDoctorRoute /> },
      { path: 'medication', element: <MedicationRoute /> },
      { path: 'rehab-guidance', element: <RehabGuidanceRoute /> },
      { path: 'records', element: <MedicalRecordsRoute /> },
      { path: 'records/reports/:reportId', element: <MedicalRecordReportRoute /> },
      { path: 'records/:archiveId', element: <MedicalRecordArchiveRoute /> },
      { path: 'reports', element: <ReportsRoute /> },
      { path: 'reports/:reportId', element: <MedicalRecordReportRoute /> },
      { path: 'profile', element: <ProfileRoute /> },
    ],
  },
  { path: '*', element: <Navigate to="/login" replace /> },
])
