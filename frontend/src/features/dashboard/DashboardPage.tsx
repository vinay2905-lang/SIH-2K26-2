import { Navigate } from 'react-router'
import { PERMISSIONS, useAuth } from '@/lib/auth'
import { CentralDashboard } from './CentralDashboard'
import { InstitutionDashboard } from './InstitutionDashboard'

export function DashboardPage() {
  const { can } = useAuth()
  if (can(PERMISSIONS.dashboardInstitution)) return <InstitutionDashboard />
  if (can(PERMISSIONS.dashboardCentral)) return <CentralDashboard />
  return <Navigate to="/" replace />
}
