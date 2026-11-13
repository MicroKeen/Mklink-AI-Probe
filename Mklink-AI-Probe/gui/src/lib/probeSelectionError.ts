import { tr } from '../composables/useLanguage'

export function probeSelectionError(error: { detail?: { reason?: string }; message?: string }): string {
  switch (error.detail?.reason) {
    case 'probe_missing':
    case 'missing':
      return tr('所选下载器已不可用。请检查 USB 连接，刷新列表后重新选择；不会自动连接其他下载器。',
        'The selected probe is unavailable. Check USB, refresh the list and select a probe; another device will not be connected automatically.')
    case 'port_changed':
      return tr('下载器端口已变化。请刷新列表后重新连接同一下载器。',
        'The probe port changed. Refresh the list and reconnect the same probe.')
    case 'probe_ambiguous':
    case 'probe_selection_required':
      return tr('检测到多个匹配的下载器，请在列表中明确选择一个命令端口。',
        'Multiple probes match. Select one command port explicitly from the list.')
    case 'probe_in_use':
      return tr('此下载器正被另一客户端使用。请选择其他下载器，或先在原客户端断开；当前连接保持不变。',
        'This probe is in use by another client. Select another probe or disconnect it in that client first; the current connection is unchanged.')
    default:
      return error.message || String(error)
  }
}
