// Native Comfy product UI worker. Launch only under a sealed program child and
// a live parent supervisor. Importing this module opens no browser or network.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const readline = require('node:readline');
const crypto = require('node:crypto');
const { ORIGIN, BUDGET, ACTIONS, validateConfig, classify, apiPath, Counter, replyFor, digest } = require('./v0_s2_browser_policy.cjs');
const FIELDS = Object.freeze({ natural_zh: '浏览器人工稿：保留蓝色陶瓷杯', natural_en: 'Human draft: blue ceramic cup',
  image_prompt: 'a blue ceramic cup', video_prompt: 'static camera, ceramic cup', tags: '人工,local', negative: 'blur', edit_instruction: '保留构图' });
const CASES = ['manual-initial', 'upload', 'native-analysis', 'busy-manual', 'explicit-adoption', 'exports-clipboard',
  'late-adoption-new-run-cancel', 'offline-manual', 'node-removal'];

function parentBridge(config, input = process.stdin, output = process.stdout) {
  const pending = new Map(); let sequence = 0, closed = false;
  const controller = new AbortController();
  const lines = readline.createInterface({ input, crlfDelay: Infinity });
  function stop(error) { closed = true; controller.abort(error); for (const p of pending.values()) { clearTimeout(p.timer); p.reject(error); } pending.clear(); }
  lines.on('line', line => {
    try {
      if (Buffer.byteLength(line) > 65536) throw new Error('BROWSER_PARENT_REPLY_LIMIT');
      const reply = JSON.parse(line), item = pending.get(reply.sequence);
      if (!item) throw new Error('BROWSER_PARENT_REPLY_REPLAY');
      const payload = replyFor(config, reply.sequence, reply);
      clearTimeout(item.timer); pending.delete(reply.sequence); item.resolve(payload);
    } catch (error) { stop(error); }
  });
  lines.on('close', () => stop(new Error('BROWSER_PARENT_DISCONNECTED')));
  lines.on('error', stop); output.on('error', stop);
  return { signal: controller.signal, async request(action, payload = {}) {
    if (closed || !ACTIONS.has(action) || sequence >= 512 || pending.size >= 8 || Date.now() / 1000 >= config.expires_at) throw new Error('BROWSER_PARENT_PROTOCOL_BOUND');
    const id = ++sequence;
    const packet = { kind: 'lvw.s2.browser-parent-request/1', sequence: id, protocol_nonce: config.protocol_nonce,
      candidate_sha: config.candidate_sha, authorization_sha256: config.authorization_sha256, action, payload };
    const encoded = JSON.stringify(packet);
    if (Buffer.byteLength(encoded) > 65536) throw new Error('BROWSER_PARENT_REQUEST_LIMIT');
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(new Error('BROWSER_PARENT_TIMEOUT:' + action)); },
        action === 'offline_op' ? 1200000 : action === 'case_finished' ? 60000 : 20000);
      pending.set(id, { resolve, reject, timer }); output.write(encoded + '\n');
    });
  }, close() { stop(new Error('BROWSER_WORKER_CLOSED')); lines.close(); } };
}

function regular(file, maximum) {
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > maximum) throw new Error('BROWSER_BOUND_FILE_INVALID');
  return fs.readFileSync(file);
}

function fileIdentity(file, maximum, kernelLink = false) {
  const stat = fs.lstatSync(file);
  if ((!stat.isFile() || stat.isSymbolicLink()) && !(kernelLink && /^\/proc\/[1-9][0-9]*\/exe$/.test(file))) throw new Error('BROWSER_BOUND_FILE_INVALID');
  const fd = fs.openSync(file, fs.constants.O_RDONLY | (kernelLink ? 0 : fs.constants.O_NOFOLLOW));
  try {
    const before = fs.fstatSync(fd); if (!before.isFile() || before.size > maximum) throw new Error('BROWSER_BOUND_FILE_LIMIT');
    const hash = crypto.createHash('sha256'), buffer = Buffer.alloc(65536), header = Buffer.alloc(4); let total = 0, count;
    while ((count = fs.readSync(fd, buffer, 0, buffer.length, null)) !== 0) {
      if (total === 0) buffer.copy(header, 0, 0, Math.min(count, 4));
      total += count; if (total > maximum) throw new Error('BROWSER_BOUND_FILE_LIMIT'); hash.update(buffer.subarray(0, count));
    }
    const after = fs.fstatSync(fd);
    if (total !== before.size || after.size !== before.size || after.mtimeMs !== before.mtimeMs || after.ino !== before.ino) throw new Error('BROWSER_FILE_CHANGED');
    return { bytes: total, sha256: hash.digest('hex'), header: header.toString('hex') };
  } finally { fs.closeSync(fd); }
}

function birth(pid) {
  const text = fs.readFileSync(`/proc/${pid}/stat`, 'utf8');
  const rest = text.slice(text.lastIndexOf(')') + 2).trim().split(/\s+/);
  return { pid, state: rest[0], parent: Number(rest[1]), group: Number(rest[2]), session: Number(rest[3]), start_ticks: rest[19] };
}

function groupMembers(group) {
  const entries = fs.readdirSync('/proc').filter(name => /^\d+$/.test(name));
  if (entries.length > 8192) throw new Error('BROWSER_PROCESS_CATALOG_LIMIT');
  const members = [];
  for (const name of entries) {
    try { const p = birth(Number(name)); if (p.group === group) members.push(p); }
    catch (error) { if (error.code !== 'ENOENT' && error.code !== 'ESRCH') throw error; }
  }
  if (members.length > 64) throw new Error('BROWSER_PROCESS_GROUP_LIMIT');
  return members;
}

async function run(config, parent, dependencies = {}) {
  validateConfig(config);
  if (!parent || typeof parent.request !== 'function') throw new Error('LIVE_PARENT_REQUIRED');
  let root;
  try {
    const preflight = await parent.request('preflight', { run_root: config.run_root });
    root = fs.realpathSync(config.run_root);
    if (preflight.owned_run_root !== root) throw new Error('BROWSER_PARENT_ROOT_MISMATCH');
  } catch (error) {
    // The formal parent records this rejected attempt. No unapproved directory,
    // media/executable read or browser process is created by the worker.
    return { kind: 'NATIVE_COMFY_BROWSER_NOT_STAGE_ACCEPTANCE', candidate_sha: config.candidate_sha,
      authorization_sha256: config.authorization_sha256, run_id: config.run_id, decision: 'NO_GO', stage_pass_claim: false,
      error_code: error.message, cases: Object.fromEntries(CASES.map(c => [c, 'NOT_RUN'])),
      counts: { fixed: CASES.length, PASS: 0, FAIL: 0, NOT_RUN: CASES.length }, browser_starts: 0 };
  }
  const directory = path.join(root, 'temp/browser-phase');
  const evidence = path.join(directory, 'evidence'); fs.mkdirSync(evidence, { recursive: false });
  const counter = new Counter(), artifacts = [], network = [], faults = [], cases = Object.fromEntries(CASES.map(c => [c, 'NOT_RUN']));
  let server, browser, context, child, processBirth, profile, profileIdentity, releaseHeld, holdTimer, state = { armed: false }, fatal, active;
  const result = { kind: 'NATIVE_COMFY_BROWSER_NOT_STAGE_ACCEPTANCE', candidate_sha: config.candidate_sha,
    authorization_sha256: config.authorization_sha256, run_id: config.run_id, cases, decision: 'NO_GO', stage_pass_claim: false, action_count: 0 };
  const artifact = (name, value) => {
    const raw = Buffer.isBuffer(value) ? value : Buffer.from(JSON.stringify(value, null, 2) + '\n');
    if (raw.length > 24 * 1024 * 1024) throw new Error('BROWSER_ARTIFACT_LIMIT');
    fs.writeFileSync(path.join(evidence, name), raw, { flag: 'wx' });
    artifacts.push({ file: name, bytes: raw.length, sha256: digest(raw) });
  };
  const action = (name, payload = {}) => {
    const raw = JSON.stringify({ ordinal: ++result.action_count, name, payload }) + '\n';
    const fd = fs.openSync(path.join(directory, 'actions.jsonl'), 'a');
    try { fs.writeSync(fd, raw); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  };
  const permit = async (name, payload) => { action('parent:' + name, payload); return parent.request(name, payload); };
  const assertHealthy = () => { if (fatal) throw fatal; if (Date.now() / 1000 >= config.expires_at) throw new Error('BROWSER_LEASE_EXPIRED'); };
  const pass = name => { cases[name] = 'PASS'; artifact(name + '.json', { status: 'PASS', stage_pass_claim: false }); };
  let page, actualQueues = [], adopted;
  const parentAborted = () => { fatal = parent.signal.reason || new Error('BROWSER_PARENT_ABORTED'); if (server) server.close().catch(() => {}); };
  parent.signal?.addEventListener('abort', parentAborted, { once: true });
  try {
    action('parent:preflight', { approved_before_directory_writes: true }); assertHealthy();
    const project = path.resolve(__dirname, '..'), policyPath = path.join(__dirname, 'v0_s2_browser_policy.cjs');
    const workflowPath = path.join(project, 'LVW_V0_RuntimePatch/workflows/video_reverse_prompt_v0.ui.json');
    if (digest(fs.readFileSync(__filename)) !== config.harness_sha256 || digest(fs.readFileSync(policyPath)) !== config.policy_sha256
        || digest(fs.readFileSync(workflowPath)) !== config.ui_workflow_sha256) throw new Error('BROWSER_SOURCE_BINDING_MISMATCH');
    const samplePath = fs.realpathSync(config.sample_path);
    if (!samplePath.startsWith(path.join(root, 'input') + path.sep)) throw new Error('BROWSER_SAMPLE_OUTSIDE_OWNED_INPUT');
    const sample = fileIdentity(config.sample_path, 8 * 1024 * 1024), executable = fileIdentity(config.browser_executable, 1024 * 1024 * 1024);
    if (sample.bytes !== config.sample_bytes || sample.sha256 !== config.sample_sha256 || executable.sha256 !== config.browser_executable_sha256
        || executable.header !== '7f454c46' || process.platform !== 'linux') throw new Error('BROWSER_LOCAL_BINDING_MISMATCH');
    if (fileIdentity(config.playwright_module, 4 * 1024 * 1024).sha256 !== config.playwright_entry_sha256) throw new Error('BROWSER_SDK_ENTRY_MISMATCH');
    const launchPermit = await permit('browser_start', { sample_sha256: sample.sha256, executable_sha256: executable.sha256 });
    if (launchPermit.ephemeral_user_root_verified !== true || !Number.isInteger(launchPermit.comfy_pid) || launchPermit.comfy_pid <= 0) throw new Error('EPHEMERAL_COMFY_USER_ROOT_NOT_PROVEN');
    assertHealthy(); counter.charge('browser_starts'); action('launch_headless');
    const { chromium } = dependencies.playwright || require(config.playwright_module);
    server = await chromium.launchServer({ host: '127.0.0.1', port: 0, headless: true, executablePath: config.browser_executable,
      args: ['--disable-gpu', '--disable-background-networking', '--disable-component-update', '--disable-sync', '--no-first-run', '--disable-extensions', '--no-proxy-server'] });
    assertHealthy();
    child = server.process(); processBirth = birth(child.pid);
    if (processBirth.group !== child.pid || processBirth.session !== child.pid || fs.realpathSync(`/proc/${child.pid}/exe`) !== fs.realpathSync(config.browser_executable)) throw new Error('BROWSER_PROCESS_OWNERSHIP_UNPROVEN');
    if (fileIdentity(`/proc/${child.pid}/exe`, 1024 * 1024 * 1024, true).sha256 !== config.browser_executable_sha256) throw new Error('BROWSER_RUNNING_EXECUTABLE_MISMATCH');
    const profileArg = child.spawnargs.find(arg => arg.startsWith('--user-data-dir=')); profile = profileArg?.slice('--user-data-dir='.length);
    if (!profile || path.dirname(profile) !== os.tmpdir() || !path.basename(profile).startsWith('playwright_chromiumdev_profile-')) throw new Error('BROWSER_FRESH_PROFILE_UNPROVEN');
    profileIdentity = fs.lstatSync(profile);
    if (!profileIdentity.isDirectory() || profileIdentity.isSymbolicLink() || profileIdentity.uid !== process.getuid()) throw new Error('BROWSER_PROFILE_OWNERSHIP_INVALID');
    const ws = new URL(server.wsEndpoint()); if (ws.hostname !== '127.0.0.1') throw new Error('BROWSER_DRIVER_NON_LOOPBACK');
    artifact('browser-owner.json', { ...processBirth, executable_sha256: config.browser_executable_sha256,
      fresh_profile: true, profile_relative_name: path.basename(profile), profile_inode: profileIdentity.ino, profile_device: profileIdentity.dev });
    await permit('browser_owner', { ...processBirth, executable_sha256: config.browser_executable_sha256,
      profile_relative_name: path.basename(profile), profile_inode: profileIdentity.ino, profile_device: profileIdentity.dev });
    browser = await chromium.connect(server.wsEndpoint());
    context = await browser.newContext({ viewport: { width: 1600, height: 1200 }, locale: 'zh-CN', serviceWorkers: 'block', acceptDownloads: true });
    if (typeof context.routeWebSocket !== 'function') throw new Error('BROWSER_WEBSOCKET_GUARD_UNAVAILABLE');
    await context.routeWebSocket('**/*', async route => {
      const url = new URL(route.url());
      if (url.protocol === 'ws:' && url.host === '127.0.0.1:8191' && url.pathname === '/ws') return route.connectToServer();
      fatal = new Error('BROWSER_FOREIGN_WEBSOCKET'); faults.push({ code: fatal.message }); await route.close({ code: 1008, reason: 'local-only' });
    });
    await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: ORIGIN });
    let heldPromise, heldReady, holding = false;
    await context.route('**/*', async route => {
      try {
        assertHealthy(); const req = route.request(), raw = req.postDataBuffer();
        const isUpload = apiPath(new URL(req.url()).pathname) === '/lvw/v0/video/upload';
        if (raw && raw.length > (isUpload ? 8 * 1024 * 1024 : 1024 * 1024)) throw new Error('BROWSER_REQUEST_LIMIT');
        const body = raw && !isUpload ? JSON.parse(raw.toString('utf8')) : null;
        const classified = classify(req.url(), req.method(), body, state);
        if (network.length >= 8192) throw new Error('BROWSER_NETWORK_LEDGER_LIMIT');
        network.push({ method: req.method(), pathname: classified.pathname, kind: classified.kind, body_sha256: raw ? digest(raw) : null });
        if (classified.kind !== 'read') {
          counter.charge(classified.kind); action(classified.kind, { pathname: classified.pathname, body_sha256: raw ? digest(raw) : null });
          if (classified.kind === 'uploads') {
            if (digest(raw) !== config.sample_sha256 || raw.length !== config.sample_bytes) throw new Error('BROWSER_UPLOAD_BYTES_CHANGED');
            await permit('upload', { bytes: raw.length, sha256: digest(raw) });
          }
          if (classified.kind === 'public_submissions') {
            const armed = state.armed; state.armed = false;
            await permit('public_submit', { case_id: armed, body });
            actualQueues.push({ case_id: armed, body });
          }
          if (classified.kind === 'user_writes') await permit('user_write', { pathname: classified.pathname, method: req.method(), bytes: raw?.length || 0 });
        }
        assertHealthy();
        if (classified.kind === 'adoptions' && holding) {
          holding = false; counter.charge('held_responses');
          const response = await route.fetch({ timeout: 10000 }), bytes = await response.body();
          if (response.status() !== 200 || bytes.length > 24 * 1024 * 1024) throw new Error('BROWSER_HELD_ADOPTION_NOT_REAL_SUCCESS');
          artifact('held-adoption-original.json', { status: response.status(), raw_utf8: bytes.toString('utf8'), sha256: digest(bytes) });
          heldReady(); await heldPromise;
          await route.fulfill({ response, body: bytes }); artifact('held-adoption-forwarded.json', { sha256: digest(bytes), bytes: bytes.length });
          return;
        }
        return route.continue();
      } catch (error) { fatal = error; faults.push({ code: error.message }); await route.abort('blockedbyclient').catch(() => {}); }
    });
    page = await context.newPage(); page.setDefaultTimeout(15000);
    page.on('pageerror', error => { faults.push({ code: 'PAGE_ERROR', message: error.message }); fatal = error; });
    await page.goto(ORIGIN, { waitUntil: 'domcontentloaded', timeout: 60000 });
    // The inspected installed scripts/app.js is a window.comfyAPI shim; DOM
    // readiness alone does not mean its asynchronous app/graph boot completed.
    await page.waitForFunction(() => typeof window.comfyAPI?.app?.app?.loadGraphData === 'function'
      && window.comfyAPI.app.app.graph && window.comfyAPI.app.app.canvas && window.comfyAPI?.api?.api,
      null, { timeout: 60000 });
    await page.evaluate(async graph => { const { app } = await import('/scripts/app.js'); await app.loadGraphData(graph); }, JSON.parse(fs.readFileSync(workflowPath, 'utf8')));
    const field = name => page.locator(`[data-lvw-field="${name}"]`), button = label => page.getByRole('button', { name: label, exact: true });
    const readFields = async () => Object.fromEntries(await Promise.all(Object.keys(FIELDS).map(async k => [k, await field(k).inputValue()])));
    const fill = async values => { for (const [k, v] of Object.entries(values)) await field(k).fill(v); };
    const same = (a, b, reason) => { if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(reason); };
    const download = async (label, name) => {
      counter.charge('downloads'); action('download', { name });
      const waiting = page.waitForEvent('download'); await button(label).click(); const item = await waiting;
      const target = path.join(evidence, name); await item.saveAs(target); const raw = regular(target, 24 * 1024 * 1024);
      artifacts.push({ file: name, bytes: raw.length, sha256: digest(raw) }); return raw;
    };
    active = 'manual-initial'; await fill(FIELDS);
    const initial = JSON.parse(await download('导出人工稿 JSON', 'manual-initial-export.json'));
    same(initial.draft, { ...FIELDS, tags: ['人工', 'local'] }, 'INITIAL_MANUAL_DRAFT_CHANGED');
    if (initial.source_type !== 'manual' || initial.run_id !== null || initial.source !== null || initial.raw_response !== null
        || initial.suggestion !== null || initial.draft_origin !== 'manual') throw new Error('INITIAL_MANUAL_PROVENANCE'); pass(active);
    active = 'upload';
    const responseFor = endpoint => r => { const u = new URL(r.url()); return u.origin === ORIGIN && apiPath(u.pathname) === endpoint && r.request().method() === 'POST'; };
    const uploaded = page.waitForResponse(responseFor('/lvw/v0/video/upload'));
    await page.getByLabel('选择并上传 MP4 或 MOV 视频，最大 256 MiB、60 秒', { exact: true }).setInputFiles(config.sample_path);
    const uploadResponse = await uploaded, uploadBody = await uploadResponse.json();
    if (uploadResponse.status() !== 201 || typeof uploadBody.video_reference !== 'string') throw new Error('NATIVE_UI_UPLOAD_FAILED');
    state.reference = uploadBody.video_reference; artifact('upload-response.json', uploadBody); pass(active);
    const queue = async name => {
      await permit('case_begin', { case_id: name }); state.armed = name;
      const waiting = page.waitForResponse(responseFor('/prompt'));
      await page.locator('canvas').first().click({ position: { x: 20, y: 20 } }); await page.keyboard.press('Control+Enter');
      const response = await waiting, value = await response.json(); assertHealthy();
      if (response.status() !== 200 || !/^[0-9a-f-]{1,80}$/i.test(value.prompt_id || '')) throw new Error('NATIVE_UI_QUEUE_FAILED');
      const record = actualQueues[actualQueues.length - 1]; record.prompt_id = value.prompt_id;
      artifact(name + '-public-queue.json', record); await permit('case_queued', record); return record;
    };
    active = 'native-analysis'; const first = await queue('complete');
    active = 'busy-manual'; await permit('busy_manual', { prompt_id: first.prompt_id });
    const busy = JSON.parse(await download('导出人工稿 JSON', 'busy-manual-export.json'));
    same(busy.draft, initial.draft, 'BUSY_MANUAL_CHANGED'); pass(active);
    active = 'native-analysis';
    await page.waitForFunction(() => {
      if ([...document.querySelectorAll('p')].some(p => /任务：(failed|cancelled)/.test(p.textContent))) throw new Error('NATIVE_UI_ANALYSIS_FAILED');
      return [...document.querySelectorAll('button')].some(b => b.textContent === '采纳当前机器建议' && !b.disabled);
    }, null, { timeout: 480000 });
    same(await readFields(), FIELDS, 'MACHINE_OVERWROTE_DIRTY_DRAFT');
    const rawUi = await page.locator('details').filter({ has: page.locator('summary', { hasText: '模型原始响应（采样帧）' }) }).locator('pre').textContent();
    artifact('raw-visible.json', { text: rawUi, sha256: digest(Buffer.from(rawUi)) });
    const complete = await permit('case_finished', { case_id: 'analysis_before_adoption', prompt_id: first.prompt_id, raw_sha256: digest(Buffer.from(rawUi)) });
    if (typeof complete.run_token !== 'string' || !complete.run_token) throw new Error('PARENT_ANALYSIS_TOKEN_MISSING');
    state.adoptToken = complete.run_token; pass(active);
    active = 'explicit-adoption'; const adoptionCount = counter.used.adoptions;
    await button('采纳当前机器建议').click();
    if (counter.used.adoptions !== adoptionCount) throw new Error('ADOPTION_WITHOUT_SECOND_CONFIRMATION');
    const adoptionResponse = page.waitForResponse(responseFor('/lvw/v0/video/workbench'));
    await button('再次点击确认替换人工稿').click();
    const actualAdoption = await adoptionResponse, adoptionBytes = await actualAdoption.body();
    if (actualAdoption.status() !== 200 || adoptionBytes.length > 24 * 1024 * 1024) throw new Error('NATIVE_ADOPTION_RESPONSE_INVALID');
    artifact('adoption-response.json', adoptionBytes);
    await page.getByRole('status').filter({ hasText: '已显式采纳' }).waitFor();
    adopted = await readFields(); if (!adopted.natural_en.trim()) throw new Error('EMPTY_ADOPTED_PROMPT');
    artifact('adopted-fields.json', adopted); pass(active);
    active = 'exports-clipboard';
    await button('复制人工稿 TXT').click(); await page.getByRole('status').filter({ hasText: '人工稿已复制或导出' }).waitFor();
    const clipboard = await page.evaluate(() => navigator.clipboard.readText());
    artifact('clipboard.txt', Buffer.from(clipboard));
    if (!clipboard.includes(adopted.natural_en)) throw new Error('NATIVE_CLIPBOARD_MISMATCH');
    const exportBytes = await download('导出人工稿 JSON', 'adopted-export.json'), exported = JSON.parse(exportBytes);
    if (exported.source_type !== 'video' || exported.source.sha256 !== config.sample_sha256 || exported.raw_response !== rawUi) throw new Error('ADOPTED_EXPORT_PROVENANCE_MISMATCH');
    const firstToken = exported.run_id;
    if (firstToken !== state.adoptToken) throw new Error('ADOPTED_TOKEN_DIFFERS_FROM_NATIVE_JOIN');
    await permit('case_finished', { case_id: 'complete', prompt_id: first.prompt_id, export_file: 'adopted-export.json', raw_sha256: digest(Buffer.from(rawUi)) });
    const txt = (await download('导出人工稿 TXT', 'adopted-export.txt')).toString('utf8');
    if (txt !== clipboard) throw new Error('TXT_CLIPBOARD_DIFFER');
    await page.evaluate(() => { window.__lvwClipboardDescriptor = Object.getOwnPropertyDescriptor(navigator.clipboard, 'writeText');
      Object.defineProperty(navigator.clipboard, 'writeText', { configurable: true, value: async () => { throw new Error('LVW controlled clipboard denial'); } }); });
    await button('复制人工稿 TXT').click(); await page.getByRole('status').filter({ hasText: 'LVW controlled clipboard denial' }).waitFor();
    same(await readFields(), adopted, 'CLIPBOARD_FAILURE_CHANGED_DRAFT');
    await page.evaluate(() => { if (window.__lvwClipboardDescriptor) Object.defineProperty(navigator.clipboard, 'writeText', window.__lvwClipboardDescriptor);
      else delete navigator.clipboard.writeText; delete window.__lvwClipboardDescriptor; }); pass(active);
    active = 'late-adoption-new-run-cancel'; const edited = { ...adopted, natural_zh: '人工修改：等待采纳时保留，不被新运行或取消覆盖' }; await fill(edited);
    heldPromise = new Promise(resolve => { releaseHeld = resolve; }); const ready = new Promise(resolve => { heldReady = resolve; }); holding = true;
    holdTimer = setTimeout(() => { fatal = new Error('BROWSER_ADOPTION_HOLD_DEADLINE'); releaseHeld?.(); }, 150000);
    await button('采纳当前机器建议').click(); await button('再次点击确认替换人工稿').click();
    await Promise.race([ready, new Promise((_, reject) => setTimeout(() => reject(new Error('ADOPTION_HOLD_TIMEOUT')), 10000))]);
    await field('natural_zh').fill(edited.natural_zh + '；请求期间继续编辑'); edited.natural_zh += '；请求期间继续编辑';
    const second = await queue('cancel');
    let cancellation; const readyDeadline = process.hrtime.bigint() + 120000000000n;
    for (let i = 0; i < 240; i++) {
      if (process.hrtime.bigint() >= readyDeadline) break;
      cancellation = await permit('cancel_ready', { prompt_id: second.prompt_id });
      if (cancellation.ready === true) break; await page.waitForTimeout(500);
    }
    if (!cancellation?.ready || typeof cancellation.run_token !== 'string') throw new Error('NATIVE_UI_CANCEL_WINDOW_MISSED');
    state.cancelToken = cancellation.run_token;
    const cancelResponse = page.waitForResponse(responseFor('/lvw/v0/video/cancel'));
    const cancelStart = process.hrtime.bigint(); await button('取消本次视频分析').click();
    const cancelled = await cancelResponse, ack = await cancelled.json(), elapsed = Number(process.hrtime.bigint() - cancelStart) / 1e9;
    if (cancelled.status() !== 200 || ack.run_token !== state.cancelToken || ack.cancel_epoch !== 1 || elapsed > 1) throw new Error('NATIVE_UI_CANCEL_FEEDBACK_INVALID');
    artifact('cancel-ack.json', { http_status: cancelled.status(), response: ack, elapsed_seconds: elapsed });
    releaseHeld(); releaseHeld = null; clearTimeout(holdTimer);
    await page.getByRole('status').filter({ hasText: '未应用迟到的采纳结果' }).waitFor();
    same(await readFields(), edited, 'LATE_ADOPTION_OR_CANCEL_OVERWROTE_DRAFT');
    await permit('case_finished', { case_id: 'cancel', prompt_id: second.prompt_id, acknowledgement_file: 'cancel-ack.json' });
    const final = JSON.parse(await download('导出人工稿 JSON', 'after-cancel-export.json'));
    if (final.run_id !== firstToken || final.draft.natural_zh !== edited.natural_zh || final.draft_origin !== 'edited') throw new Error('ADOPTED_SNAPSHOT_LOST_AFTER_CANCEL'); pass(active);
    active = 'offline-manual';
    const offline = await permit('offline_op', { require_owned_ollama_stopped: true });
    if (offline.owned_ollama_stopped !== true || offline.comfy_pid !== launchPermit.comfy_pid) throw new Error('OFFLINE_UI_PHASE_NOT_PROVEN');
    const offlineExport = JSON.parse(await download('导出人工稿 JSON', 'offline-export.json'));
    if (offlineExport.draft.natural_zh !== edited.natural_zh || offlineExport.run_id !== firstToken) throw new Error('OFFLINE_UI_DRAFT_CHANGED'); pass(active);
    active = 'node-removal';
    await page.screenshot({ path: path.join(evidence, 'native-workbench.png'), fullPage: true });
    const screenshot = regular(path.join(evidence, 'native-workbench.png'), 24 * 1024 * 1024);
    artifacts.push({ file: 'native-workbench.png', bytes: screenshot.length, sha256: digest(screenshot) });
    await page.evaluate(async () => { const { app } = await import('/scripts/app.js'); app.graph.remove(app.graph.getNodeById(1)); });
    if (await page.locator('[data-lvw-field]').count() !== 0) throw new Error('REMOVED_NODE_EDITORS_REMAIN'); pass(active);
    assertHealthy(); result.decision = 'BROWSER_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE';
  } catch (error) { if (active) cases[active] = 'FAIL'; result.error_code = error.message; }
  finally {
    parent.signal?.removeEventListener('abort', parentAborted);
    clearTimeout(holdTimer);
    releaseHeld?.();
    const cleanup = { browser_original_absent: false, group_empty: false, profile_absent: false };
    try {
      const bounded = async (operation, milliseconds) => {
        let timer;
        try { return await Promise.race([operation, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('BROWSER_CLOSE_TIMEOUT')), milliseconds); })]); }
        finally { clearTimeout(timer); }
      };
      if (server) {
        try { await bounded(server.close(), 15000); }
        catch (error) { cleanup.graceful_error = error.message; await bounded(server.kill(), 5000); }
      }
      cleanup.browser_original_absent = !child || child.exitCode !== null || child.signalCode !== null;
      cleanup.group_empty = !server || (processBirth && groupMembers(processBirth.group).length === 0) || false;
      if (profile && fs.existsSync(profile) && cleanup.group_empty && cleanup.browser_original_absent) {
        const current = fs.lstatSync(profile);
        if (!profileIdentity || current.ino !== profileIdentity.ino || current.dev !== profileIdentity.dev || current.isSymbolicLink()) throw new Error('BROWSER_PROFILE_CHANGED_BEFORE_CLEANUP');
        fs.rmSync(profile, { recursive: true }); cleanup.owned_profile_removed = true;
      }
      cleanup.profile_absent = !server || (!!profile && !fs.existsSync(profile));
    } catch (error) { cleanup.error = error.message; }
    if (Object.values(cleanup).some(v => v === false)) result.decision = 'NO_GO';
    if (fatal) { result.decision = 'NO_GO'; result.error_code = fatal.message; }
    artifact('network.json', network); artifact('faults.json', faults); artifact('browser-cleanup.json', cleanup);
    result.counts = { fixed: CASES.length, PASS: Object.values(cases).filter(v => v === 'PASS').length,
      FAIL: Object.values(cases).filter(v => v === 'FAIL').length, NOT_RUN: Object.values(cases).filter(v => v === 'NOT_RUN').length };
    if (result.decision === 'BROWSER_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE' && (result.counts.PASS !== CASES.length
        || ['uploads', 'public_submissions', 'previews', 'adoptions', 'cancellations', 'held_responses', 'downloads'].some(k => counter.used[k] !== BUDGET[k]))) {
      result.decision = 'NO_GO'; result.error_code = 'BROWSER_INCOMPLETE_FIXED_DENOMINATOR';
    }
    result.budget_used = counter.used; result.cleanup = cleanup; result.artifacts = artifacts.slice(); artifact('browser-result.json', result);
  }
  return result;
}

module.exports = { run, parentBridge, birth, groupMembers, fileIdentity, FIELDS, CASES };
if (require.main === module) {
  (async () => {
    if (process.argv.length !== 4 || process.argv[2] !== '--config') throw new Error('SEALED_PARENT_CONFIG_REQUIRED');
    const config = JSON.parse(regular(process.argv[3], 65536)); validateConfig(config);
    const bridge = parentBridge(config);
    try { const result = await run(config, bridge); process.exitCode = result.decision === 'BROWSER_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE' ? 0 : 1; }
    finally { bridge.close(); }
  })().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
}
