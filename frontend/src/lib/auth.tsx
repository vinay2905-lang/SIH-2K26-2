import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react'
import type { CurrentUser, SessionInfo } from '@/types/api'
import { ApiError, api, setCsrfToken } from './api'

interface AuthContextValue {
  user: CurrentUser | null
  loading: boolean
  can: (permission: string) => boolean
  login: (email: string, password: string) => Promise<CurrentUser>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export const SESSION_KEY = ['session'] as const

async function fetchSession(): Promise<SessionInfo | null> {
  try {
    const session = await api.get<SessionInfo>('/auth/me')
    setCsrfToken(session.csrf_token)
    return session
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      setCsrfToken(null)
      return null
    }
    throw error
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const session = useQuery({ queryKey: SESSION_KEY, queryFn: fetchSession, staleTime: 5 * 60_000 })

  const loginMutation = useMutation({
    mutationFn: (input: { email: string; password: string }) =>
      api.post<SessionInfo>('/auth/login', input),
    onSuccess: (data) => {
      setCsrfToken(data.csrf_token)
      queryClient.clear()
      queryClient.setQueryData(SESSION_KEY, data)
    },
  })

  const login = useCallback(
    async (email: string, password: string) => (await loginMutation.mutateAsync({ email, password })).user,
    [loginMutation],
  )

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      setCsrfToken(null)
      queryClient.clear()
      queryClient.setQueryData(SESSION_KEY, null)
    }
  }, [queryClient])

  const user = session.data?.user ?? null
  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading: session.isPending,
      can: (permission) => Boolean(user?.permissions.includes(permission)),
      login,
      logout,
    }),
    [user, session.isPending, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}

export const PERMISSIONS = {
  studentsRead: 'students.read',
  studentsWrite: 'students.write',
  uploadsCreate: 'uploads.create',
  uploadsRead: 'uploads.read',
  findingsRead: 'findings.read',
  findingsReview: 'findings.review',
  programmesRead: 'programmes.read',
  intakeManage: 'intake.manage',
  institutionsRead: 'institutions.read',
  dashboardInstitution: 'dashboard.institution',
  dashboardCentral: 'dashboard.central',
  reportsExport: 'reports.export',
  identityCheck: 'verification.identity_check',
  verifyLookup: 'verification.lookup',
  consentManage: 'consent.manage',
  recordsIssue: 'records.issue',
  auditRead: 'audit.read',
  settingsManage: 'settings.manage',
} as const
