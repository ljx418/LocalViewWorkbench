import assert from "node:assert/strict";
import test from "node:test";
import { adopt, asJson, asText, emptyDraft, hasContent } from "./domain";
import type { PromptSpec } from "./types";

const spec: PromptSpec = {
  schema_version: "lvw.prompt/1", mode: "realistic",
  domains: { observation: ["blue cup"], inference: [], user_evidence: [], creative_intent: [], unknowns: [] },
  text_zh: "蓝色杯子", text_en: "blue cup", tags: ["blue", "cup"], negative: "blur",
  template_id: "t", template_version: "1",
};

test("adopt is explicit and creates a new draft", () => {
  const before = emptyDraft();
  const after = adopt(spec);
  assert.equal(hasContent(before), false);
  assert.equal(after.naturalZh, "蓝色杯子");
  assert.equal(after.imagePrompt, "blue cup");
  assert.notEqual(after, before);
});

test("manual export remains valid without a model run", () => {
  const draft = { ...emptyDraft(), naturalZh: "手写内容" };
  const payload = JSON.parse(asJson(draft, null));
  assert.equal(payload.source.type, "manual");
  assert.equal(payload.outputs.natural_zh, "手写内容");
  assert.match(asText(draft), /手写内容/);
});

test("tags are normalized only at export", () => {
  const payload = JSON.parse(asJson({ ...emptyDraft(), tags: "a, b,  ,c" }, null));
  assert.deepEqual(payload.outputs.tags, ["a", "b", "c"]);
});
