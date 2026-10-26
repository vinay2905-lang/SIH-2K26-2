import clsx from 'clsx'
import {
  BadgeCheck,
  FileChartColumn,
  FlaskConical,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  ShieldAlert,
  SlidersHorizontal,
  Upload,
  Users,
  Building2,
  X,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { PERMISSIONS, useAuth } from '@/lib/auth'
import { roleLabel } from '@/lib/format'

interface NavItem {
  to: string
  label: string
  icon: ReactNode
  permission?: string
  anyOf?: string[]
}

const NAV: { heading: string; items: NavItem[] }[] = [
  {
    heading: 'Overview',
    items: [
      {
        to: '/dashboard',
        label: 'Dashboard',
        icon: <LayoutDashboard className="size-4" />,
        anyOf: [PERMISSIONS.dashboardInstitution, PERMISSIONS.dashboardCentral],
      },
    ],
  },
  {
    heading: 'Records',
    items: [
      { to: '/students', label: 'Students', icon: <Users className="size-4" />, permission: PERMISSIONS.studentsRead },
      { to: '/uploads', label: 'Uploads', icon: <Upload className="size-4" />, permission: PERMISSIONS.uploadsRead },
    ],
  },
  {
    heading: 'Compliance',
    items: [
      {
        to: '/exceptions',
        label: 'Exception queue',
        icon: <ShieldAlert className="size-4" />,
        permission: PERMISSIONS.findingsRead,
      },
      {
        to: '/programmes',
        label: 'Programmes & intake',
        icon: <Building2 className="size-4" />,
        permission: PERMISSIONS.programmesRead,
      },
      {
        to: '/reports',
        label: 'Reports',
        icon: <FileChartColumn className="size-4" />,
        permission: PERMISSIONS.reportsExport,
      },
    ],
  },
  {
    heading: 'Verification',
    items: [
      {
        to: '/verification',
        label: 'Verify a record',
        icon: <BadgeCheck className="size-4" />,
        permission: PERMISSIONS.verifyLookup,
      },
    ],
  },
  {
    heading: 'Administration',
    items: [
      { to: '/audit', label: 'Audit trail', icon: <ScrollText className="size-4" />, permission: PERMISSIONS.auditRead },
      {
        to: '/settings',
        label: 'Validation policy',
        icon: <SlidersHorizontal className="size-4" />,
        permission: PERMISSIONS.settingsManage,
      },
    ],
  },
]

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, can, logout } = useAuth()
  const navigate = useNavigate()
  const visible = (item: NavItem) =>
    item.permission ? can(item.permission) : item.anyOf ? item.anyOf.some(can) : true

  return (
    <div className="flex h-full flex-col bg-brand-900 text-slate-200">
      <div className="flex items-center gap-3 border-b border-white/10 px-5 py-5">
        <div className="flex size-9 items-center justify-center rounded-lg bg-white/10 text-white ring-1 ring-white/15">
          <GraduationCap className="size-5" aria-hidden />
        </div>
        <div className="leading-tight">
          <p className="text-[15px] font-semibold text-white">APAAR Data Platform</p>
          <p className="text-[11px] tracking-wide text-slate-400">SIH26263 · Prototype</p>
        </div>
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4" aria-label="Main">
        {NAV.map((group) => {
          const items = group.items.filter(visible)
          if (!items.length) return null
          return (
            <div key={group.heading}>
              <p className="px-3 pb-1.5 text-[10.5px] font-semibold tracking-[0.08em] text-slate-500 uppercase">
                {group.heading}
              </p>
              <ul className="space-y-0.5">
                {items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        clsx(
                          'flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] font-medium transition-colors',
                          isActive
                            ? 'bg-white/10 text-white shadow-[inset_2px_0_0_0_var(--color-brand-500)]'
                            : 'text-slate-300 hover:bg-white/5 hover:text-white',
                        )
                      }
                    >
                      <span aria-hidden className="opacity-90">
                        {item.icon}
                      </span>
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </nav>

      <div className="border-t border-white/10 p-3">
        <div className="rounded-lg bg-white/5 px-3 py-2.5">
          <p className="truncate text-[13px] font-medium text-white">{user?.full_name}</p>
          <p className="truncate text-[11.5px] text-slate-400">{roleLabel(user?.role)}</p>
          {user?.institution && (
            <p className="mt-0.5 truncate text-[11.5px] text-slate-400" title={user.institution.name}>
              {user.institution.code}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={async () => {
            await logout()
            navigate('/login', { replace: true })
          }}
          className="mt-2 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium text-slate-300 hover:bg-white/5 hover:text-white"
        >
          <LogOut className="size-4" aria-hidden />
          Sign out
        </button>
      </div>
    </div>
  )
}

export function DemoBanner() {
  return (
    <div className="no-print flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-[12.5px] text-amber-900 sm:px-8">
      <FlaskConical className="size-3.5 shrink-0" aria-hidden />
      <p>
        <span className="font-semibold">Demo environment.</span> Synthetic data only — not real student
        information. Identity verification is simulated.
      </p>
    </div>
  )
}

export function AppLayout() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  useEffect(() => setOpen(false), [location.pathname])

  return (
    <div className="min-h-screen lg:pl-64 print:pl-0">
      <aside className="no-print fixed inset-y-0 left-0 hidden w-64 lg:block">
        <Sidebar />
      </aside>

      {open && (
        <div className="no-print fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} aria-hidden />
          <aside className="absolute inset-y-0 left-0 w-72 shadow-xl">
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="absolute top-4 left-[19rem] rounded-md bg-white/90 p-1.5 text-ink"
            aria-label="Close menu"
          >
            <X className="size-5" />
          </button>
        </div>
      )}

      <div className="no-print sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-white/95 px-4 py-3 backdrop-blur lg:hidden">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-md p-1.5 text-ink hover:bg-slate-100"
          aria-label="Open menu"
        >
          <Menu className="size-5" />
        </button>
        <span className="text-sm font-semibold">APAAR Data Platform</span>
      </div>

      <DemoBanner />
      <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-8 sm:py-8 print:max-w-none print:p-0">
        <Outlet />
      </main>
    </div>
  )
}
