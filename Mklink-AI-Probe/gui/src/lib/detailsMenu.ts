/** Lift shared instrument menus and help out of clipped panels. */
export function mountAnchoredPopover(summary: HTMLElement, menu: HTMLElement, onClose: () => void) {
  const nativePopover = typeof menu.showPopover === 'function';
  let shown = false;
  if (nativePopover) menu.setAttribute('popover', 'manual');
  Object.assign(menu.style, { position: 'fixed', inset: 'auto', margin: '0', width: 'max-content', minWidth: '0', maxWidth: 'calc(100vw - 16px)', maxHeight: 'calc(100vh - 16px)', overflow: 'auto', display: 'none' });
  function position() {
    if (!shown) return;
    const anchor = summary.getBoundingClientRect();
    if (anchor.width === 0 && anchor.height === 0) { close(); return; }
    const box = menu.getBoundingClientRect();
    const { innerWidth, innerHeight } = summary.ownerDocument.defaultView || window;
    const left = anchor.left + box.width <= innerWidth - 8 ? anchor.left : anchor.right - box.width;
    const top = anchor.bottom + 4 + box.height <= innerHeight - 8 ? anchor.bottom + 4 : anchor.top - box.height - 4;
    menu.style.left = `${Math.max(8, Math.min(left, innerWidth - box.width - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(top, innerHeight - box.height - 8))}px`;
  }
  function show() {
      listen(summary.ownerDocument);
      menu.style.display = '';
      if (nativePopover && !shown) menu.showPopover();
      shown = true;
      position();
  }
  function close() {
      const wasShown = shown;
      if (nativePopover && shown && menu.isConnected) menu.hidePopover();
      shown = false;
      menu.style.display = 'none';
      unlisten();
      if (wasShown) onClose();
  }
  function outside(event: PointerEvent) { if (!summary.contains(event.target as Node) && !menu.contains(event.target as Node)) close(); }
  function escape(event: KeyboardEvent) {
    if (!shown || event.key !== 'Escape') return;
    if (event.target instanceof Element && event.target.closest('dialog[open]') && !menu.contains(event.target)) return;
    event.preventDefault(); event.stopPropagation(); close(); summary.focus();
  }
  function scroll(event: Event) { if (!menu.contains(event.target as Node)) close(); }
  let listening: Document | undefined;
  function listen(doc: Document) {
    if (listening === doc) return;
    unlisten();
    listening = doc;
    doc.addEventListener('pointerdown', outside);
    doc.addEventListener('keydown', escape, true);
    doc.addEventListener('scroll', scroll, true);
    doc.defaultView?.addEventListener('resize', position);
  }
  function unlisten() {
    listening?.removeEventListener('pointerdown', outside);
    listening?.removeEventListener('keydown', escape, true);
    listening?.removeEventListener('scroll', scroll, true);
    listening?.defaultView?.removeEventListener('resize', position);
    listening = undefined;
  }
  const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(position) : undefined;
  observer?.observe(menu);
  observer?.observe(summary);
  function dispose() {
    close(); observer?.disconnect();
  }
  return { show, close, dispose };
}

export function mountDetailsMenu(details: HTMLDetailsElement, menu: HTMLElement): () => void {
  const popup = mountAnchoredPopover(details.querySelector('summary')!, menu, () => { details.open = false; });
  const sync = () => { if (details.open) popup.show(); else popup.close(); };
  details.addEventListener('toggle', sync);
  sync();
  return () => { details.removeEventListener('toggle', sync); popup.dispose(); };
}
