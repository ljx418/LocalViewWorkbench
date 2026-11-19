import test from "node:test";
import assert from "node:assert/strict";
import { cleanupMessage, sampleMessage } from "./cleanup";
import { cleanupResources } from "./api";
import type { CleanupResult } from "./types";

const base: CleanupResult = { operation_id: "cleanup_test", status: "unknown", verified: false, actions: [], before: null, after: null, reason: null, runtime: null, runtime_error: "NOT_OBSERVED", inventory_observation: { state: "not_started", model_count: null }, listener_observation: { state: "not_observed", reason: "NOT_OBSERVED" }, verification_scope: "original_service_exit_and_resource_bound" };
test("cleanup verdict requires proof; missing telemetry is never zero", () => {
  assert.match(cleanupMessage({ ...base, status: "released" }), /未能确认/);
  assert.match(cleanupMessage({ ...base, status: "released", verified: true }), /已确认/);
  assert.match(cleanupMessage({ ...base, status: "noop", verified: true }), /无需清理/);
  assert.match(cleanupMessage({ ...base, status: "blocked" }), /未执行/);
  assert.match(sampleMessage(null), /暂不可用/);
  assert.match(sampleMessage({ values: null, error: "UNAVAILABLE" }), /暂不可用/);
});
test("cleanup uses fixed POST endpoint, control header, no arbitrary parameters", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/runtime/resources/cleanup");
    assert.equal(options?.method, "POST");
    assert.equal((options?.headers as Record<string, string>)["X-LVW-Control"], "local-ui");
    assert.equal(options?.body, undefined);
    return new Response(JSON.stringify({ data: base }));
  };
  try { assert.equal((await cleanupResources()).status, "unknown"); }
  finally { globalThis.fetch = original; }
});

test("only HTTP404 means a missing backend endpoint", async () => {
  const original = globalThis.fetch;
  try {
    for (const [status, code] of [[404, "ENDPOINT_NOT_FOUND"], [503, "HTTP_503"]] as const) {
      globalThis.fetch = async () => new Response("not-json", { status });
      await assert.rejects(cleanupResources(), (error: unknown) => (error as { code: string }).code === code);
    }
    globalThis.fetch = async () => new Response(JSON.stringify({ unexpected: true }));
    await assert.rejects(cleanupResources(), (error: unknown) => (error as { code: string }).code === "INVALID_RESPONSE");
  } finally { globalThis.fetch = original; }
});
