import { describe, expect, it } from 'vitest'
import { createId, isUuid } from './ids'

describe('stable client IDs', () => {
  it('creates UUIDs', () => {
    expect(isUuid(createId())).toBe(true)
  })
})
