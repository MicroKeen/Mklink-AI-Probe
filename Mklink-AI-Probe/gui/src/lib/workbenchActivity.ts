import { reactive, type InjectionKey } from 'vue'
import { interaction, objectSchema } from './frontendControl'

export const contentKinds = ['text', 'table', 'bar', 'line', 'pie']
export const contentSchema = objectSchema({
  title: { type: 'string', maxLength: 200 }, text: { type: 'string', maxLength: 16000 },
  kind: { type: 'string', enum: contentKinds }, unit: { type: 'string', maxLength: 40 },
  columns: { type: 'array', maxItems: 8, items: { type: 'string', maxLength: 100 } },
  rows: { type: 'array', maxItems: 100, items: { type: 'array', maxItems: 8, items: { type: 'string', maxLength: 500 } } },
  points: { type: 'array', maxItems: 100, items: objectSchema({ label: { type: 'string', maxLength: 120 }, value: { type: 'number' } }) },
})
export interface PanelContent { title: string; text: string; kind: string; unit: string; columns: string[]; rows: string[][]; points: { label: string; value: number }[] }
export const emptyContent = (): PanelContent => ({ title: '', text: '', kind: 'text', unit: '', columns: [], rows: [], points: [] })
export function validateContent(value: PanelContent): PanelContent {
  interaction.validateArgs(value, contentSchema)
  if (value.rows.some(row => row.length !== value.columns.length)) throw new Error('Each table row must match the column count')
  if (value.kind === 'pie' && value.points.length && (value.points.some(point => point.value < 0) || !(value.points.reduce((sum, point) => sum + point.value, 0) > 0))) throw new Error('Pie values must be nonnegative with a positive total')
  if (JSON.stringify(value).length > 24000) throw new Error('Display content is too large; split it into smaller tables')
  return JSON.parse(JSON.stringify(value))
}
export interface ActivityEntry { id: string; time: string; kind: 'operation' | 'question' | 'answer' | 'note' | 'error'; source: string; title: string; text: string; status: string; requestId?: string }
export function createWorkbenchActivity(storage?: Pick<Storage, 'getItem' | 'setItem'>) {
  const state = reactive({ entries: [] as ActivityEntry[], dropped: 0, documents: {} as Record<string, PanelContent>, storageError: '' })
  let key = ''
  function persist() {
    if (!key || !storage) return
    try { storage.setItem(key, JSON.stringify({ entries: state.entries, dropped: state.dropped, documents: state.documents })); state.storageError = '' }
    catch { state.storageError = '本窗口历史无法保存；当前显示保留，刷新后可能丢失。' }
  }
  function validEntry(entry: ActivityEntry) {
    return entry && ['operation', 'question', 'answer', 'note', 'error'].includes(entry.kind) &&
      ['id', 'time', 'source', 'title', 'text', 'status'].every(field => typeof entry[field as keyof ActivityEntry] === 'string') &&
      entry.id.length > 0 && entry.id.length <= 160 && entry.time.length <= 40 && Number.isFinite(Date.parse(entry.time)) && entry.text.length <= 16000 && entry.title.length <= 200 && entry.source.length <= 200 && entry.status.length <= 100 &&
      (entry.requestId === undefined || typeof entry.requestId === 'string' && /^[a-zA-Z0-9_-]{1,80}$/.test(entry.requestId))
  }
  function bind(identity: string) {
    const next = identity ? 'mklink.flexible.history.' + identity : ''
    if (key === next) return
    key = next; state.entries = []; state.documents = {}; state.dropped = 0; state.storageError = ''
    if (!key || !storage) return
    try {
      const value = JSON.parse(storage.getItem(key) || 'null')
      if (!value) return
      if (!Array.isArray(value.entries) || value.entries.length > 200 || !value.entries.every(validEntry) || !Number.isSafeInteger(value.dropped) || value.dropped < 0) throw new Error('Invalid history')
      const documents = Object.entries(value.documents || {})
      if (documents.length > 32) throw new Error('Too many information panels')
      for (const [id, document] of documents) { if (!/^[a-zA-Z0-9_-]{1,80}$/.test(id) || ['__proto__', 'constructor', 'prototype'].includes(id)) throw new Error('Invalid panel'); validateContent(document as PanelContent) }
      state.entries = value.entries; state.dropped = value.dropped; state.documents = Object.fromEntries(documents) as Record<string, PanelContent>
    } catch { state.storageError = '本窗口历史不可读取，未执行其中任何操作。' }
  }
  function append(input: Omit<ActivityEntry, 'id' | 'time'> & { id?: string }) {
    const entry = { ...input, id: input.id || crypto.randomUUID(), time: new Date().toISOString() }
    if (!validEntry(entry)) throw new Error('Invalid activity entry')
    if (state.entries.some(item => item.id === entry.id)) return
    state.entries.push(entry)
    if (state.entries.length > 200) { state.dropped += state.entries.length - 200; state.entries.splice(0, state.entries.length - 200) }
    persist()
  }
  function setContent(id: string, value: PanelContent) {
    if (!/^[a-zA-Z0-9_-]{1,80}$/.test(id) || ['__proto__', 'constructor', 'prototype'].includes(id) || !(id in state.documents) && Object.keys(state.documents).length >= 32) throw new Error('Invalid information panel')
    state.documents[id] = validateContent(value); persist()
  }
  return { state, bind, append, setContent,
    clear: () => { state.entries = []; state.dropped = 0; persist() },
    follow: (id: string) => { delete state.documents[id]; persist() },
    latestAnswer: () => [...state.entries].reverse().find(entry => entry.kind === 'answer'),
  }
}
export type WorkbenchActivity = ReturnType<typeof createWorkbenchActivity>
export const workbenchActivityKey: InjectionKey<WorkbenchActivity> = Symbol('workbench-activity')
export const activitySourceKey: InjectionKey<string> = Symbol('workbench-activity-source')
