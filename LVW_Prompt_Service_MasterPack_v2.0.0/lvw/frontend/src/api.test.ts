import assert from "node:assert/strict";
import test from "node:test";
import { getReadiness } from "./api";

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
