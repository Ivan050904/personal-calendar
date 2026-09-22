import { addDays, mondayOf } from './week-calendar'

export function monthGrid(month: string): string[] {
  const first = `${month}-01`
  const start = mondayOf(first)
  return Array.from({ length: 42 }, (_, index) => addDays(start, index))
}

export function addMonths(month: string, count: number): string {
  const date = new Date(`${month}-01T12:00:00Z`)
  date.setUTCMonth(date.getUTCMonth() + count)
  return date.toISOString().slice(0, 7)
}
