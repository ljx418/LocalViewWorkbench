import type { ModelRun, PromptSpec } from "./types";

export interface Draft {
  naturalZh: string;
  naturalEn: string;
  imagePrompt: string;
  videoPrompt: string;
  negative: string;
  tags: string;
}

export const emptyDraft = (): Draft => ({ naturalZh: "", naturalEn: "", imagePrompt: "", videoPrompt: "", negative: "", tags: "" });

export function adopt(spec: PromptSpec): Draft {
  return {
    naturalZh: spec.text_zh,
    naturalEn: spec.text_en,
    imagePrompt: spec.text_en,
    videoPrompt: [spec.text_en, spec.technical?.camera_motion, spec.technical?.subject_action].filter(Boolean).join("\n"),
    negative: spec.negative,
    tags: spec.tags.join(", "),
  };
}

export function asText(draft: Draft): string {
  return [
    `中文提示词\n${draft.naturalZh}`,
    `English prompt\n${draft.naturalEn}`,
    `图像生成提示词\n${draft.imagePrompt}`,
    `视频生成提示词\n${draft.videoPrompt}`,
    `负向提示词\n${draft.negative}`,
    `标签\n${draft.tags}`,
  ].join("\n\n");
}

export function asJson(draft: Draft, run: ModelRun | null): string {
  return JSON.stringify({
    schema_version: "lvw.unified.export/1",
    source: run ? { type: "model_adopted", model_run_id: run.id, job_id: run.job_id,
      input_sha256: run.input_sha256, frames: run.frames ?? [], model_tag: run.model_tag } : { type: "manual" },
    outputs: {
      natural_zh: draft.naturalZh,
      natural_en: draft.naturalEn,
      image_prompt: draft.imagePrompt,
      video_prompt: draft.videoPrompt,
      negative: draft.negative,
      tags: draft.tags.split(",").map((value) => value.trim()).filter(Boolean),
    },
  }, null, 2);
}

export function hasContent(draft: Draft): boolean {
  return Object.values(draft).some((value) => value.trim().length > 0);
}

export function canAnalyze(hasFile: boolean, phase: string, modelReady: boolean): boolean {
  return hasFile && modelReady && !["uploading", "analyzing", "cancelling"].includes(phase);
}
