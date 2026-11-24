import type { JsonObject } from './frontendControl'

const labels: Record<string, string> = {
  args_json: '操作参数', arguments_json: '操作参数', confirm: '确认本次执行', paused: '暂停显示',
  device_status: '设备状态', watch: '读取变量', write_memory: '写入内存', read_memory: '读取内存',
  read_variable: '读取变量', write_variable: '设置变量', superwatch_values: '最新采样',
  superwatch_recording_export: '导出 Excel', superwatch_recording_status: '记录状态',
  superwatch_start: '开始采样', superwatch_stop: '停止采样', superwatch_add: '添加采样变量',
  superwatch_sampling: '设置变量采集开关', sampling_enabled: '参与采集', superwatch_items: '已选变量', address: '地址', data_hex: '写入数据（十六进制）', verify: '写后校验',
  path: '路径', directory: '保存目录', names: '变量名称', name: '名称', value: '值', rows: '变量读数',
  type: '类型', size: '字节数', connected: '已连接', state: '状态', status: '状态', active: '正在记录',
  running: '正在采样', sample: '最新采样', values: '数值', channels: '通道', sequence: '采样序号',
  samples: '采样组数', error: '错误', interval: '采样间隔（秒）', age_seconds: '采样距今（秒）',
  bytes_written: '已写入字节', acknowledged: '设备已应答', verified: '已回读验证',
  export_state: '导出状态', export_path: '导出文件', export_error: '导出错误',
  job_id: '任务编号', runtime_job_id: '任务编号', message: '说明', hint: '建议', detail: '说明',
  parts: '文件分段数', bytes: '字节数', started_at: '开始时间', stopped_at: '结束时间',
  export_parts: '导出分段数', export_format: '导出格式', export_rows: '导出行数', export_sheets: '工作表数',
  acknowledgedValue: '已确认的值', sampled: '已采样', generation: '会话序号', operation_id: '操作编号', result: '结果',
}
export const label = (key: string): string => labels[key] || key.replace(/_/g, ' ')
export function display(value: unknown, key?: string): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (['started_at', 'stopped_at'].includes(key || '') && typeof value === 'number' && Number.isFinite(value) && value > 0 && value < 8640000000000) return new Date(value * 1000).toLocaleString('zh-CN', { hour12: false })
  const states: Record<string, string> = { idle: '等待操作', running: '执行中', completed: '已完成',
    succeeded: '已成功', submitted: '已提交，等待结果', queued: '排队中', accepted: '已受理',
    failed: '失败', unknown: '结果待确认', stopped: '已停止', pending: '等待处理', generating: '生成中', ok: '成功' }
  return typeof value === 'string' ? states[value] || labels[value] || value : String(value)
}
export function errorText(value: any): string {
  if (typeof value === 'string') {
    try { return errorText(JSON.parse(value)) } catch { return value.replace(/^Error: /, '') }
  }
  if (Array.isArray(value)) return value.map(errorText).join('；')
  return value?.message ? errorText(value.message) : value?.hint ? errorText(value.hint)
    : value?.detail ? errorText(value.detail) : value?.msg ? errorText(value.msg) : '操作未完成，请查询当前状态。'
}
export interface OperationField { key: string; schema: JsonObject; required: boolean; kind: string }
export function operationFields(capability?: JsonObject): { fields: OperationField[]; guided: boolean } {
  const body = capability?.requestBody?.content?.['application/json']?.schema || {}
  const definitions = new Map<string, { schema: JsonObject; required: boolean }>()
  for (const parameter of capability?.parameters || []) definitions.set(parameter.name, { schema: parameter.schema || {}, required: parameter.required === true })
  for (const [key, schema] of Object.entries(body.properties || {})) definitions.set(key, { schema: schema as JsonObject, required: body.required?.includes(key) === true })
  let guided = body.type === 'object' && !body.properties && body.additionalProperties !== false
  const fields = [...definitions].map(([key, definition]) => {
    const choices = definition.schema.anyOf?.filter((item: JsonObject) => item.type !== 'null')
    const schema = choices?.length === 1 ? { ...definition.schema, ...choices[0] } : definition.schema
    const kind = schema.enum ? 'enum' : ['string', 'number', 'integer', 'boolean'].includes(schema.type) ? schema.type
      : schema.type === 'array' && schema.items?.type === 'string' ? 'lines' : 'guided'
    if (kind === 'guided' && definition.required) guided = true
    return { key, schema, required: definition.required, kind }
  })
  return { fields, guided }
}
export function formArguments(fields: OperationField[], values: JsonObject): JsonObject {
  const result: JsonObject = {}
  for (const field of fields) {
    const value = values[field.key]
    if (value === undefined || value === '') {
      if (field.required) throw new Error(`请填写${label(field.key)}`)
      continue
    }
    if (field.kind === 'guided') continue
    const parsed = field.kind === 'lines' ? String(value).split(/\r?\n/).map(item => item.trim()).filter(Boolean)
      : field.kind === 'boolean' ? value === 'true' : field.kind === 'enum' ? field.schema.enum[Number(value)]
      : field.kind === 'number' || field.kind === 'integer' ? Number(value) : value
    if (typeof parsed === 'number' && (!Number.isFinite(parsed) || (field.kind === 'integer' && !Number.isInteger(parsed)))) throw new Error(`${label(field.key)}需要有效${field.kind === 'integer' ? '整数' : '数值'}`)
    if (field.schema.minimum !== undefined && parsed < field.schema.minimum || field.schema.maximum !== undefined && parsed > field.schema.maximum) throw new Error(`${label(field.key)}超出允许范围`)
    result[field.key] = parsed
  }
  return result
}
