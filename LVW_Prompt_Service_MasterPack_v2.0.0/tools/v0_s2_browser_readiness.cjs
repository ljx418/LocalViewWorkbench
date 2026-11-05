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
module.exports = { hostReady, waitForHost };
