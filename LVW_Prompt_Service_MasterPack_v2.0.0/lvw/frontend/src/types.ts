export type Mode = "documentary" | "realistic" | "scifi" | "science" | "cinematic" | "stylized";
export type ContentProfile = "standard" | "faithful" | "adult-art" | "medical";

export interface MediaRef {
  id: string;
  sha256: string;
  display_name: string;
  bytes: number;
  width: number;
  height: number;
  kind: "image" | "video";
  duration_seconds: number | null;
}

export interface Job {
  id: string;
  status: "queued" | "preparing" | "running" | "partial" | "succeeded" | "failed" | "cancelling" | "cancelled" | "interrupted";
  resource_state: string;
  result_ref: string | null;
  error_code: string | null;
  progress_done?: number;
  progress_total?: number;
}

export interface FrameRef {
  index: number; source_pts: number | null; time_base_num: number | null; time_base_den: number | null;
  target_seconds: number; time_basis: "sample_target" | "decoded_pts"; sha256: string;
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
  technical?: { camera_motion: string; subject_action: string };
}

export interface ModelRun {
  id: string;
  job_id: string;
  status: string;
  raw_response: string;
  parsed_spec: PromptSpec | null;
  error_code: string | null;
  input_sha256?: string;
  frames?: FrameRef[];
  model_tag?: string;
}

export interface ApiEnvelope<T> {
  data: T;
  request_id: string;
  schema_version: string;
}

export interface Readiness {
  ready: boolean;
  model: string;
  reason: string | null;
  loaded: boolean;
}

export interface RuntimeStatus {
  protocol: "lvw.runtime/1";
  lvw: { state: "ready" };
  ollama: {
    state: "stopped" | "starting" | "ready" | "external" | "error";
    reachable: boolean;
    model: string;
    model_ready: boolean;
    model_loaded: boolean;
    managed: boolean;
    pid: number | null;
    reason: string | null;
    last_error: string | null;
  };
  actions: { can_start: boolean; can_reset: boolean; can_stop: boolean };
}
