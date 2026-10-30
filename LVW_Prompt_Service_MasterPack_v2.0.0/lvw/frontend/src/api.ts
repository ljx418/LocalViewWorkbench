import type { ApiEnvelope, Job, MediaRef, ModelRun, Mode, Readiness, RuntimeStatus } from "./types";

export class ApiError extends Error {
  code: string;
  retryable: boolean;

  constructor(code: string, message: string, retryable = false) {
    super(message);
    this.code = code;
    this.retryable = retryable;
  }
}

async function read<T>(response: Response): Promise<T> {
  const payload = await response.json();
  if (!response.ok) {
    throw new ApiError(payload?.error?.code ?? "REQUEST_FAILED",
      payload?.error?.message ?? "请求失败", payload?.error?.retryable ?? false);
  }
  return (payload as ApiEnvelope<T>).data;
}

function key(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export async function uploadImage(file: File, signal?: AbortSignal): Promise<MediaRef> {
  const body = new FormData();
  body.append("file", file);
  return read(await fetch("/api/v1/media", {
    method: "POST", body, signal, headers: { "Idempotency-Key": key("upload") },
  }));
}

export async function getReadiness(signal?: AbortSignal): Promise<Readiness> {
  return read(await fetch("/api/v1/readiness", { signal }));
}

export async function getRuntimeStatus(signal?: AbortSignal): Promise<RuntimeStatus> {
  return read(await fetch("/api/v1/runtime/status", { signal }));
}

export async function controlOllama(action: "start" | "reset" | "stop",
                                    signal?: AbortSignal): Promise<RuntimeStatus> {
  return read(await fetch(`/api/v1/runtime/ollama/${action}`, {
    method: "POST", signal, headers: { "X-LVW-Control": "local-ui" },
  }));
}

export async function startAnalysis(mediaRefId: string, mode: Mode, signal?: AbortSignal): Promise<Job> {
  return read(await fetch("/api/v1/jobs/analyze", {
    method: "POST", signal,
    headers: { "Content-Type": "application/json", "Idempotency-Key": key("analysis") },
    body: JSON.stringify({ media_ref_id: mediaRefId, shot_id: null, mode, config_profile: "local-default" }),
  }));
}

export async function getJob(id: string, signal?: AbortSignal): Promise<Job> {
  return read(await fetch(`/api/v1/jobs/${encodeURIComponent(id)}`, { signal }));
}

export async function getModelRun(id: string, signal?: AbortSignal): Promise<ModelRun> {
  return read(await fetch(`/api/v1/model-runs/${encodeURIComponent(id)}`, { signal }));
}

export async function waitForJob(initial: Job, signal?: AbortSignal): Promise<Job> {
  let job = initial;
  const terminal = new Set(["succeeded", "partial", "failed", "cancelled", "interrupted"]);
  while (!terminal.has(job.status)) {
    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(resolve, 450);
      signal?.addEventListener("abort", () => { window.clearTimeout(timer); reject(new DOMException("Aborted", "AbortError")); }, { once: true });
    });
    job = await getJob(job.id, signal);
  }
  return job;
}
