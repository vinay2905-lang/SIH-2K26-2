import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, setCsrfToken } from '@/lib/api'

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockImplementation(
    async () =>
      new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  )
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => {
  vi.unstubAllGlobals()
  setCsrfToken(null)
})

describe('api client', () => {
  it('sends the CSRF token on mutations but not on reads', async () => {
    setCsrfToken('token-123')
    const fetchMock = mockFetch(200, { ok: true })
    await api.get('/students', { q: 'Rao', empty: '' })
    await api.post('/findings/1/actions', { action: 'comment' })

    const [getUrl, getInit] = fetchMock.mock.calls[0]
    expect(getUrl).toBe('/api/v1/students?q=Rao')
    expect(getInit.headers['X-CSRF-Token']).toBeUndefined()
    expect(getInit.credentials).toBe('same-origin')

    const [, postInit] = fetchMock.mock.calls[1]
    expect(postInit.headers['X-CSRF-Token']).toBe('token-123')
    expect(postInit.body).toBe(JSON.stringify({ action: 'comment' }))
  })

  it('turns error envelopes into ApiError with field errors', async () => {
    mockFetch(422, {
      error: {
        code: 'record_rejected',
        message: 'The record could not be saved',
        details: [
          { field: 'apaar_id', code: 'IDENTIFIER_FORMAT_INVALID', message: 'Bad format' },
          { field: 'date_of_birth', code: 'INVALID_DATE', message: 'Use YYYY-MM-DD' },
        ],
        request_id: 'req-1',
      },
    })
    const error = (await api.post('/students', {}).catch((e) => e)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(422)
    expect(error.code).toBe('record_rejected')
    expect(error.requestId).toBe('req-1')
    expect(error.fieldErrors).toEqual({ apaar_id: 'Bad format', date_of_birth: 'Use YYYY-MM-DD' })
  })

  it('reports network failures clearly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const error = (await api.get('/students').catch((e) => e)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('network_error')
  })
})
