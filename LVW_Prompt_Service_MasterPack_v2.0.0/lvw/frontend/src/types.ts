export type Mode = "documentary" | "realistic" | "scifi" | "science" | "cinematic" | "stylized";

export interface MediaRef {
  id: string;
  sha256: string;
  display_name: string;
  bytes: number;
  width: number;
  height: number;
}

export interface Job {
  id: string;
  status: "queued" | "preparing" | "running" | "partial" | "succeeded" | "failed" | "cancelled" | "interrupted";
  resource_state: string;
  result_ref: string | null;
  error_code: string | null;
}

export interface PromptSpec {
  schema_version: "lvw.prompt/1";
  mode: Mode;
  domains: {
    observation: string[];
    inference: string[];
    user_evidence: unknown[];
    creative_intent: string[];
    unknowns: string[];
  };
  text_zh: string;
  text_en: string;
  tags: string[];
  negative: string;
  template_id: string;
  template_version: string;
}

export interface ModelRun {
  id: string;
  job_id: string;
  status: string;
  raw_response: string;
  parsed_spec: PromptSpec | null;
  error_code: string | null;
}

export interface ApiEnvelope<T> {
  data: T;
  request_id: string;
  schema_version: string;
}
