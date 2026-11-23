// Run on a disposable official-GUI project with this side-by-side variable / wave fixture.
// The scenario saves its split layout. Use a headed Chromium browser for system PiP.
async page => {
  const wb = page.getByTestId('workbench')
  const left = wb.locator('article[data-panel-id="legacy_variables"]')
  const right = wb.locator('article[data-panel-id="legacy_watch_main"]')
  const edit = wb.locator('.workbench-actions button[aria-pressed]')
  const locate = () => wb.locator('.workbench-locator select').selectOption('legacy_variables')
  const geometry = card => card.evaluate(el => ['x','y','w','h'].map(k => Number(el.getAttribute('gs-' + k) || 0)))
  await page.setViewportSize({ width: 1440, height: 900 })
  await locate()
  if (await edit.getAttribute('aria-pressed') === 'false') await edit.click()
  async function drop(edge) {
    const grip = left.locator('.dock-grip')
    await left.locator('.workbench-card-header').evaluate(el => el.scrollIntoView({ block: 'start' }))
    await grip.click({ trial: true })
    const box = await grip.boundingBox()
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
    await page.mouse.down()
    try {
      await page.mouse.move(box.x + 20, box.y + 13, { steps: 5 })
      const zone = right.locator('[data-snap-edge=' + edge + ']')
      await zone.waitFor({ timeout: 3000 })
      const target = await zone.boundingBox()
      await page.mouse.move(target.x + target.width / 2, target.y + target.height / 2, { steps: 12 })
      await page.mouse.move(target.x + target.width / 2 + 1, target.y + target.height / 2)
    } finally { await page.mouse.up() }
  }
  for (const edge of ['right', 'left']) {
    await drop(edge)
    const a = await geometry(left), b = await geometry(right)
    if (a[1] !== b[1] || (edge === 'right' ? a[0] !== b[0] + b[2] : b[0] !== a[0] + a[2])) throw Error('Incorrect ' + edge + ' edge')
  }
  await drop('tabs')
  await left.locator('.dock-tabs').waitFor()
  if (await left.getByRole('tab').count() !== 2) throw Error('Drop did not group the views')
  await left.locator('.panel-read').click()
  await left.getByRole('tab', { selected: false }).click()
  await right.locator('.workbench-card-header').waitFor({ state: 'visible' })
  await right.getByRole('tab', { selected: true }).press('ArrowRight')
  if (!await left.getByRole('tab', { selected: true }).evaluate(el => el === document.activeElement)) throw Error('Lost tab focus')
  await page.keyboard.press('Escape')
  await left.getByRole('button', { name: /分离当前面板|Undock current panel/ }).click()
  await left.locator('.workbench-card-header button[aria-expanded]').click()
  const dialog = page.locator('dialog[open]')
  await dialog.locator('.panel-editor select').last().selectOption('legacy_watch_main')
  await dialog.getByRole('button', { name: /左右分栏|Split side by side/ }).click()
  await dialog.waitFor({ state: 'detached' })
  await edit.click()
  const divider = left.getByRole('separator', { name: /调整左右分栏比例|Resize adjacent columns/ })
  await divider.press('ArrowRight')
  const a = await geometry(left), b = await geometry(right)
  if (a[2] !== 7 || b[2] !== 5 || a[1] !== b[1] || a[0] + a[2] !== b[0]) throw Error('Shared bounds changed')
  await wb.getByTestId('save-layout').click()
  await wb.locator('[role=status]').filter({ hasText: /已保存|Layout saved/ }).waitFor()
  await page.reload()
  await left.waitFor()
  if ((await geometry(left)).join() !== a.join() || (await geometry(right)).join() !== b.join()) throw Error('Split lost after reload')
  for (const [width, height] of [[390,800],[667,375],[1440,900]]) {
    await page.setViewportSize({ width, height })
    await locate()
    const geometry = await wb.evaluate(el => {
      const bar = el.querySelector('.workbench-toolbar').getBoundingClientRect()
      const view = el.querySelector('.workbench-viewport').getBoundingClientRect()
      return { separate: bar.bottom <= view.top + 1, height: view.height }
    })
    if (!geometry.separate || geometry.height < 160) throw Error('Controls obscure the reading area')
    await left.locator('.panel-read').click()
    if (await wb.locator('.workbench-card-header:visible').count() !== 1) throw Error('Enlarged view has other cards')
    await page.keyboard.press('Escape')
    if (!await left.locator('.panel-read').evaluate(el => document.activeElement === el)) throw Error('Lost reading focus')
  }
  // Stage a deterministic recording through the normal log-file input.
  await right.getByTestId('replay-file').evaluate(input => {
    const transfer = new DataTransfer()
    transfer.items.add(new File(['timestamp,signal\n0,0\n30,1\n60,0\n'], 'split-test.csv', { type: 'text/csv' }))
    input.files = transfer.files
    input.dispatchEvent(new Event('change', { bubbles: true }))
  })
  await right.locator('[data-testid="replay-seek"]:enabled').waitFor()
  await right.locator('.panel-read').click()
  const live = await right.locator('.workbench-panel-body').elementHandle()
  const opened = page.context().waitForEvent('page')
  await wb.getByRole('button', { name: /浮窗置顶|Float on top/ }).click()
  const pip = await opened
  let lastPosition = 0
  try {
    await pip.locator('.workbench-panel-body canvas').first().waitFor()
    if (!await live.evaluate(el => el.ownerDocument === window.documentPictureInPicture.window.document)) throw Error('Original live view was replaced')
    await pip.getByRole('button', { name: /^(开始|Start)$/ }).click()
    await pip.waitForFunction(() => Number(document.querySelector('[data-testid=replay-seek]').value) > 0)
    const menu = pip.locator('.watch-log-controls summary')
    await menu.click()
    const popup = pip.locator('.watch-log-menu')
    await popup.waitFor({ state: 'visible' })
    if (!await popup.evaluate(el => { const b = el.getBoundingClientRect(); return el.contains(document.elementFromPoint(b.left + 8, b.top + 8)) })) throw Error('Floating menu obscured')
    await pip.keyboard.press('Escape')
    if (!await menu.evaluate(el => document.activeElement === el && !el.parentElement.open)) throw Error('Floating menu retained focus')
    lastPosition = Number(await pip.getByTestId('replay-seek').inputValue())
  } finally { await pip.close() }
  await right.locator('.workbench-panel-body canvas').first().waitFor({ state: 'attached' })
  if (!await live.evaluate(el => el.ownerDocument === document && el.isConnected)) throw Error('Native close lost the original view')
  await page.waitForFunction(last => Number(document.querySelector('article[data-panel-id="legacy_watch_main"] [data-testid=replay-seek]').value) > last, lastPosition)
  return { replayContinued: true, magneticDock: true, persistedSplit: [a[2], b[2]], focusRestored: true, pictureInPicture: true, originalViewReturned: true }
}
