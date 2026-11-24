import { tr } from '../composables/useLanguage'

function detailText(value: unknown): string {
  if (typeof value === 'string') return value.trim()
  if (Array.isArray(value)) return value.map(detailText).filter(Boolean).join(' / ')
  if (!value || typeof value !== 'object') return ''
  const data = value as Record<string, unknown>
  const message = detailText(data.message) || detailText(data.msg) || detailText(data.detail) || detailText(data.error) || detailText(data.conflict)
  const field = Array.isArray(data.loc) ? data.loc.join('.') : ''
  const code = typeof data.code === 'string' || typeof data.code === 'number' ? String(data.code) : ''
  return [field, message, code && !message.includes(code) ? code : ''].filter(Boolean).join(' · ')
}

/** Preserve server guidance, including validation fields and support codes. */
export function requestError(detail: unknown, status: number, operation: string): string {
  const message = detailText(detail)
  const occupied = /\[WinError (32|33)\]/i.test(message)
  const denied = /\[WinError 5\]/i.test(message)
  if ((occupied || denied) && !/请|check|close/i.test(message)) {
    const hint = occupied
      ? tr('资源正被占用。请关闭占用该文件或端口的程序，或等待同步完成。', 'The resource is in use. Close the program using the file or port, or wait for synchronization.')
      : tr('访问被拒绝。请检查所示路径或端口的访问权限及只读状态。', 'Access denied. Check permissions and read-only attributes for the indicated path or port.')
    return [operation, hint, message].join(' · ')
  }
  if (message && !/^(?:[A-Z][A-Z_0-9.-]*|0[xX][\da-fA-F]+|-?\d+|HTTP \d+)$/.test(message)) return message
  let hint: string
  if (/^(OUTCOME_UNKNOWN|UNKNOWN_OUTCOME)$/i.test(message)) {
    hint = tr('后台无法确认操作结果。请查看原任务记录并核对设备状态，避免重复写入或复位。', 'The outcome is unknown. Check the original job and target state before another write or reset.')
  } else if (message === 'FLASH_VERIFY_FAIL') {
    hint = tr('烧录校验失败。请核对器件型号、镜像起始地址与供电，并读取失败地址作对照。', 'Flash verification failed. Check the target, image address and power, then read back the failing address.')
  } else if (status === 409) {
    hint = tr('当前设备或任务状态不允许此操作。请刷新状态，核对所选设备及正在执行的任务。', 'The current device or job state conflicts with this operation. Refresh status and check the selected device and active jobs.')
  } else if (status === 401 || status === 403) {
    hint = tr('请求未获授权。请核对当前后台连接及访问权限。', 'Access denied. Check the backend connection and access permissions.')
  } else if (status === 404) {
    hint = tr('后台找不到请求的资源。请刷新列表并核对文件或设备。', 'Resource not found. Refresh the list and check the file or device.')
  } else if (status === 400 || status === 422) {
    hint = tr('后台未接受输入。请检查所选项目、地址及参数。', 'The backend rejected the input. Check the selection, address and parameters.')
  } else {
    hint = tr('操作未正常完成。请在后台管理中查看连接状态和任务日志。', 'The operation did not complete. Check the backend connection and job log.')
  }
  return [operation, hint, message, status ? 'HTTP ' + status : ''].filter(Boolean).join(' · ')
}
