<template>
  <div class="rtt-terminal-panel" @keydown.capture="onFindShortcut">
    <div v-if="searchOpen" class="terminal-find" role="search" @keydown.esc.stop.prevent="closeSearch">
      <input ref="findInput" v-model="query" type="text" :aria-label="tr('查找终端文本', 'Find terminal text')"
        :placeholder="tr('查找终端文本', 'Find terminal text')" @keydown.enter="onFindEnter">
      <span v-if="missing" role="status">{{ tr('未找到', 'No matches') }}</span>
      <button type="button" :disabled="!query" :aria-label="tr('上一个匹配', 'Previous match')" @click="find('previous')"><ChevronUp :size="16" /></button>
      <button type="button" :disabled="!query" :aria-label="tr('下一个匹配', 'Next match')" @click="find('next')"><ChevronDown :size="16" /></button>
      <button type="button" :aria-label="tr('关闭查找', 'Close search')" @click="closeSearch"><X :size="16" /></button>
    </div>
    <div ref="host" class="terminal-screen" role="application" tabindex="-1"
      :aria-label="ariaLabel || tr('RTT 终端', 'RTT terminal')" @mousedown="focus" />
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ChevronDown, ChevronUp, X } from '@lucide/vue'
import { invoke, isTauri } from '@tauri-apps/api/core'
import { writeClipboard } from '../../lib/writeClipboard'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { SearchAddon } from '@xterm/addon-search'
import '@xterm/xterm/css/xterm.css'
import { tr } from '../../composables/useLanguage'
import { SeggerAnsiNormalizer } from '../../lib/seggerAnsi'

const props = defineProps<{ inputEnabled: boolean, ariaLabel?: string }>()
const emit = defineEmits<{ input: [data: string] }>()
const host = ref<HTMLElement | null>(null)
const findInput = ref<HTMLInputElement | null>(null)
const searchOpen = ref(false)
const query = ref('')
const missing = ref(false)
let search: SearchAddon | undefined
let searchRetry: ReturnType<typeof setTimeout> | undefined
const normalizer = new SeggerAnsiNormalizer()
let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
let resizeObserver: ResizeObserver | null = null
let visibilityObserver: IntersectionObserver | null = null
let visible = typeof IntersectionObserver === 'undefined'
let pasteHost: HTMLElement | null = null
let pendingOutput = ''
let outputFrame: number | null = null
let outputFallback: ReturnType<typeof setTimeout> | null = null
let writeInFlight = false
let disposed = false
const OUTPUT_FALLBACK_MS = 50

function flushOutput(): void {
  if (outputFrame !== null) cancelAnimationFrame(outputFrame)
  outputFrame = null
  if (outputFallback !== null) clearTimeout(outputFallback)
  outputFallback = null
  if (!pendingOutput || writeInFlight || disposed || !terminal) return
  const output = pendingOutput
  pendingOutput = ''
  writeInFlight = true
  terminal.write(output, () => {
    writeInFlight = false
    if (!disposed && missing.value && searchOpen.value && searchRetry === undefined) {
      searchRetry = setTimeout(() => {
        searchRetry = undefined
        if (searchOpen.value && missing.value) find('incremental')
      }, 300)
    }
    if (pendingOutput && !disposed) scheduleOutput()
  })
}

function scheduleOutput(): void {
  if (outputFrame !== null || writeInFlight || disposed) return
  outputFrame = requestAnimationFrame(flushOutput)
  outputFallback = setTimeout(flushOutput, OUTPUT_FALLBACK_MS)
}

function write(text: string): void {
  const normalized = normalizer.push(text)
  if (!normalized) return
  pendingOutput += normalized
  scheduleOutput()
}

function clear(): void {
  normalizer.reset()
  missing.value = searchOpen.value && !!query.value
  if (outputFrame !== null) cancelAnimationFrame(outputFrame)
  outputFrame = null
  if (outputFallback !== null) clearTimeout(outputFallback)
  outputFallback = null
  terminal?.clear()
  pendingOutput = '\x1b[2J\x1b[H'
  scheduleOutput()
}

function fit(): void {
  const element = host.value
  if (!visible || !element || element.clientWidth <= 0 || element.clientHeight <= 0) return
  try { fitAddon?.fit() } catch { /* hidden or not measured yet */ }
}

function focus(): void {
  terminal?.focus()
}

async function openSearch(): Promise<void> {
  if (!terminal) return
  if (!search) {
    search = new SearchAddon()
    terminal.loadAddon(search)
  }
  searchOpen.value = true
  await nextTick()
  findInput.value?.focus()
  findInput.value?.select()
}

function closeSearch(): void {
  if (query.value) terminal?.clearSelection()
  query.value = ''
  missing.value = false
  searchOpen.value = false
  focus()
}

function find(direction: 'next' | 'previous' | 'incremental'): void {
  if (!search || !searchOpen.value) return
  if (!query.value) {
    terminal?.clearSelection()
    missing.value = false
    return
  }
  missing.value = direction === 'previous'
    ? !search.findPrevious(query.value)
    : !search.findNext(query.value, { incremental: direction === 'incremental' })
}

function onFindShortcut(event: KeyboardEvent): void {
  if (event.key.toLowerCase() !== 'f' || !(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return
  event.preventDefault()
  event.stopPropagation()
  void openSearch()
}

function onFindEnter(event: KeyboardEvent): void {
  if (event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  find(event.shiftKey ? 'previous' : 'next')
}

watch(query, () => find('incremental'))

function activate(): void {
  requestAnimationFrame(() => {
    fit()
    focus()
  })
}

async function readTauriClipboard(): Promise<string> {
  try {
    return await invoke<string>('clipboard_read_text')
  } catch {
    if (!navigator.clipboard?.readText) throw new Error('Clipboard read is unavailable')
    return await navigator.clipboard.readText()
  }
}

function handleBrowserPaste(event: ClipboardEvent): void {
  event.preventDefault()
  event.stopPropagation()
  if (!props.inputEnabled) return
  const text = event.clipboardData?.getData('text/plain') ?? ''
  if (text) terminal?.paste(text)
}

function handleShortcut(event: KeyboardEvent): boolean {
  if (event.type !== 'keydown' || (!event.ctrlKey && !event.metaKey) || event.altKey) return true
  const key = event.key.toLowerCase()
  if (key === 'a') {
    event.preventDefault()
    terminal?.selectAll()
    return false
  }
  if (key === 'c') {
    const selection = terminal?.getSelection() ?? ''
    if (!selection) return true
    event.preventDefault()
    void writeClipboard(selection, focus).catch(() => undefined)
    return false
  }
  if (key === 'v') {
    if (!props.inputEnabled) {
      event.preventDefault()
      return false
    }
    // Browser paste events provide clipboardData without the permission prompt
    // required by navigator.clipboard.readText(). The capture listener below
    // feeds that trusted event into xterm exactly once.
    // Returning true lets xterm translate Ctrl+V into the terminal control
    // byte SYN (0x16) and cancel the DOM key event. Leave the event itself
    // untouched, but stop xterm's key handling so Chromium can dispatch its
    // trusted paste event to the capture listener below.
    if (!isTauri()) return false
    event.preventDefault()
    void readTauriClipboard()
      .then(text => {
        if (text && props.inputEnabled) terminal?.paste(text)
      })
      .catch(() => undefined)
    return false
  }
  return true
}

watch(() => props.inputEnabled, enabled => {
  if (terminal) terminal.options.disableStdin = !enabled
})

onMounted(() => {
  const element = host.value
  if (!element) return
  terminal = new Terminal({
    allowTransparency: false,
    convertEol: true,
    cursorBlink: true,
    disableStdin: !props.inputEnabled,
    fontFamily: 'Cascadia Mono, Consolas, SFMono-Regular, monospace',
    fontSize: 13,
    lineHeight: 1.15,
    scrollback: 5000,
    theme: {
      background: '#10151d', foreground: '#d7dde7', cursor: '#f2f5f8',
      selectionBackground: '#315d91aa', black: '#1b2028', red: '#e7646a',
      green: '#4fc47f', yellow: '#e6b657', blue: '#5b97e5', magenta: '#b183d7',
      cyan: '#4bb8c4', white: '#d7dde7', brightBlack: '#697586',
      brightRed: '#ff7b81', brightGreen: '#6bd995', brightYellow: '#f5c96d',
      brightBlue: '#74adf5', brightMagenta: '#c69aeb', brightCyan: '#62cdd8',
      brightWhite: '#ffffff',
    },
  })
  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(element)
  pasteHost = element
  element.addEventListener('paste', handleBrowserPaste, true)
  terminal.attachCustomKeyEventHandler(handleShortcut)
  terminal.onData(data => {
    if (props.inputEnabled) emit('input', data)
  })
  if (pendingOutput) scheduleOutput()
  // xterm pauses renderer measurements offscreen. Resizing its buffer while
  // those measurements are stale can turn the resize into a history scroll.
  // Keep receiving output, and fit only when the terminal becomes visible.
  if (typeof IntersectionObserver !== 'undefined') {
    visibilityObserver = new IntersectionObserver(entries => {
      visible = entries[entries.length - 1]?.isIntersecting ?? false
      if (visible) fit()
    })
    visibilityObserver.observe(element)
  }
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(fit)
    resizeObserver.observe(element)
  }
  fit()
})

onUnmounted(() => {
  disposed = true
  clearTimeout(searchRetry)
  if (outputFrame !== null) cancelAnimationFrame(outputFrame)
  outputFrame = null
  if (outputFallback !== null) clearTimeout(outputFallback)
  outputFallback = null
  pendingOutput = ''
  pasteHost?.removeEventListener('paste', handleBrowserPaste, true)
  pasteHost = null
  resizeObserver?.disconnect()
  visibilityObserver?.disconnect()
  const currentTerminal = terminal
  terminal = null
  fitAddon = null
  if (currentTerminal) {
    if (writeInFlight) currentTerminal.write('', () => currentTerminal.dispose())
    else currentTerminal.dispose()
  }
})

defineExpose({ write, clear, activate, focus, flushOutput, openSearch })
</script>

<style scoped>
.rtt-terminal-panel {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 220px;
  margin-top: 8px;
  padding: 8px 6px;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: #10151d;
}
.terminal-screen { flex: 1 1 auto; min-height: 0; min-width: 0; }
.terminal-find { display: flex; align-items: center; justify-content: flex-end; gap: 4px; margin-bottom: 4px; }
.terminal-find input { min-width: 0; width: 22ch; }
.terminal-find span { color: #d7dde7; white-space: nowrap; }
.terminal-find button { display: inline-flex; align-items: center; padding: 3px; }
.rtt-terminal-panel :deep(.xterm) { height: 100%; }
.rtt-terminal-panel :deep(.xterm-viewport) { scrollbar-width: thin; }
</style>
