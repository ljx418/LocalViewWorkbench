// Execute the unchanged production module with explicit Comfy/DOM substitutes.
// No browser, service, network or source media is used.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

async function fixture(uploadResponse = { ok: true, value: { video_reference: 'opaque.mp4' } }) {
  const elements = [], requests = [], listeners = new Map(), clipboard = [], downloads = [], urls = new Map();
  const element = (tag) => {
    const value = { tag, style: {}, children: [], files: [], disabled: false,
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      attributes: {}, setAttribute(name, value) { this.attributes[name] = value; },
      click() { if (tag === 'a') downloads.push({ name: this.download, blob: urls.get(this.href) }); } };
    elements.push(value); return value;
  };
  let extension;
  const app = { registerExtension(value) { extension = value; } };
  const api = {
    rejectClipboard: false,
    async workbench(body) {
      const fields = body.fields || { natural_zh: '', natural_en: 'machine English', image_prompt: 'machine image',
        video_prompt: 'machine video', tags: 'machine,tag', negative: '', edit_instruction: '' };
      const draft = { ...fields, tags: fields.tags.split(',').map((tag) => tag.trim()).filter(Boolean) };
      return { ok: true, value: { result: { schema_version: 'lvw.v0.result/1',
        run_id: body.action === 'adopt' ? body.run_token : null, source_type: body.action === 'adopt' ? 'video' : 'manual',
        draft, draft_origin: body.action === 'adopt' ? 'model_adopted' : 'manual', raw_response: 'bound raw' },
        txt: `manual_txt:${fields.natural_zh}` } };
    },
    addEventListener(name, handler) { listeners.set(name, handler); },
    removeEventListener(name, handler) { if (listeners.get(name) === handler) listeners.delete(name); },
    async fetchApi(url, options) {
      requests.push({ url, options });
      if (url.endsWith('/upload')) return { ok: uploadResponse.ok, json: async () => uploadResponse.value };
      if (url.endsWith('/workbench')) {
        const response = await api.workbench(JSON.parse(options.body));
        return { ok: response.ok, json: async () => response.value };
      }
      return { ok: true, json: async () => ({ status: 'idle', run_token: null }) };
    },
  };
  const context = vm.createContext({ document: { createElement: element },
    setTimeout: () => 1, clearTimeout() {}, AbortController, Blob,
    URL: { createObjectURL(blob) { const key = `blob:fixture-${urls.size}`; urls.set(key, blob); return key; },
      revokeObjectURL(key) { urls.delete(key); } },
    navigator: { clipboard: { async writeText(text) { if (api.rejectClipboard) throw new Error('clipboard denied'); clipboard.push(text); } } } });
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
  return { app, api, node, reference, requests, listeners, elements, clipboard, downloads, urls, input: elements.find((e) => e.tag === 'input'),
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

  const manual = await fixture();
  const field = (f, name) => f.elements.find((e) => e.attributes['data-lvw-field'] === name);
  const button = (f, label) => f.elements.find((e) => e.tag === 'button' && e.textContent === label);
  const edit = (f, name, value) => { const input = field(f, name); input.value = value; input.oninput(); };
  edit(manual, 'natural_zh', 'GPU忙时人工稿');
  manual.listeners.get('lvw.video.started')({ detail: { node_id: 1, run_token: 'busy-run' } });
  assert.equal(button(manual, '复制人工稿 TXT').disabled, false);
  await button(manual, '复制人工稿 TXT').onclick();
  assert.equal(manual.clipboard[0], 'manual_txt:GPU忙时人工稿');
  await button(manual, '导出人工稿 JSON').onclick();
  const exported = JSON.parse(await manual.downloads[0].blob.text());
  assert.equal(exported.source_type, 'manual'); assert.equal(exported.draft.natural_en, '');
  assert.equal(exported.draft.natural_zh, 'GPU忙时人工稿');
  manual.api.rejectClipboard = true;
  await button(manual, '复制人工稿 TXT').onclick();
  assert.equal(field(manual, 'natural_zh').value, 'GPU忙时人工稿');
  manual.node.onRemoved(); assert.equal(manual.urls.size, 0);

  const adoption = await fixture();
  adoption.listeners.get('lvw.video.started')({ detail: { node_id: 1, run_token: 'owned' } });
  adoption.node.onExecuted(message('owned', 'original raw'));
  assert.equal(field(adoption, 'natural_en').value, '');
  edit(adoption, 'natural_zh', 'preserve until explicit confirmation');
  let before = adoption.requests.length;
  await button(adoption, '采纳当前机器建议').onclick();
  assert.equal(adoption.requests.length, before);
  assert.equal(field(adoption, 'natural_zh').value, 'preserve until explicit confirmation');
  await button(adoption, '再次点击确认替换人工稿').onclick();
  assert.equal(field(adoption, 'natural_en').value, 'machine English');
  assert.equal(field(adoption, 'natural_zh').value, '');
  edit(adoption, 'natural_zh', 'edited after adoption');
  adoption.listeners.get('lvw.video.started')({ detail: { node_id: 1, run_token: 'next-run' } });
  assert.equal(field(adoption, 'natural_zh').value, 'edited after adoption');
  await button(adoption, '导出人工稿 JSON').onclick();
  const adoptedExport = JSON.parse(await adoption.downloads[0].blob.text());
  assert.equal(adoptedExport.run_id, 'owned'); assert.equal(adoptedExport.raw_response, 'bound raw');
  assert.equal(adoptedExport.draft_origin, 'edited'); assert.equal(adoptedExport.draft.natural_zh, 'edited after adoption');
  adoption.node.onRemoved();

  for (const scenario of ['edit', 'new-run', 'cancel', 'remove']) {
    const late = await fixture(); let resolveAdoption;
    const reply = late.api.workbench;
    late.api.workbench = (body) => body.action === 'adopt' ? new Promise((resolve) => { resolveAdoption = () => reply(body).then(resolve); }) : reply(body);
    late.listeners.get('lvw.video.started')({ detail: { node_id: 1, run_token: 'owned' } });
    late.node.onExecuted(message('owned', 'raw'));
    const pending = button(late, '采纳当前机器建议').onclick();
    if (scenario === 'edit') edit(late, 'natural_zh', 'typed while adoption pending');
    if (scenario === 'new-run') late.listeners.get('lvw.video.started')({ detail: { node_id: 1, run_token: 'new-run' } });
    if (scenario === 'cancel') await button(late, '取消本次视频分析').onclick();
    if (scenario === 'remove') {
      late.node.onRemoved();
      assert.equal(late.requests.find((r) => r.url.endsWith('/workbench')).options.signal.aborted, true);
    }
    resolveAdoption(); await pending;
    assert.equal(field(late, 'natural_zh').value, scenario === 'edit' ? 'typed while adoption pending' : '', scenario);
    assert.equal(field(late, 'natural_en').value, '', scenario); late.node.onRemoved();
  }
  const exporting = await fixture(); let resolveExport;
  const exportReply = exporting.api.workbench;
  exporting.api.workbench = (body) => new Promise((resolve) => { resolveExport = () => exportReply(body).then(resolve); });
  edit(exporting, 'natural_zh', 'snapshot at click');
  const pendingExport = button(exporting, '导出人工稿 TXT').onclick();
  edit(exporting, 'natural_zh', 'newer text'); resolveExport(); await pendingExport;
  assert.equal(field(exporting, 'natural_zh').value, 'newer text');
  assert.equal(await exporting.downloads[0].blob.text(), 'manual_txt:snapshot at click');
  exporting.node.onRemoved();
  console.log('PASS production video controls: upload, raw/suggestion, explicit confirmed adoption, late/cancel/graph guards, CPU manual copy/export while busy, adopted provenance, clipboard failure preservation and cleanup');
})().catch((error) => { console.error(error); process.exitCode = 1; });
