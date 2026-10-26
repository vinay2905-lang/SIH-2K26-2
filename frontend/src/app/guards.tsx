import { ShieldX } from 'lucide-react'
import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'
import { ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState, LoadingBlock } from '@/components/ui/Feedback'
import { PERMISSIONS, useAuth } from '@/lib/auth'

export function RequireAuth() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingBlock label="Checking your session…" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <Outlet />
}

/** Client-side guard for a nicer experience. The server enforces every permission regardless. */
export function RequirePermission({ permission, children }: { permission: string; children: ReactNode }) {
  const { can } = useAuth()
  if (!can(permission)) {
    return (
      <Card>
        <EmptyState
          icon={<ShieldX className="size-5" aria-hidden />}
          title="You don’t have access to this page"
          description="Your role does not include this permission. Contact your administrator if you need access."
          action={<ButtonLink to="/">Go to start page</ButtonLink>}
        />
      </Card>
    )
  }
  return <>{children}</>
}

/** Each role lands on the page it uses most. */
export function HomeRedirect() {
  const { can } = useAuth()
  if (can(PERMISSIONS.dashboardInstitution) || can(PERMISSIONS.dashboardCentral)) {
    return <Navigate to="/dashboard" replace />
  }
  if (can(PERMISSIONS.verifyLookup)) return <Navigate to="/verification" replace />
  if (can(PERMISSIONS.settingsManage)) return <Navigate to="/settings" replace />
  return <Navigate to="/programmes" replace />
}
