import assert from "node:assert/strict";
import test from "node:test";
import { controlOllama, getReadiness } from "./api";

test("readiness uses the public same-origin endpoint", async () => {
  const original = globalThis.fetch;
  let requested = "";
  globalThis.fetch = (async (input: string | URL | Request) => {
    requested = String(input);
    return new Response(JSON.stringify({
      data: { ready: false, model: "gemma4:26b", reason: "OLLAMA_UNAVAILABLE" },
      request_id: "test", schema_version: "lvw.api/1",
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  try {
    const readiness = await getReadiness();
    assert.equal(requested, "/api/v1/readiness");
    assert.deepEqual(readiness, {
      ready: false, model: "gemma4:26b", reason: "OLLAMA_UNAVAILABLE"});
  } finally {
    globalThis.fetch = original;
  }
});

test("runtime controls use only fixed actions and the local control header", async () => {
  const original = globalThis.fetch;
  let requested = ""; let init: RequestInit | undefined;
  globalThis.fetch = (async (input: string | URL | Request, options?: RequestInit) => {
    requested = String(input); init = options;
    return new Response(JSON.stringify({ data: { protocol: "lvw.runtime/1", lvw: { state: "ready" },
      ollama: { state: "stopped", reachable: false, model: "gemma4:26b",
        model_ready: false, model_loaded: false, managed: false, pid: null,
        reason: "OLLAMA_UNAVAILABLE", last_error: null },
      actions: { can_start: true, can_reset: false, can_stop: false } },
      request_id: "test", schema_version: "lvw.api/1" }),
      { status: 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  try {
    await controlOllama("start");
    assert.equal(requested, "/api/v1/runtime/ollama/start");
    assert.equal(init?.method, "POST");
    assert.deepEqual(init?.headers, { "X-LVW-Control": "local-ui" });
  } finally { globalThis.fetch = original; }
});
