// Read-only synchronization with the pinned native host's completed setup and
// initial workflow load. No graph mutation, fixed sleep or pageerror suppression.
function hostReady() {
  const app = window.comfyAPI?.app?.app;
  return !!(app && typeof app.loadGraphData === 'function' && app.graph && app.canvas
    && window.app === app && window.graph === app.graph
    && app.configuringGraph === false && app.pendingGraphLoads instanceof Set
    && app.pendingGraphLoads.size === 0 && Number.isSafeInteger(app.graphLoadSequence)
    && app.graphLoadSequence > 0 && app.committedGraphLoadSequence === app.graphLoadSequence);
}

async function waitForHost(page) {
  return page.waitForFunction(hostReady, null, { timeout: 60000 });
}

async function dismissStartupTemplates(page) {
  // This pinned host opens its template selector for a fresh isolated user.
  // Close through the actual keyboard handler; never hide DOM or bypass focus.
  const templates = page.locator('[data-testid="template-workflows-content"]');
  await templates.waitFor({ state: 'visible', timeout: 30000 });
  await page.keyboard.press('Escape');
  await templates.waitFor({ state: 'hidden', timeout: 15000 });
  await waitForHost(page);
}
module.exports = { hostReady, waitForHost, dismissStartupTemplates };
