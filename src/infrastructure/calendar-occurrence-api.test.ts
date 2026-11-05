import { expect, it, vi, afterEach } from 'vitest'
afterEach(() => vi.unstubAllGlobals())

it('keeps explicit null on projection transport and sends credential cookies', async () => {
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    void path; void init
    return { ok: true, status: 200, json: async () => ({ items: [{ due_date: null }], complete: true, next_cursor: null }) }
  })
  vi.stubGlobal('fetch', fetch)
  const { occurrencePage } = await import('./calendar-occurrence-api')
  const result = await occurrencePage('c', '2026-10-08', '2026-10-08', 'UTC')
  expect(result.items[0]?.due_date).toBeNull()
  expect(result.next_cursor).toBeNull()
  expect(fetch.mock.calls[0]?.[1]).toMatchObject({ credentials: 'include' })
})
