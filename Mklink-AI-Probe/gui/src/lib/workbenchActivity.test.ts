import { describe, expect, it, vi } from 'vitest'
import { createWorkbenchActivity, emptyContent, validateContent } from './workbenchActivity'

describe('window operation history and information', () => {
  it('restores display data without executing anything and isolates changed device generations', () => {
    const saved = new Map<string, string>()
    const storage = { getItem: (key: string) => saved.get(key) || null, setItem: (key: string, value: string) => { saved.set(key, value) } }
    const first = createWorkbenchActivity(storage)
    first.bind('session:probe:1')
    first.append({ id: 'answer_one', kind: 'answer', title: 'Result', text: 'The capture contains four rejected requests.', source: 'Agent', status: 'replied' })
    first.setContent('chart_one', { ...emptyContent(), kind: 'bar', points: [{ label: 'Rejected', value: 4 }] })
    const next = createWorkbenchActivity(storage)
    next.bind('session:probe:1')
    expect(next.latestAnswer()?.text).toContain('four')
    expect(next.state.documents.chart_one?.points[0]?.value).toBe(4)
    next.bind('session:probe:2')
    expect(next.state.entries).toHaveLength(0)
    expect(next.state.documents).toEqual({})
    next.bind('session:probe:1')
    expect(next.state.entries).toHaveLength(1)
  })
  it('deduplicates question replies and bounds history with an explicit expired count', () => {
    const activity = createWorkbenchActivity()
    const event = { id: 'reply_one', kind: 'answer' as const, title: 'Answer', text: 'Confirmed', source: 'Agent', status: 'replied', requestId: 'question_one' }
    activity.append(event); activity.append(event)
    expect(activity.state.entries).toHaveLength(1)
    for (let i = 0; i < 201; i++) activity.append({ ...event, id: 'entry_' + i })
    expect(activity.state.entries).toHaveLength(200)
    expect(activity.state.dropped).toBe(2)
  })
  it('keeps the prior chart after invalid data and rejects executable or malformed restored content', () => {
    const activity = createWorkbenchActivity()
    const valid = { ...emptyContent(), kind: 'pie', points: [{ label: 'OK', value: 2 }, { label: 'Rejected', value: 4 }] }
    activity.setContent('chart', valid)
    expect(() => activity.setContent('chart', { ...valid, points: [{ label: 'Invalid', value: -1 }] })).toThrow('Pie')
    expect(activity.state.documents.chart).toEqual(valid)
    expect(() => activity.setContent('__proto__', valid)).toThrow('Invalid')
    expect(() => validateContent({ ...emptyContent(), columns: ['A'], rows: [['one', 'two']] })).toThrow('column')
    expect(() => validateContent({ ...emptyContent(), points: [{ label: 'NaN', value: NaN }] })).toThrow()
    expect(() => validateContent({ ...emptyContent(), html: '<script>bad()</script>' } as any)).toThrow()
    const restored = createWorkbenchActivity({ getItem: () => '{"entries":[{"kind":"answer"}],"documents":{}}', setItem: vi.fn() })
    restored.bind('test'); expect(restored.state.entries).toEqual([]); expect(restored.state.storageError).not.toBe('')
  })
})
