// Run on the official GUI with a disposable browser context and clipboard.
async page => {
  const origin = new URL(page.url()).origin
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin })
  await page.goto(origin + '/#/dashboard?tab=workbench')
  const w = page.getByTestId('workbench'), help = w.getByTestId('workbench-help')
  await help.waitFor()
  const theme = page.getByTestId('theme-select'), language = page.getByTestId('global-language-toggle')
  const initialTheme = await theme.inputValue(), size = page.viewportSize()
  const isEnglish = () => page.evaluate(() => document.documentElement.lang === 'en')
  const initialEnglish = await isEnglish(), save = w.getByTestId('save-layout')
  async function checkCloseButton(dialog) {
    const button = dialog.locator(':scope > header button').first()
    const b = await button.boundingBox(), icon = await button.locator('svg').boundingBox()
    if (!b || !icon || b.width !== b.height || b.width < 28 ||
        Math.abs(b.x + b.width / 2 - icon.x - icon.width / 2) > 0.5 ||
        Math.abs(b.y + b.height / 2 - icon.y - icon.height / 2) > 0.5) throw Error('Close icon is off-center or has a small target')
  }
  const result = []
  try {
    for (const [width, height, english, mode] of [[1440,900,false,'light'],[320,640,true,'dark'],[667,375,false,'dark']]) {
      await page.setViewportSize({ width, height })
      if (await isEnglish() !== english) await language.click()
      await theme.selectOption(mode)
      const locator = await w.locator('.workbench-locator select').boundingBox(), button = await help.boundingBox()
      if (locator && (Math.abs(locator.y - button.y) > 1 || locator.height !== button.height || button.x + button.width > width)) throw Error('Help and panel selector are not aligned')
      const before = await save.isEnabled()
      await help.focus(); await help.press('Enter')
      const dialog = page.getByRole('dialog', { name: english ? 'Flexible Panels help' : '灵活面板帮助' })
      await checkCloseButton(dialog)
      const copy = dialog.getByRole('button', { name: english ? 'Copy for agent' : '复制给 Agent' })
      const within = await copy.evaluate(el => {
        const r = el.getBoundingClientRect(), d = el.closest('dialog').getBoundingClientRect()
        return d.top >= 0 && d.bottom <= innerHeight + 1 && d.left >= 0 && d.right <= innerWidth + 1 &&
          el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2))
      })
      if (!within) throw Error('Copy action is clipped')
      const last = dialog.locator('li').last()
      await last.scrollIntoViewIfNeeded()
      if (!await last.evaluate(el => {
        const b = el.getBoundingClientRect()
        return el.contains(document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2))
      })) throw Error('Last example is obscured')
      const examples = await dialog.locator('li').allTextContents()
      await copy.click()
      await dialog.getByRole('status').filter({ hasText: english ? 'Copied.' : '已复制' }).waitFor()
      const copied = await page.evaluate(() => navigator.clipboard.readText())
      if (examples.length !== 3 || !examples.every(item => copied.includes(item)) || !copied.includes('references/agent-ui.md') || !copied.includes('gui_frontend_read')) throw Error('Incomplete clipboard guide')
      await page.keyboard.press('Escape')
      await dialog.waitFor({ state: 'detached' })
      if (!await help.evaluate(el => document.activeElement === el) || await save.isEnabled() !== before) throw Error('Help changed focus or layout')
      result.push({ width, height, english, examples: examples.length, clipboard: true })
    }
    // Layout libraries, panel settings and close confirmation share this dialog chrome.
    await w.getByTestId('load-layout').click()
    await checkCloseButton(page.getByRole('dialog'))
    await page.keyboard.press('Escape')
    const card = w.locator('article[data-grid-id]').first()
    const edit = w.locator('.workbench-actions button[aria-pressed]')
    const wasEditing = await edit.getAttribute('aria-pressed') === 'true'
    if (!wasEditing) await edit.click()
    try {
      await card.locator('.workbench-card-header button[aria-expanded]').click()
      await checkCloseButton(page.getByRole('dialog'))
      await page.keyboard.press('Escape')
    } finally { if (!wasEditing) await edit.click() }
    await card.getByRole('button', { name: /^(关闭面板|Close panel)$/ }).click()
    await checkCloseButton(page.getByRole('dialog'))
    await page.keyboard.press('Escape')
    const first = w.locator('article[data-grid-id] .panel-read').first()
    await first.click()
    await help.click()
    await page.keyboard.press('Escape')
    if (!await w.evaluate(el => el.classList.contains('is-reading'))) throw Error('Help closed the enlarged panel')
    await page.keyboard.press('Escape')
    return result
  } finally {
    await page.keyboard.press('Escape')
    if (await isEnglish() !== initialEnglish) await language.click()
    await theme.selectOption(initialTheme)
    if (size) await page.setViewportSize(size)
    await page.context().clearPermissions()
  }
}
