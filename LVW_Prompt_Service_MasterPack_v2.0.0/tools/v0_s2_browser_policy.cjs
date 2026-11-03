// Deterministic browser-worker protocol/route bounds. No process or network I/O.
const crypto = require('node:crypto');
const ORIGIN = 'http://127.0.0.1:8191';
const BUDGET = Object.freeze({ browser_starts: 1, uploads: 1, public_submissions: 2,
  previews: 8, adoptions: 2, cancellations: 1, held_responses: 1, downloads: 6, user_writes: 16 });
const ACTIONS = new Set(['preflight', 'browser_start', 'browser_owner', 'upload', 'public_submit', 'case_begin',
  'case_queued', 'busy_manual', 'cancel_ready', 'case_finished', 'offline_op', 'user_write']);

function validateConfig(c, now = Date.now() / 1000) {
  if (!c || c.schema_version !== 'lvw.s2.browser-config/1'
      || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(c.run_id || '')
      || !/^[a-f0-9]{40}$/.test(c.candidate_sha || '')
      || !Number.isFinite(c.expires_at) || c.expires_at <= now || c.expires_at - now > 7200
      || !Number.isSafeInteger(c.sample_bytes) || c.sample_bytes < 1 || c.sample_bytes > 8 * 1024 * 1024) {
    throw new Error('BROWSER_CONFIG_INVALID_OR_EXPIRED');
  }
  for (const key of ['authorization_sha256', 'harness_sha256', 'policy_sha256', 'ui_workflow_sha256', 'playwright_entry_sha256', 'browser_executable_sha256', 'sample_sha256', 'protocol_nonce']) {
    if (!/^[a-f0-9]{64}$/.test(c[key] || '')) throw new Error('BROWSER_IDENTITY_INVALID');
  }
  for (const key of ['run_root', 'sample_path', 'browser_executable', 'playwright_module']) {
    if (typeof c[key] !== 'string' || !c[key].startsWith('/') || c[key].includes('\0')) throw new Error('BROWSER_PATH_INVALID');
  }
  if (!/\.(mp4|mov)$/i.test(c.sample_path) || !c.budget || Object.keys(c.budget).sort().join(',') !== Object.keys(BUDGET).sort().join(',')
      || Object.entries(BUDGET).some(([key, value]) => c.budget[key] !== value)) throw new Error('BROWSER_BUDGET_OR_SAMPLE_INVALID');
}

function classify(raw, method, body, state) {
  const url = new URL(raw);
  if (method === 'GET' && (raw.startsWith('data:image/png;base64,') || (url.protocol === 'blob:' && url.origin === ORIGIN))) return { kind: 'read', pathname: 'memory-image' };
  if (url.origin !== ORIGIN || url.username || url.password || url.hash) throw new Error('BROWSER_NON_COMFY_ORIGIN');
  const pathname = apiPath(url.pathname);
  if (['GET', 'HEAD'].includes(method)) return { kind: 'read', pathname };
  if (method === 'POST' && pathname === '/lvw/v0/video/upload') return { kind: 'uploads', pathname };
  if (method === 'POST' && pathname === '/prompt') {
    const graph = body?.prompt;
    if (!state.armed || !graph || Object.keys(graph).join(',') !== '1'
        || graph['1'].class_type !== 'LVWVideoPromptOwner') throw new Error('BROWSER_UNARMED_OR_NONPUBLIC_GRAPH');
    const input = graph['1'].inputs;
    if (!input || Object.keys(input).sort().join(',') !== 'mode,model,timeout_seconds,user_instruction,video_reference'
        || input.video_reference !== state.reference || input.model !== 'gemma4:26b'
        || input.mode !== 'realistic' || input.user_instruction !== '' || input.timeout_seconds !== 120) {
      throw new Error('BROWSER_GRAPH_CONTRACT_MISMATCH');
    }
    return { kind: 'public_submissions', pathname };
  }
  if (method === 'POST' && pathname === '/lvw/v0/video/workbench') {
    if (body?.action === 'preview') return { kind: 'previews', pathname };
    if (body?.action === 'adopt' && typeof body.run_token === 'string' && body.run_token === state.adoptToken) return { kind: 'adoptions', pathname };
  }
  if (method === 'POST' && pathname === '/lvw/v0/video/cancel' && body?.run_token === state.cancelToken && state.cancelToken) {
    return { kind: 'cancellations', pathname };
  }
  // Only the parent may authorize writes after proving an ephemeral user root.
  if (['POST', 'PUT', 'DELETE'].includes(method) && (pathname === '/settings' || pathname.startsWith('/settings/')
      || pathname.startsWith('/userdata/'))) {
    const decoded = decodeURIComponent(pathname);
    if (decoded.includes('..') || decoded.includes('\\') || decoded.includes('\0')) throw new Error('BROWSER_USER_PATH_INVALID');
    return { kind: 'user_writes', pathname };
  }
  throw new Error('BROWSER_MUTATION_FORBIDDEN');
}

function apiPath(pathname) {
  const bare = pathname.startsWith('/api/') ? pathname.slice(4) : pathname;
  return bare === '/prompt' || bare.startsWith('/lvw/v0/video/') || bare === '/settings'
    || bare.startsWith('/settings/') || bare.startsWith('/userdata/') ? bare : pathname;
}

class Counter {
  constructor() { this.used = Object.fromEntries(Object.keys(BUDGET).map(key => [key, 0])); }
  charge(key) {
    if (!Object.prototype.hasOwnProperty.call(BUDGET, key) || this.used[key] >= BUDGET[key]) throw new Error('BROWSER_BUDGET_EXHAUSTED:' + key);
    this.used[key]++; // Failures consume the slot too.
  }
}

function replyFor(config, sequence, value) {
  if (!value || value.kind !== 'lvw.s2.browser-parent-reply/1' || value.sequence !== sequence
      || value.protocol_nonce !== config.protocol_nonce || value.candidate_sha !== config.candidate_sha
      || value.authorization_sha256 !== config.authorization_sha256 || value.approved !== true
      || !value.payload || typeof value.payload !== 'object' || Array.isArray(value.payload)) throw new Error('BROWSER_PARENT_REPLY_REFUSED');
  return value.payload;
}

function digest(raw) { return crypto.createHash('sha256').update(raw).digest('hex'); }
module.exports = { ORIGIN, BUDGET, ACTIONS, validateConfig, classify, apiPath, Counter, replyFor, digest };
