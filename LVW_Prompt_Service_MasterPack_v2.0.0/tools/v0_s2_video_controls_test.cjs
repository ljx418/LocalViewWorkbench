// Execute the unchanged production module with explicit Comfy/DOM substitutes.
// No browser, service, network or source media is used.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

async function fixture(uploadResponse = { ok: true, value: { video_reference: 'opaque.mp4' } }) {
  const elements = [], requests = [], listeners = new Map();
  const element = (tag) => {
    const value = { tag, style: {}, children: [], files: [], disabled: false,
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      setAttribute() {} };
    elements.push(value); return value;
  };
  let extension;
  const app = { registerExtension(value) { extension = value; } };
  const api = {
    addEventListener(name, handler) { listeners.set(name, handler); },
    removeEventListener(name, handler) { if (listeners.get(name) === handler) listeners.delete(name); },
    async fetchApi(url, options) {
      requests.push({ url, options });
      if (url.endsWith('/upload')) return { ok: uploadResponse.ok, json: async () => uploadResponse.value };
      return { ok: true, json: async () => ({ status: 'idle', run_token: null }) };
    },
  };
  const context = vm.createContext({ document: { createElement: element },
    setTimeout: () => 1, clearTimeout() {}, AbortController });
  const source = fs.readFileSync(path.join(__dirname, '../LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/web/video_controls.js'), 'utf8');
  const module = new vm.SourceTextModule(source, { context });
  await module.link((name) => {
    const key = name.endsWith('/app.js') ? 'app' : 'api';
    return new vm.SyntheticModule([key], function () { this.setExport(key, key === 'app' ? app : api); }, { context });
  });
  await module.evaluate();
  class Node { addDOMWidget() {} setDirtyCanvas() {} }
  await extension.beforeRegisterNodeDef(Node, { name: 'LVWVideoPromptOwner' });
  const node = new Node(); node.id = 1;
  const reference = { name: 'video_reference', value: 'previous.mp4' }; node.widgets = [reference];
  node.onNodeCreated(); await Promise.resolve();
  return { app, node, reference, requests, listeners, elements, input: elements.find((e) => e.tag === 'input'),
    status: elements.find((e) => e.tag === 'p') };
}

(async () => {
  const good = await fixture();
  const file = { name: 'synthetic.MP4', size: 6 };
  good.input.files = [file]; await good.input.onchange();
  const upload = good.requests.find((r) => r.url.endsWith('/upload'));
  assert.equal(upload.options.body, file);
  assert.equal(upload.options.headers['X-LVW-Control'], 'local-ui');
  assert.equal(upload.options.headers['X-LVW-Video-Extension'], '.mp4');
  assert.equal(good.reference.value, 'opaque.mp4');
  assert.equal(good.input.disabled, false);
  good.listeners.get('lvw.video.started')({ detail: { node_id: 1, run_token: 'owned' } });
  assert.equal(good.input.disabled, true);
  const [raw, suggestion] = good.elements.filter((e) => e.tag === 'pre');
  const message = (token, text) => ({ text: [text, JSON.stringify({ schema_version: 'lvw.prompt/1', text_en: 'sample' }),
    JSON.stringify({ run_token: token, cancel_epoch: 0 })] });
  good.node.onExecuted(message('old', 'stale result'));
  assert.equal(raw.textContent, '');
  good.listeners.get('lvw.video.preview')({ detail: { node_id: 1, run_token: 'old', images: [], frames: [] } });
  good.node.onExecuted(message('owned', '<script>untrusted model text</script>'));
  assert.equal(raw.textContent, '<script>untrusted model text</script>');
  assert.equal(raw.innerHTML, undefined);
  assert.equal(JSON.parse(suggestion.textContent).text_en, 'sample');
  await good.elements.find((e) => e.tag === 'button').onclick();
  good.node.onExecuted(message('owned', 'late cancelled response'));
  assert.equal(raw.textContent, '<script>untrusted model text</script>');
  good.node.onRemoved(); assert.equal(good.listeners.size, 0);

  const bad = await fixture({ ok: false, value: { error: { message: 'upload rejected' } } });
  bad.input.files = [file]; await bad.input.onchange();
  assert.equal(bad.reference.value, 'previous.mp4'); assert.equal(bad.status.textContent, 'upload rejected');
  const count = bad.requests.filter((r) => r.url.endsWith('/upload')).length;
  bad.input.files = [{ name: 'large.mp4', size: 256 * 1024 * 1024 + 1 }]; await bad.input.onchange();
  assert.equal(bad.requests.filter((r) => r.url.endsWith('/upload')).length, count);
  assert.equal(bad.reference.value, 'previous.mp4'); bad.node.onRemoved();
  const inactive = await fixture(); inactive.node.graph = {}; inactive.app.graph = {};
  inactive.listeners.get('lvw.video.started')({ detail: { node_id: 1, run_token: 'other-graph' } });
  assert.equal(inactive.input.disabled, false);
  inactive.app.graph = inactive.node.graph;
  inactive.listeners.get('lvw.video.started')({ detail: { node_id: 1, run_token: 'owned-graph' } });
  assert.equal(inactive.input.disabled, true); inactive.node.onRemoved();
  console.log('PASS production video controls: upload binding, failure preservation, one-over rejection, run lock, client/graph scope, raw/suggestion display, stale/cancelled result rejection, listener cleanup');
})().catch((error) => { console.error(error); process.exitCode = 1; });
