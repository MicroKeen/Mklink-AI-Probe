// Run in a disposable official GUI window with at least two selected AXF symbols.
// Adds and closes one unsaved variable panel; leaves the project layout on disk intact.
async page => {
  const wb = page.getByTestId('workbench')
  const edit = wb.locator('.workbench-actions button[aria-pressed]')
  const initial = await edit.getAttribute('aria-pressed') === 'true'
  const cards = wb.locator('.workbench-grid > article')
  const original = await cards.evaluateAll(es => es.map(el => el.dataset.panelId))
  const size = page.viewportSize()
  let added
  async function drag(locator, dy) {
    await locator.evaluate(el => el.scrollIntoView({ block: 'center', inline: 'nearest' }))
    const box = await locator.boundingBox()
    const x = box.x + box.width / 2, y = box.y + box.height / 2
    if (!await locator.evaluate((el, [x, y]) => el.contains(document.elementFromPoint(x, y)), [x, y])) throw Error('Resize handle is covered')
    await page.mouse.move(x, y)
    await page.mouse.down()
    try {
      await page.mouse.move(x, y + Math.sign(dy) * 7, { steps: 3 })
      await page.waitForTimeout(140)
      await page.mouse.move(x, y + dy, { steps: 12 })
    } finally { await page.mouse.up() }
    await page.waitForTimeout(300)
  }
  try {
    await page.setViewportSize({ width: 1440, height: 900 })
    if (!initial) await edit.click()
    await wb.locator('.workbench-actions select').selectOption('variables')
    await wb.getByTestId('add-panel').click()
    const id = await cards.evaluateAll((es, before) => es.map(el => el.dataset.panelId).find(id => !before.includes(id)), original)
    if (!id) throw Error('New variable panel missing')
    added = wb.locator('article[data-panel-id="' + id + '"]')
    await edit.click()
    const height = () => added.evaluate(el => el.clientHeight)
    const wide = await height()
    await drag(added.locator(':scope > .ui-resizable-s'), 130)
    const wideAfter = await height()
    if (wideAfter < wide + 88) throw Error('Cannot resize in viewing mode')
    await page.setViewportSize({ width: 390, height: 820 })
    const handle = added.locator('.narrow-panel-resize')
    const narrow = await height()
    await drag(handle, 110)
    const narrowAfter = await height()
    if (narrowAfter < narrow + 88) throw Error('Single-column height did not follow the pointer')
    await handle.press('ArrowUp')
    await page.waitForFunction(({ el, expected }) => el.clientHeight === expected, { el: await added.elementHandle(), expected: narrowAfter - 88 }, { timeout: 2000 })
    const divider = added.getByTestId('resize-signals-section')
    const split = Number(await divider.getAttribute('aria-valuenow'))
    await drag(divider, 115)
    const splitAfter = Number(await divider.getAttribute('aria-valuenow'))
    if (splitAfter < split + 90) throw Error('Variable divider stopped early')
    const list = added.locator('.selected-workspace'), catalog = added.getByTestId('all-variables')
    const last = list.locator('.selected-signal:visible').last()
    if (await list.locator('.selected-signal:visible').count() < 2) throw Error('Load symbols first')
    await last.scrollIntoViewIfNeeded()
    if (!await last.evaluate(el => {
      const box = el.getBoundingClientRect()
      return el.contains(document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2))
    })) throw Error('Last selected symbol was clipped')
    const rows = catalog.locator('.variable-section-rows')
    await rows.scrollIntoViewIfNeeded()
    await rows.hover()
    await page.mouse.wheel(0, 8000)
    await page.waitForFunction(el => el.scrollTop + el.clientHeight >= el.scrollHeight - 2, await rows.elementHandle())
    await added.getByRole('button', { name: /关闭面板|Close panel/ }).click()
    await page.getByTestId('confirm-close-panel').click()
    if (await cards.count() !== original.length) throw Error('Closing one card affected another')
    return { wide, wideAfter, narrow, narrowAfter, split, splitAfter, lastSelectedReachable: true, catalogBottomReachable: true, originalPanels: original.length }
  } finally {
    if (added && await added.count()) {
      await added.getByRole('button', { name: /关闭面板|Close panel/ }).click()
      await page.getByTestId('confirm-close-panel').click()
    }
    if ((await edit.getAttribute('aria-pressed') === 'true') !== initial) await edit.click()
    if (size) await page.setViewportSize(size)
  }
}
