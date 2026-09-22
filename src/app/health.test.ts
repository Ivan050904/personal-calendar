import { describe, expect, it } from 'vitest'
import { projectHealth } from './health'

describe('project health', () => {
  it('declares the documented architectural layers', () => {
    expect(projectHealth.layers).toEqual([
      'presentation',
      'application',
      'domain',
      'infrastructure',
    ])
  })
})
