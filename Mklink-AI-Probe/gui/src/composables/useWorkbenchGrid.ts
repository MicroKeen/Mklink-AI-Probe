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
      const elements = Array.from(element.value.children) as HTMLElement[];
      grid.batchUpdate();
      for (const node of [...grid.engine.nodes]) {
        if (!widgets.some(item => item.id === node.id) || !elements.some(el => el === node.el && el.dataset.gridId === node.id)) grid.removeWidget(node.el!, false, false);
      }
      // Vue owns the component DOM; GridStack owns only its placement and handles.
      for (const item of widgets) {
        const el = elements.find(el => el.dataset.gridId === item.id);
        if (el && !grid.engine.nodes.some(node => node.el === el)) grid.makeWidget(el, item);
      }
      grid.load(widgets, false);
      grid.batchUpdate(false);
      grid.enableMove(editing.value && !narrow?.matches, false);
      grid.enableResize((resizeWhileViewing || editing.value) && !narrow?.matches, false);
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
