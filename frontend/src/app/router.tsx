import { Compass } from 'lucide-react'
import type { ReactNode } from 'react'
import { createBrowserRouter } from 'react-router'
import { ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/Feedback'
import { AuditPage } from '@/features/audit/AuditPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { ExceptionDetailPage } from '@/features/exceptions/ExceptionDetailPage'
import { ExceptionsPage } from '@/features/exceptions/ExceptionsPage'
import { ProgrammesPage } from '@/features/programmes/ProgrammesPage'
import { ReportsPage } from '@/features/reports/ReportsPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { CertificatePage } from '@/features/students/CertificatePage'
import { StudentDetailPage } from '@/features/students/StudentDetailPage'
import { StudentFormPage } from '@/features/students/StudentFormPage'
import { StudentsPage } from '@/features/students/StudentsPage'
import { UploadDetailPage } from '@/features/uploads/UploadDetailPage'
import { UploadsPage } from '@/features/uploads/UploadsPage'
import { VerificationPage } from '@/features/verification/VerificationPage'
import { PERMISSIONS as P } from '@/lib/auth'
import { AppLayout } from './AppLayout'
import { HomeRedirect, RequireAuth, RequirePermission } from './guards'

function NotFound() {
  return (
    <Card>
      <EmptyState
        icon={<Compass className="size-5" aria-hidden />}
        title="Page not found"
        description="The page you were looking for does not exist or has moved."
        action={<ButtonLink to="/">Go to start page</ButtonLink>}
      />
    </Card>
  )
}

const guard = (permission: string, element: ReactNode) => (
  <RequirePermission permission={permission}>{element}</RequirePermission>
)

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <HomeRedirect /> },
          { path: 'dashboard', element: <DashboardPage /> },
          { path: 'students', element: guard(P.studentsRead, <StudentsPage />) },
          { path: 'students/new', element: guard(P.studentsWrite, <StudentFormPage />) },
          { path: 'students/:id', element: guard(P.studentsRead, <StudentDetailPage />) },
          { path: 'admissions/:id/certificate', element: guard(P.recordsIssue, <CertificatePage />) },
          { path: 'uploads', element: guard(P.uploadsRead, <UploadsPage />) },
          { path: 'uploads/:id', element: guard(P.uploadsRead, <UploadDetailPage />) },
          { path: 'exceptions', element: guard(P.findingsRead, <ExceptionsPage />) },
          { path: 'exceptions/:id', element: guard(P.findingsRead, <ExceptionDetailPage />) },
          { path: 'programmes', element: guard(P.programmesRead, <ProgrammesPage />) },
          { path: 'reports', element: guard(P.reportsExport, <ReportsPage />) },
          { path: 'verification', element: guard(P.verifyLookup, <VerificationPage />) },
          { path: 'audit', element: guard(P.auditRead, <AuditPage />) },
          { path: 'settings', element: guard(P.settingsManage, <SettingsPage />) },
          { path: '*', element: <NotFound /> },
        ],
      },
    ],
  },
])
