import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from '@/features/auth/LoginPage'
import { AuthProvider } from '@/lib/auth'

const PUBLIC_META = {
  app_name: 'APAAR Student Data Platform',
  problem_statement: 'SIH26263',
  demo_mode: true,
  demo_accounts: [
    {
      email: 'aranya.operator@demo.example',
      role: 'institution_operator',
      institution: 'Aranya Institute of Technology (Demo)',
      description: '',
    },
  ],
  demo_password: 'Demo@12345',
}

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function renderLogin(fetchImpl: (url: string, init?: RequestInit) => Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn(fetchImpl))
  const router = createMemoryRouter(
    [
      { path: '/login', element: <LoginPage /> },
      { path: '/', element: <p>Signed in home</p> },
    ],
    { initialEntries: ['/login'] },
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('LoginPage', () => {
  it('fills credentials from a demo account and signs in', async () => {
    const calls: string[] = []
    renderLogin(async (url, init) => {
      calls.push(`${init?.method ?? 'GET'} ${url}`)
      if (url.startsWith('/api/v1/auth/me')) return json(401, { error: { code: 'unauthenticated', message: 'x' } })
      if (url.startsWith('/api/v1/meta/public')) return json(200, PUBLIC_META)
      if (url.startsWith('/api/v1/auth/login')) {
        expect(JSON.parse(String(init?.body))).toEqual({
          email: 'aranya.operator@demo.example',
          password: 'Demo@12345',
        })
        return json(200, {
          csrf_token: 'csrf',
          user: {
            id: '1',
            email: 'aranya.operator@demo.example',
            full_name: 'Operator',
            role: 'institution_operator',
            institution: null,
            permissions: [],
          },
        })
      }
      return json(404, {})
    })

    const user = userEvent.setup()
    await user.click(await screen.findByText('Institution data operator'))
    expect(screen.getByLabelText('Email')).toHaveValue('aranya.operator@demo.example')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Signed in home')).toBeInTheDocument()
    expect(calls).toContain('POST /api/v1/auth/login')
  })

  it('shows a generic error for wrong credentials', async () => {
    renderLogin(async (url) => {
      if (url.startsWith('/api/v1/auth/me')) return json(401, { error: { code: 'unauthenticated', message: 'x' } })
      if (url.startsWith('/api/v1/meta/public')) return json(200, { ...PUBLIC_META, demo_accounts: [] })
      return json(401, { error: { code: 'invalid_credentials', message: 'Email or password is incorrect' } })
    })
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Email'), 'someone@demo.example')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(screen.getByText('Email or password is incorrect')).toBeInTheDocument())
  })

  it('validates empty fields before calling the API', async () => {
    const fetchSpy = vi.fn(async (url: string) =>
      url.startsWith('/api/v1/meta/public')
        ? json(200, { ...PUBLIC_META, demo_accounts: [] })
        : json(401, { error: { code: 'unauthenticated', message: 'x' } }),
    )
    renderLogin(fetchSpy)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter your email address')).toBeInTheDocument()
    expect(fetchSpy.mock.calls.some(([url]) => String(url).includes('/auth/login'))).toBe(false)
  })
})
