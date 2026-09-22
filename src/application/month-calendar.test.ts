import { describe, expect, it } from 'vitest'
import { addMonths, monthGrid } from './month-calendar'
describe('month calendar', () => { it('builds a Monday-first grid and navigates months', () => { expect(monthGrid('2026-09')[0]).toBe('2026-08-31'); expect(monthGrid('2026-09')).toHaveLength(42); expect(addMonths('2026-12', 1)).toBe('2027-01') }) })
