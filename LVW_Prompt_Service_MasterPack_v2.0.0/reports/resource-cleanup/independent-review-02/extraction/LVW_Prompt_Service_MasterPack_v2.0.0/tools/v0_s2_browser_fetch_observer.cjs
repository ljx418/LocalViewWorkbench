const crypto = require('node:crypto');
const { performance } = require('node:perf_hooks');

// Serialized into the fresh browser context before host code loads. Preserve
// the native fetch arguments and original Response; observe only owned URLs.
function installFetchObserver({ nonce, origin }) {
  const original = globalThis.fetch;
  const records = [];
  let overflow = false;
  const hash = async data => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', data)), b => b.toString(16).padStart(2, '0')).join('');
  Object.defineProperty(globalThis, '__lvwReadFetchEvidence', { configurable: false, writable: false, value(query) {
    if (query.nonce !== nonce || overflow) throw Error('FETCH_EVIDENCE_AUTHORITY_OR_LIMIT');
    const matches = records.filter(r => !r.claimed && r.url === query.url && r.method === query.method && r.request_sha256 === query.request_sha256);
    if (matches.length > 1) throw Error('FETCH_EVIDENCE_AMBIGUOUS');
    if (!matches.length || !matches[0].ready) return null;
    const row = matches[0];
    if (row.error || row.status !== query.status) throw Error('FETCH_EVIDENCE_INVALID:' + (row.error || 'status'));
    row.claimed = true;
    return { nonce, status: row.status, raw_utf8: row.raw_utf8, bytes: row.bytes, sha256: row.sha256 };
  } });
  globalThis.fetch = function (...args) {
    const [input, init] = args;
    let url, method;
    try {
      url = new URL(input instanceof Request ? input.url : String(input), location.href);
      method = String(init?.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    } catch { return original.apply(this, args); }
    const bare = url.pathname.replace(/^\/api/, '');
    if (url.origin !== origin || method !== 'POST' || !['/prompt', '/lvw/v0/video/upload', '/lvw/v0/video/workbench', '/lvw/v0/video/cancel'].includes(bare)) return original.apply(this, args);
    if (records.length >= 32) { overflow = true; return original.apply(this, args); }
    const row = { url: url.href, method, ready: false, claimed: false };
    records.push(row);
    let requestBytes;
    try {
      const copy = new Request(input instanceof Request ? input.clone() : input, init);
      requestBytes = copy.arrayBuffer();
      requestBytes.catch(() => {});
    } catch (error) { row.error = error.message; requestBytes = Promise.resolve(new ArrayBuffer(0)); }
    // Exactly one native call with the original argument objects. Capturing a
    // clone runs in the background and never substitutes the application's body.
    return original.apply(this, args).then(response => {
      row.status = response.status;
      let captured;
      try { captured = response.clone().arrayBuffer(); }
      catch (error) { row.error = error.message; row.ready = true; return response; }
      Promise.all([requestBytes, captured]).then(async ([request, body]) => {
        if (request.byteLength > 8 * 1024 * 1024 || body.byteLength > 24 * 1024 * 1024) throw Error('FETCH_EVIDENCE_BODY_LIMIT');
        row.request_sha256 = await hash(request);
        row.sha256 = await hash(body);
        row.bytes = body.byteLength;
        row.raw_utf8 = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(body);
        row.ready = true;
      }).catch(error => { row.error = error.message; row.ready = true; });
      return response;
    }, error => { row.error = error.message; row.ready = true; throw error; });
  };
}

async function captureBrowserResponse(page, response, nonce) {
  const failure = await response.finished();
  if (failure) throw failure;
  const request = response.request();
  const query = { nonce, url: response.url(), method: request.method(), status: response.status(),
    request_sha256: crypto.createHash('sha256').update(request.postDataBuffer() || Buffer.alloc(0)).digest('hex') };
  const deadline = performance.now() + 5000;
  while (performance.now() <= deadline) {
    const row = await page.evaluate(query => {
      if (typeof globalThis.__lvwReadFetchEvidence !== 'function') throw Error('FETCH_OBSERVER_ABSENT');
      return globalThis.__lvwReadFetchEvidence(query);
    }, query);
    if (row) {
      const body = Buffer.from(row.raw_utf8, 'utf8');
      if (row.nonce !== nonce || row.status !== response.status() || body.length !== row.bytes || body.length > 24 * 1024 * 1024
          || crypto.createHash('sha256').update(body).digest('hex') !== row.sha256) throw Error('FETCH_CAPTURE_BYTES_CHANGED');
      return { response, body };
    }
    await new Promise(resolve => setTimeout(resolve, 10));
  }
  throw Error('FETCH_EVIDENCE_NOT_READY');
}
module.exports = { installFetchObserver, captureBrowserResponse };
