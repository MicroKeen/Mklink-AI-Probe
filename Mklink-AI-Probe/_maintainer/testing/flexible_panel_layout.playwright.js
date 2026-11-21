// playwright-cli run-code --filename=<this file>, on a disposable official GUI session
// with a SuperWatch panel. Only presentation preferences and unsaved drafts are exercised.
async (page) => {
  const wb = page.getByTestId('workbench')
  const theme = page.getByTestId('theme-select')
  const toggle = page.getByTestId('global-language-toggle')
  const edit = wb.locator('.workbench-actions button[aria-pressed]')
  const initial = {
    theme: await theme.inputValue(),
    english: (await page.locator('html').getAttribute('lang')).startsWith('en'),
    editing: await edit.getAttribute('aria-pressed') === 'true',
    size: page.viewportSize(),
  }
  async function english() {
    return (await page.locator('html').getAttribute('lang')).startsWith('en')
  }
  const rows = []
  try {
    if (!initial.editing) await edit.click()
    for (const [width, mode, en] of [[320, 'light', true], [390, 'dark', false], [768, 'dark', false], [1440, 'light', true]]) {
      await page.setViewportSize({ width, height: width < 700 ? 780 : 900 })
      await theme.selectOption(mode)
      if (await english() !== en) await toggle.click()
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
      const geometry = await page.evaluate(() => {
        const rect = el => el.getBoundingClientRect()
        const within = (el, box) => rect(el).left >= box.left - 1 && rect(el).right <= box.right + 1
        const equalHeights = elements => new Set(Array.from(elements, el => rect(el).height)).size === 1
        const tabs = document.querySelector('.tabs-bar')
        const headers = [...document.querySelectorAll('.workbench-card-header')].filter(el => el.getClientRects().length)
        return {
          tab: within(tabs.querySelector('.active'), rect(tabs)),
          iconCenters: [...document.querySelectorAll('.workbench-card-header button,.control-widget>header button')]
            .filter(b => b.getClientRects().length && !b.textContent.trim() && b.querySelector('svg'))
            .every(b => {
              const box = rect(b), icon = rect(b.querySelector('svg'))
              return Math.abs(box.x + box.width / 2 - icon.x - icon.width / 2) <= 0.5 &&
                Math.abs(box.y + box.height / 2 - icon.y - icon.height / 2) <= 0.5
            }),
          cards: headers.length > 0 && headers.every(h => rect(h.querySelector('strong')).width >= 12 && [...h.querySelectorAll('button')].every(b => within(b, rect(h)))),
          quick: [...document.querySelectorAll('.title-right button')].filter(b => b.getClientRects().length).every(b => within(b, { left: 0, right: innerWidth })),
          status: rect(document.querySelector('.status-bar .badge')).height <= 32,
          toolbar: equalHeights(document.querySelector('.workbench-actions').children),
          preferences: equalHeights(document.querySelectorAll('.theme-setting select,.language-toggle')),
          page: document.documentElement.scrollWidth === innerWidth,
        }
      })
      if (!Object.values(geometry).every(Boolean)) throw Error(JSON.stringify({ width, mode, geometry }))
      const trigger = wb.locator('.workbench-card-header button[aria-expanded]').first()
      await trigger.click()
      const dialog = page.locator('dialog[open]')
      const fields = dialog.locator('.geometry-fields input')
      if (await fields.count() !== 4 || await fields.evaluateAll(inputs => inputs.some(input => input.getBoundingClientRect().width < 80))) throw Error('Unreadable geometry fields')
      const draft = dialog.locator('input').first()
      await draft.fill('Discard visual QA draft')
      await page.keyboard.press('Escape')
      await dialog.waitFor({ state: 'detached' })
      if (!await trigger.evaluate(el => el === document.activeElement) || await wb.getByText('Discard visual QA draft', { exact: true }).count()) throw Error('Settings focus or draft leaked')
      const menu = wb.locator('.watch-log-controls').first()
      await menu.locator('summary').click()
      const popup = menu.locator('.watch-log-menu')
      await popup.waitFor({ state: 'visible' })
      if (!await popup.evaluate(el => {
        const b = el.getBoundingClientRect()
        return b.left >= 0 && b.top >= 0 && b.right <= innerWidth + 1 && b.bottom <= innerHeight + 1 && el.contains(document.elementFromPoint(b.left + 12, b.top + 12))
      })) throw Error('Clipped or covered SuperWatch menu')
      await page.keyboard.press('Escape')
      if (!await menu.evaluate(el => !el.open && el.firstElementChild === document.activeElement)) throw Error('Menu focus')
      rows.push({ width, mode, language: en ? 'en' : 'zh' })
    }
    return rows
  } finally {
    await page.keyboard.press('Escape')
    if (!initial.editing && await edit.getAttribute('aria-pressed') === 'true') await edit.click()
    if (await english() !== initial.english) await toggle.click()
    await theme.selectOption(initial.theme)
    if (initial.size) await page.setViewportSize(initial.size)
  }
}
