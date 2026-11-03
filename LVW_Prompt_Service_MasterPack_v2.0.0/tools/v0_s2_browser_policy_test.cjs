// Offline protocol/file/route tests only. Never loads Playwright or starts UI.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { PassThrough } = require('node:stream');
const { ORIGIN, BUDGET, validateConfig, classify, Counter, replyFor, digest } = require('./v0_s2_browser_policy.cjs');
const { run, parentBridge, fileIdentity, CASES } = require('./v0_s2_browser_acceptance.cjs');
const results = [];
const check = async (name, fn) => { await fn(); results.push({ name, passed: true }); };
const config = () => ({ schema_version: 'lvw.s2.browser-config/1', run_id: 'synthetic-browser', candidate_sha: 'a'.repeat(40),
  authorization_sha256: 'b'.repeat(64), harness_sha256: 'c'.repeat(64), policy_sha256: 'd'.repeat(64), ui_workflow_sha256: 'e'.repeat(64),
  playwright_entry_sha256: '2'.repeat(64), playwright_module: '/nonexistent-sdk/index.js',
  browser_executable_sha256: 'f'.repeat(64), sample_sha256: '0'.repeat(64), protocol_nonce: '1'.repeat(64),
  run_root: '/nonexistent-owned-run', browser_executable: '/nonexistent-browser', sample_path: '/nonexistent-owned-run/input/clip.mp4',
  sample_bytes: 10, expires_at: Date.now() / 1000 + 3600, budget: { ...BUDGET } });
const reply = (c, sequence, payload = {}) => ({ kind: 'lvw.s2.browser-parent-reply/1', sequence,
  candidate_sha: c.candidate_sha, authorization_sha256: c.authorization_sha256, protocol_nonce: c.protocol_nonce, approved: true, payload });

(async () => {
  await check('config_identity_expiry_exact_and_one_over', () => {
    const c = config(); c.expires_at = 8200; validateConfig(c, 1000);
    assert.throws(() => validateConfig({ ...c, expires_at: 8200.0001 }, 1000));
    assert.throws(() => validateConfig({ ...c, expires_at: 1000 }, 1000));
    assert.throws(() => validateConfig({ ...c, candidate_sha: 'old' }, 1000));
    assert.throws(() => validateConfig({ ...c, sample_bytes: 8 * 1024 * 1024 + 1 }, 1000));
    const reversed = Object.fromEntries(Object.entries(c.budget).reverse()); validateConfig({ ...c, budget: reversed }, 1000);
    assert.throws(() => validateConfig({ ...c, budget: { ...BUDGET, public_submissions: 3 } }, 1000));
  });
  await check('origin_no_provider_cloud_file_or_lookalike', () => {
    for (const url of ['https://example.org', 'http://127.0.0.1:11434/api/ps', 'http://localhost:8191/',
      'http://127.0.0.1.evil:8191/', 'file:///private', 'http://user@127.0.0.1:8191/', 'data:text/html,fake']) {
      assert.throws(() => classify(url, 'GET', null, {}), url);
    }
    assert.equal(classify(ORIGIN + '/scripts/app.js', 'GET', null, {}).kind, 'read');
    assert.equal(classify('data:image/png;base64,AAAA', 'GET', null, {}).kind, 'read');
  });
  await check('graph_actual_owner_and_exact_inputs_and_armed_case', () => {
    const body = { prompt: { '1': { class_type: 'LVWVideoPromptOwner', inputs: {
      video_reference: 'owned.mp4', model: 'gemma4:26b', mode: 'realistic', user_instruction: '', timeout_seconds: 120 } } } };
    const state = { armed: 'complete', reference: 'owned.mp4' };
    assert.equal(classify(ORIGIN + '/prompt', 'POST', body, state).kind, 'public_submissions');
    assert.equal(classify(ORIGIN + '/api/prompt', 'POST', body, state).kind, 'public_submissions');
    assert.throws(() => classify(ORIGIN + '/prompt', 'POST', body, { ...state, armed: false }));
    for (const mutation of [v => v.prompt['1'].inputs.video_reference = '../private.mp4', v => v.prompt['2'] = {},
      v => v.prompt['1'].class_type = 'InternalModelMock', v => v.prompt['1'].inputs.model = 'other',
      v => v.prompt['1'].inputs.url = 'https://example.org']) {
      const bad = JSON.parse(JSON.stringify(body)); mutation(bad); assert.throws(() => classify(ORIGIN + '/prompt', 'POST', bad, state));
    }
  });
  await check('adopt_and_cancel_require_current_parent_bound_tokens', () => {
    assert.equal(classify(ORIGIN + '/api/lvw/v0/video/cancel', 'POST', { run_token: 'current' }, { cancelToken: 'current' }).kind, 'cancellations');
    assert.throws(() => classify(ORIGIN + '/lvw/v0/video/cancel', 'POST', { run_token: 'old' }, { cancelToken: 'current' }));
    assert.throws(() => classify(ORIGIN + '/lvw/v0/video/workbench', 'POST', { action: 'adopt', run_token: 'old' }, { adoptToken: 'current' }));
    assert.throws(() => classify(ORIGIN + '/interrupt', 'POST', {}, {}));
    assert.throws(() => classify(ORIGIN + '/userdata/..%2fprivate', 'PUT', {}, {}));
  });
  await check('failed_actions_consume_fixed_budget_no_unknown_keys', () => {
    const counter = new Counter();
    for (let i = 0; i < BUDGET.public_submissions; i++) counter.charge('public_submissions');
    assert.throws(() => counter.charge('public_submissions')); assert.throws(() => counter.charge('constructor'));
  });
  await check('reply_rejects_wrong_candidate_nonce_sequence_or_approval', () => {
    const c = config(); assert.deepEqual(replyFor(c, 1, reply(c, 1, { ready: true })), { ready: true });
    for (const extra of [{ candidate_sha: '0'.repeat(40) }, { protocol_nonce: '0'.repeat(64) },
      { sequence: 2 }, { approved: false }, { payload: [] }]) assert.throws(() => replyFor(c, 1, { ...reply(c, 1), ...extra }));
  });
  await check('live_parent_protocol_roundtrip_and_disconnect', async () => {
    const c = config(), input = new PassThrough(), output = new PassThrough(), bridge = parentBridge(c, input, output);
    let request; output.once('data', raw => { request = JSON.parse(raw); input.write(JSON.stringify(reply(c, request.sequence, { ready: true })) + '\n'); });
    assert.deepEqual(await bridge.request('case_begin', { case_id: 'complete' }), { ready: true });
    assert.equal(request.action, 'case_begin'); assert.equal(request.protocol_nonce, c.protocol_nonce);
    const pending = bridge.request('cancel_ready', {}); input.end(); await assert.rejects(pending, /DISCONNECTED/);
    assert.equal(bridge.signal.aborted, true); await assert.rejects(bridge.request('public_submit', {})); bridge.close();
  });
  await check('parent_protocol_refuses_replay_and_cross_run', async () => {
    const c = config(), input = new PassThrough(), output = new PassThrough(), bridge = parentBridge(c, input, output);
    output.once('data', raw => { const q = JSON.parse(raw); input.write(JSON.stringify({ ...reply(c, q.sequence), authorization_sha256: '0'.repeat(64) }) + '\n'); });
    await assert.rejects(bridge.request('case_begin', {}), /REFUSED/); assert.equal(bridge.signal.aborted, true); bridge.close();
    const secondInput = new PassThrough(), secondOutput = new PassThrough(), second = parentBridge(c, secondInput, secondOutput);
    secondOutput.once('data', raw => { const q = JSON.parse(raw); secondInput.write(JSON.stringify(reply(c, q.sequence)) + '\n'); });
    await second.request('case_begin', {});
    const pending = second.request('case_begin', {}); secondInput.write(JSON.stringify(reply(c, 1)) + '\n');
    await assert.rejects(pending, /REPLAY/); second.close();
  });
  await check('streaming_file_hash_exact_limit_and_symlink_refusal', () => {
    const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'lvw-browser-policy-'));
    try {
      const file = path.join(temp, 'bytes'); fs.writeFileSync(file, 'synthetic');
      const actual = fileIdentity(file, 9); assert.equal(actual.bytes, 9); assert.equal(actual.sha256, digest(Buffer.from('synthetic')));
      assert.throws(() => fileIdentity(file, 8)); const link = path.join(temp, 'link'); fs.symlinkSync(file, link); assert.throws(() => fileIdentity(link, 9));
    } finally { fs.rmSync(temp, { recursive: true }); }
  });
  await check('worker_refuses_missing_parent_before_target_reads', async () => { await assert.rejects(run(config(), null), /LIVE_PARENT_REQUIRED/); });
  await check('parent_refusal_preserves_all_cases_and_never_launches_browser', async () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'lvw-browser-policy-')); let launches = 0;
    try {
      fs.mkdirSync(path.join(root, 'temp/browser-phase'), { recursive: true });
      const result = await run({ ...config(), run_root: root }, { request: async () => { throw new Error('synthetic parent refusal'); } },
        { playwright: { chromium: { launchServer: async () => { launches++; } } } });
      assert.equal(result.decision, 'NO_GO'); assert.equal(result.stage_pass_claim, false); assert.equal(result.counts.NOT_RUN, CASES.length);
      assert.equal(launches, 0); assert.equal(fs.existsSync(path.join(root, 'temp/browser-phase/evidence')), false);
      const wrongRoot = await run({ ...config(), run_root: root }, { request: async () => ({ owned_run_root: '/different-root' }) },
        { playwright: { chromium: { launchServer: async () => { launches++; } } } });
      assert.equal(wrongRoot.error_code, 'BROWSER_PARENT_ROOT_MISMATCH'); assert.equal(launches, 0);
      assert.equal(fs.existsSync(path.join(root, 'temp/browser-phase/evidence')), false);
    } finally { fs.rmSync(root, { recursive: true }); }
  });
  console.log(JSON.stringify({ kind: 'OFFLINE_BROWSER_POLICY_NOT_BROWSER_ACCEPTANCE', checks: results, passed: results.length, failed: 0, browser_starts: 0 }));
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
