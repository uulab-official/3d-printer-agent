// The modeling studio shows one tab at a time (준비 · 시작점 · 출력 · 기록). A person clicks the
// tab before using a control on it; this helper does the same before every locator action:
// when the target sits in a hidden studio tab, it clicks that tab's real button first.
const ACTIONS = ['click', 'dblclick', 'fill', 'check', 'uncheck', 'setChecked', 'selectOption', 'setInputFiles',
  'press', 'pressSequentially', 'type', 'focus', 'hover', 'tap', 'scrollIntoViewIfNeeded', 'screenshot'];
const INSTALLED = Symbol('studioTabs');

async function openTabFor(locator) {
  await locator.evaluate((element) => {
    const panel = element.closest('[data-studio-panel]');
    if (panel && panel.hidden) document.querySelector(`[data-studio-tab="${panel.dataset.studioPanel}"]`).click();
    // The local connection and storage panel opens from the studio header's button.
    const local = element.closest('#local-runtime');
    const toggle = document.getElementById('studio-health-toggle');
    if (local && getComputedStyle(local).display === 'none' && toggle && toggle.offsetParent) toggle.click();
    // ...and, like a person clicking elsewhere, closes when the target is outside it.
    if (!local && toggle && toggle.getAttribute('aria-expanded') === 'true') toggle.click();
  }, undefined, { timeout: 5_000 }).catch(() => {});
}

function installStudioTabs(page) {
  const proto = Object.getPrototypeOf(page.locator('body'));
  if (proto[INSTALLED]) return;
  proto[INSTALLED] = true;
  // Visibility assertions: like a person, look at the tab that holds the element.
  const expectInternal = proto._expect;
  if (typeof expectInternal === 'function') {
    proto._expect = async function studioTabExpect(expression, options) {
      if (expression === 'to.be.visible' && !options?.isNot) await openTabFor(this);
      return expectInternal.call(this, expression, options);
    };
  }
  for (const name of ACTIONS) {
    const original = proto[name];
    proto[name] = async function studioTabAction(...args) {
      await openTabFor(this);
      return original.apply(this, args);
    };
  }
}

async function openStudioTab(page, name) {
  await page.locator(`[data-studio-tab="${name}"]`).click();
}

module.exports = { installStudioTabs, openStudioTab };
