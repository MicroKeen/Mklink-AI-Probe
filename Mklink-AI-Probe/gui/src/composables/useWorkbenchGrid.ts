import { computed, onBeforeUnmount, onMounted, watch, type Ref } from 'vue';
import { GridStack, type GridStackWidget, type GridStackNode } from 'gridstack';
import { gridGeometry, type GridGeometry } from '../lib/gridLayout';
import 'gridstack/dist/gridstack.min.css';

import { tr } from './useLanguage';

export const gridRowHeight = 88;
export const geometryKeys = ['x', 'y', 'w', 'h'] as const;
export const geometryLabels = computed(() => ({ x: tr('列位置', 'Column'), y: tr('行位置', 'Row'), w: tr('宽度（列）', 'Width (columns)'), h: tr('高度（行）', 'Height (rows)') }));

export function useWorkbenchGrid(element: Ref<HTMLElement | null>, items: () => GridStackWidget[], editing: Ref<boolean>, commit: (items: GridGeometry[]) => void, fail: (error: unknown) => void, resizeWhileViewing = false) {
  let grid: GridStack | undefined;
  let events: HTMLElement | undefined;
  let narrow: MediaQueryList | undefined;
  let syncing = false;
  function changed(event: Event) {
    const nodes = (event as CustomEvent<GridStackNode[]>).detail;
    if (syncing || !grid || !nodes?.some(node => node.grid === grid)) return;
    try { commit(gridGeometry(grid.engine.nodes)); }
    catch (error) { fail(error); sync(); }
  }
  function sync() {
    if (!grid || !element.value) return;
    syncing = true;
    try {
      const widgets = items();
      const elements = new Map(Array.from(element.value.children, child => {
        const el = child as HTMLElement;
        return [el.dataset.gridId, el] as const;
      }));
      const nodes = new Map(grid.engine.nodes.map(node => [node.id, node]));
      // A pointer gesture already placed the real nodes. Reload only for external
      // geometry, constraint or DOM changes (including a different active dock tab).
      const matches = widgets.length === nodes.size && widgets.every(item => {
        const node = nodes.get(item.id);
        return node && node.el === elements.get(item.id) &&
          geometryKeys.every(key => node[key] === item[key]) &&
          node.minW === item.minW && node.minH === item.minH && node.maxW === item.maxW && node.maxH === item.maxH;
      });
      if (!matches) {
        grid.batchUpdate();
        try {
          const ids = new Set(widgets.map(item => item.id));
          for (const node of nodes.values()) {
            if (!ids.has(node.id) || elements.get(node.id) !== node.el) grid.removeWidget(node.el!, false, false);
          }
          for (const item of widgets) {
            const el = elements.get(item.id);
            if (el && nodes.get(item.id)?.el !== el) grid.makeWidget(el, item);
          }
          grid.load(widgets, false);
        } finally { grid.batchUpdate(false); }
      }
      const move = editing.value && !narrow?.matches;
      const resize = (resizeWhileViewing || editing.value) && !narrow?.matches;
      if (move !== !grid.opts.disableDrag) grid.enableMove(move, false);
      if (resize !== !grid.opts.disableResize) grid.enableResize(resize, false);
    } finally { syncing = false; }
  }
  onMounted(() => {
    if (!element.value) return;
    narrow = window.matchMedia('(max-width: 700px)');
    narrow.addEventListener('change', sync);
    grid = GridStack.init({ auto: false, column: 12, cellHeight: gridRowHeight, margin: 4, float: true, animate: true,
      handle: '.grid-drag-handle', draggable: { cancel: 'button, input, textarea, select, a', scroll: true },
      resizable: { handles: 'e, se, s, sw, w' }, alwaysShowResizeHandle: true, disableDrag: !editing.value, disableResize: !resizeWhileViewing && !editing.value,
    }, element.value);
    // GridStack dispatches nested-grid changes on the outermost grid.
    events = element.value;
    while (events.parentElement?.closest<HTMLElement>('.grid-stack')) events = events.parentElement.closest<HTMLElement>('.grid-stack')!;
    events.addEventListener('change', changed, true);
    sync();
  });
  watch(items, sync, { deep: true, flush: 'post' });
  watch(editing, sync, { flush: 'post' });
  onBeforeUnmount(() => { narrow?.removeEventListener('change', sync); events?.removeEventListener('change', changed, true); grid?.destroy(false); grid = undefined; });
}
