import { useEffect, useMemo, useRef, useState } from "react";
import { cancelJob, ApiError, controlOllama, getModelRun, getReadiness, getRuntimeStatus, startAnalysis, uploadMedia, waitForJob } from "./api";
import { adopt, asJson, asText, canAnalyze, emptyDraft, hasContent, type Draft } from "./domain";
import type { ContentProfile, Job, MediaRef, Mode, ModelRun, Readiness, RuntimeStatus } from "./types";

const modes: Array<{ value: Mode; label: string }> = [
  { value: "realistic", label: "写实" }, { value: "cinematic", label: "电影感" },
  { value: "documentary", label: "纪实" }, { value: "stylized", label: "风格化" },
  { value: "science", label: "科学图解" }, { value: "scifi", label: "科幻" },
];
const contentProfiles: Array<{ value: ContentProfile; label: string; hint: string }> = [
  { value: "standard", label: "标准分析", hint: "中性观察，适合普通图片" },
  { value: "faithful", label: "忠实描述", hint: "保留不寻常或不完美的可见细节" },
  { value: "adult-art", label: "艺术裸体／成人内容", hint: "客观描述成年人体、姿态、构图和风格" },
  { value: "medical", label: "医学与人体结构", hint: "使用中性解剖和医学视觉术语" },
];

type Phase = "idle" | "uploading" | "analyzing" | "ready" | "failed" | "cancelling";

function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = name; anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function CopyButton({ value, label, accessibleName }: { value: string; label: string; accessibleName: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  async function copy() {
    try { await navigator.clipboard.writeText(value); setState("copied"); window.setTimeout(() => setState("idle"), 1200); }
    catch { setState("failed"); window.setTimeout(() => setState("idle"), 1800); }
  }
  return <button className="text-action" type="button" aria-label={accessibleName} onClick={copy} disabled={!value}>{state === "copied" ? "已复制" : state === "failed" ? "复制失败" : label}</button>;
}

export function App() {
  const [inputKind, setInputKind] = useState<"image" | "video">("image");
  const [adoptedRun, setAdoptedRun] = useState<ModelRun | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const jobId = useRef<string | null>(null);
  const cancelRequested = useRef(false);
  const submitted = useRef(false);
  const epoch = useRef(0);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [media, setMedia] = useState<MediaRef | null>(null);
  const [mode, setMode] = useState<Mode>("realistic");
  const [contentProfile, setContentProfile] = useState<ContentProfile>("standard");
  const [customGuidance, setCustomGuidance] = useState("");
  const [run, setRun] = useState<ModelRun | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string>("");
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [dirty, setDirty] = useState(false);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [runtimeAction, setRuntimeAction] = useState<string>("");
  const [runtimeError, setRuntimeError] = useState<string>("");
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  useEffect(() => () => { controller.current?.abort(); if (jobId.current) void cancelJob(jobId.current).catch(() => {}); }, []);
  useEffect(() => {
    let active = true;
    async function check() {
      try {
        const next = await getRuntimeStatus();
        if (active) {
          setRuntime(next);
          setRuntimeError("");
          setReadiness({ ready: next.ollama.model_ready, model: next.ollama.model,
            reason: next.ollama.reason, loaded: next.ollama.model_loaded });
        }
      } catch (caught) {
        if (active) {
          setReadiness({ ready: false, model: "gemma4:26b",
            reason: "SERVICE_UNAVAILABLE", loaded: false });
          const value = caught as ApiError;
          setRuntimeError(value.code === "REQUEST_FAILED"
            ? "当前页面连接到了旧版 LVW 后端。请关闭旧启动窗口，再重新运行 START_LVW.cmd。"
            : "无法读取本地后端状态，页面会自动重试。");
        }
      }
    }
    void check();
    const timer = window.setInterval(check, 3000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  const busy = ["uploading", "analyzing", "cancelling"].includes(phase);
  const spec = phase === "ready" ? run?.parsed_spec ?? null : null;
  const statusText = phase === "cancelling" ? "正在取消并等待资源释放" : phase === "uploading" ? "正在检查媒体" : phase === "analyzing" ? "本地模型正在观察" :
    phase === "ready" ? "分析完成，等待你采纳" : phase === "failed" ? "本次分析未完成" :
    readiness === null ? "正在检查本地模型" : readiness.ready ? "模型已就绪，等待图片或视频" : "模型未就绪，可人工编辑";
  const draftHasContent = useMemo(() => hasContent(draft), [draft]);

  async function runRuntimeAction(action: "start" | "reset" | "stop") {
    setRuntimeAction(action); setRuntimeError("");
    try {
      const next = await controlOllama(action);
      setRuntime(next);
      setReadiness({ ready: next.ollama.model_ready, model: next.ollama.model,
        reason: next.ollama.reason, loaded: next.ollama.model_loaded });
    } catch (caught) {
      const value = caught as ApiError;
      setRuntimeError(`${value.message}${value.code ? `（${value.code}）` : ""}`);
    } finally { setRuntimeAction(""); }
  }

  function choose(next: File | null) {
    if (busy) return;
    epoch.current++;
    controller.current?.abort();
    const kind = next && /\.(mp4|mov)$/i.test(next.name) ? "video" : inputKind;
    const limit = kind === "video" ? 256 * 1024 * 1024 : 20 * 1024 * 1024;
    setMedia(null); setRun(null); setJob(null); setError(""); setPhase("idle");
    jobId.current = null;
    if (next && (next.size === 0 || next.size > limit)) {
      setFile(null); setPreview(null); setPhase("failed");
      setError(next.size === 0 ? "文件为空（MEDIA_INVALID）" : `文件超过${kind === "video" ? "256" : "20"} MiB（MEDIA_LIMIT_EXCEEDED）`);
      return;
    }
    setInputKind(kind); setFile(next);
    setPreview(next ? URL.createObjectURL(next) : null);
  }

  async function analyze() {
    if (!file || busy) return;
    controller.current?.abort();
    const abort = new AbortController(); controller.current = abort;
    const generation = ++epoch.current;
    cancelRequested.current = false; submitted.current = false; jobId.current = null;
    setError(""); setPhase("uploading"); setRun(null); setJob(null);
    try {
      const ready = await getReadiness(abort.signal);
      if (generation !== epoch.current) return;
      setReadiness(ready);
      if (!ready.ready) throw new ApiError("MODEL_UNAVAILABLE", `本地模型未就绪：${ready.reason ?? "UNKNOWN"}`, true);
      const uploaded = await uploadMedia(file, abort.signal);
      if (generation !== epoch.current) return;
      setMedia(uploaded);
      if (cancelRequested.current) return;
      submitted.current = true; setPhase("analyzing");
      const initial = await startAnalysis(uploaded.id, mode, contentProfile,
        customGuidance.trim(), abort.signal);
      if (generation !== epoch.current) { void cancelJob(initial.id).catch(() => {}); return; }
      jobId.current = initial.id; setJob(initial);
      if (cancelRequested.current) await cancelJob(initial.id);
      const finished = await waitForJob(initial, abort.signal, next => {
        if (generation !== epoch.current) return;
        setJob(next);
        if (next.status === "cancelling") setPhase("cancelling");
      });
      if (generation !== epoch.current) return;
      setJob(finished); jobId.current = null;
      if (cancelRequested.current || finished.status === "cancelled") {
        setPhase("idle"); setError(finished.status !== "cancelled"
          ? `后端终态为${finished.status}；已按你的取消意图丢弃建议，人工稿没有改变。资源：${finished.resource_state}`
          : finished.resource_state === "released"
          ? "本轮已取消，资源已确认释放；人工稿没有改变。"
          : "本轮已取消，资源释放未确认；请先导出再重置本轮服务。");
        return;
      }
      if (finished.result_ref) {
        const result = await getModelRun(finished.result_ref, abort.signal);
        if (generation !== epoch.current) return;
        setRun(result);
      }
      if (finished.status !== "succeeded" || !finished.result_ref) {
        const code = finished.error_code ?? "ANALYSIS_FAILED";
        const messages: Record<string,string> = {
          MODEL_REFUSAL: "本地模型拒绝分析。可调整内容预设；模型自身仍可能拒答。",
          PARSE_PARTIAL: "模型输出不符合结构化格式。原始响应如有返回会保留在下方。",
          RESOURCE_RELEASE_PENDING: "资源释放未确认。请先导出人工稿，再重置本轮模型服务。",
          RESOURCE_BUSY: "本机资源正被占用或触及边界，本轮未产生可用建议。",
        };
        throw new ApiError(code, messages[code] ?? "本地模型没有返回可用结果");
      }
      setPhase("ready");
    } catch (caught) {
      if (generation !== epoch.current) return;
      if ((caught as Error).name === "AbortError") {
        setPhase("idle"); setError("上传或等待已取消，人工稿没有改变。"); return;
      }
      const value = caught as ApiError;
      setError(`${value.message}${value.code ? `（${value.code}）` : ""}`); setPhase("failed");
    } finally { if (generation === epoch.current) submitted.current = false; }
  }

  async function cancelAnalysis() {
    cancelRequested.current = true; setPhase("cancelling");
    if (jobId.current) {
      try { setJob(await cancelJob(jobId.current)); }
      catch (caught) { setError(`取消请求未确认：${(caught as Error).message}。仍在等待后端终态。`); }
    } else if (!submitted.current) {
      controller.current?.abort(); setPhase("idle");
    }
  }

  function change(field: keyof Draft, value: string) { setDraft((current) => ({ ...current, [field]: value })); setDirty(true); }
  function adoptSuggestion() {
    if (!spec) return;
    if ((dirty || draftHasContent) && !window.confirm("当前人工稿有未导出的修改。确定用机器建议替换吗？")) return;
    setDraft(adopt(spec)); setAdoptedRun(run); setDirty(false);
  }

  return <div className="shell">
    <header className="topbar">
      <div><span className="mark" aria-hidden="true">LVW</span><h1>本地图文与视频提示词工作台</h1></div>
      <div className={`status status-${phase}`}><span aria-hidden="true" />{statusText}</div>
    </header>

    <section className="runtime-panel" aria-labelledby="runtime-title">
      <div><h2 id="runtime-title">本地后端服务</h2><p>仅控制由 LVW 启动的 loopback Ollama，不会结束外部进程。</p></div>
      <dl>
        <div><dt>LVW API</dt><dd>{runtime ? "运行中" : "检查中"}</dd></div>
        <div><dt>Ollama</dt><dd data-testid="ollama-state">{runtime?.ollama.state ?? "检查中"}</dd></div>
        <div><dt>视觉模型</dt><dd data-testid="model-state">{runtime?.ollama.model_ready ? "可用" : runtime?.ollama.reason ?? "检查中"}</dd></div>
        <div><dt>模型装载</dt><dd data-testid="model-load-state">{runtime?.ollama.model_loaded ? "已加载" : "按需加载"}</dd></div>
        <div><dt>进程归属</dt><dd>{runtime?.ollama.managed ? "LVW 管理" : runtime?.ollama.state === "external" ? "外部服务" : "无"}</dd></div>
      </dl>
      <div className="runtime-actions">
        <button data-testid="runtime-start" type="button" onClick={() => runRuntimeAction("start")} disabled={busy || !runtime?.actions.can_start || Boolean(runtimeAction)}>{runtimeAction === "start" ? "启动中…" : "启动模型服务"}</button>
        <button data-testid="runtime-reset" type="button" onClick={() => runRuntimeAction("reset")} disabled={busy || !runtime?.actions.can_reset || Boolean(runtimeAction)}>{runtimeAction === "reset" ? "重置中…" : "重置"}</button>
        <button data-testid="runtime-stop" type="button" onClick={() => runRuntimeAction("stop")} disabled={busy || !runtime?.actions.can_stop || Boolean(runtimeAction)}>{runtimeAction === "stop" ? "关闭中…" : "关闭"}</button>
      </div>
      {runtimeError && <p className="runtime-error" role="alert">{runtimeError}</p>}
    </section>

    <main className="workspace">
      <section className="light-table" aria-labelledby="input-title">
        <div className="section-head"><div><h2 id="input-title">选择观察素材</h2><p>图片与视频只在本机处理，切换素材不会清空人工稿。</p></div><span className="step">输入</span></div>
        <div className="media-tabs" role="group" aria-label="素材类型">
          <button type="button" aria-pressed={inputKind === "image"} disabled={busy} onClick={() => { choose(null); setInputKind("image"); }}>图片</button>
          <button type="button" aria-pressed={inputKind === "video"} disabled={busy} onClick={() => { choose(null); setInputKind("video"); }}>视频</button>
        </div>
        <div className={`frame ${preview ? "has-image" : ""}`} onDragOver={event => event.preventDefault()}
          onDrop={event => { event.preventDefault(); choose(event.dataTransfer.files[0] ?? null); }}>
          <input id="media-file" data-testid={inputKind === "video" ? "video-input" : "image-input"} type="file"
            disabled={busy} accept={inputKind === "video" ? ".mp4,.mov" : "image/jpeg,image/png,image/webp"}
            onChange={event => { choose(event.target.files?.[0] ?? null); event.target.value = ""; }} />
          {preview ? inputKind === "video" ? <video src={preview} controls preload="metadata" aria-label="待分析视频预览" />
            : <img src={preview} alt="待分析图片预览" />
            : <div className="empty-frame"><strong>选择或拖入{inputKind === "video" ? "一段短视频" : "一张图片"}</strong><span>{inputKind === "video" ? "MP4 / MOV · 最大256 MiB / 60秒 · 默认四帧" : "JPEG / PNG / WebP · 最大20 MiB"}</span></div>}
          <i className="corner corner-a"/><i className="corner corner-b"/><i className="corner corner-c"/><i className="corner corner-d"/>
        </div>
        <label className="file-select" htmlFor="media-file">{file ? "更换文件" : "选择本地文件"}</label>
        <div className="input-controls">
          <div className="analysis-options">
            <label>视觉表达方式<select disabled={busy} value={mode} onChange={(event) => setMode(event.target.value as Mode)}>{modes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            <label>内容处理<select disabled={busy} data-testid="content-profile" value={contentProfile} onChange={(event) => setContentProfile(event.target.value as ContentProfile)}>{contentProfiles.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          </div>
          <button data-testid="analyze" className="primary" type="button" onClick={analyze} disabled={!canAnalyze(Boolean(file), phase, readiness?.ready === true)}>{busy ? "处理中…" : inputKind === "video" ? "分析这段视频" : "分析这张图片"}</button>
        </div>
        {busy && <button className="cancel-action" type="button" onClick={cancelAnalysis} disabled={phase === "cancelling"}>取消本次分析</button>}
        {job && <p className="job-status" role="status">任务：{job.status} · 进度{job.progress_done ?? 0}/{job.progress_total ?? 1} · 资源：{job.resource_state}</p>}
        <p className="profile-hint">{contentProfiles.find((item) => item.value === contentProfile)?.hint}</p>
        <label className="custom-guidance" htmlFor="custom-guidance">
          <span>附加分析要求 <small>{customGuidance.length}/800</small></span>
          <textarea id="custom-guidance" data-testid="custom-guidance" maxLength={800}
            disabled={busy} value={customGuidance} onChange={(event) => setCustomGuidance(event.target.value)}
            placeholder="例如：重点描述布光、镜头视角和油画笔触；不要美化皮肤质感。" />
          <small>只作为分析偏好；不能修改固定输出结构或事实／推断边界。</small>
        </label>
        {readiness && !readiness.ready && <div className="error" role="status"><strong>本地模型尚未就绪</strong><p>{readiness.model}：{readiness.reason}</p><span>页面会自动重试；人工编辑与导出仍可使用。</span></div>}
        {media && <dl className="media-facts"><div><dt>原始尺寸</dt><dd>{media.width} × {media.height}</dd></div><div><dt>文件</dt><dd>{media.display_name}</dd></div><div><dt>内容指纹</dt><dd>{media.sha256.slice(0, 12)}</dd></div></dl>}
        {media?.kind === "video" && <p className="sampling-note">时长{media.duration_seconds?.toFixed(3)}秒；只观察默认四个采样时间点，不保证连续运动或未采样事件。</p>}
        {run?.frames?.length ? <div className="sampling-note"><strong>实际生产采样：{run.frames.length}帧</strong><ul>{run.frames.map(frame => <li key={frame.index}>目标{frame.target_seconds.toFixed(4)}秒 · 实际源PTS {frame.source_pts} × {frame.time_base_num}/{frame.time_base_den} · SHA {frame.sha256.slice(0,12)}</li>)}</ul></div> : null}
        {error && <div className="error" role="alert"><strong>没有完成分析</strong><p>{error}</p><span>你的人工稿没有改变，可以继续编辑或重新尝试。</span></div>}
      </section>

      <section className="analysis" aria-labelledby="analysis-title">
        <div className="section-head"><div><h2 id="analysis-title">拆解与表达</h2><p>先看事实，再决定是否采纳机器建议。</p></div><span className="step">结果</span></div>
        <div className="evidence-grid">
          <article><h3>看见的事实</h3>{spec?.domains.observation.length ? <ul>{spec.domains.observation.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="empty-copy">分析后显示可见主体、环境、构图与光线。</p>}</article>
          <article><h3>可能的推断</h3>{spec?.domains.inference.length ? <ul>{spec.domains.inference.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="empty-copy">推断会与可见事实分开，不冒充确定信息。</p>}</article>
          <article><h3>仍不确定</h3>{spec?.domains.unknowns.length ? <ul>{spec.domains.unknowns.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="empty-copy">无法从图像确认的信息会保留在这里。</p>}</article>
        </div>

        {spec && <article className="machine-prompts" data-testid="machine-suggestion">
          <h3>本次机器建议</h3><p>这里只展示建议，不会改动下方人工稿。</p>
          <h4>中文描述</h4><p>{spec.text_zh || "模型没有提供中文，不会自动补写。"}</p>
          <h4>English description</h4><p>{spec.text_en || "未提供"}</p>
          {run?.frames?.length ? <><h4>观察到的镜头／主体变化</h4><p>{spec.technical?.camera_motion || "未确认"}</p><p>{spec.technical?.subject_action || "未确认"}</p></> : null}
          <p>标签：{spec.tags.join("，")}</p>
        </article>}
        <div className="suggestion-bar">
          <div><strong>机器建议不会自动改稿</strong><span>{spec ? "结果已就绪，你可以检查后显式采纳。" : "即使模型不可用，下方人工稿仍能编辑和导出。"}</span></div>
          <button type="button" className="secondary" onClick={adoptSuggestion} disabled={!spec}>采纳到人工稿</button>
        </div>

        <div className="draft-head"><div><h3>人工工作稿</h3><span>{dirty ? "有未导出的修改" : draftHasContent ? "已采纳，可继续编辑" : "可直接手写"}</span></div><div className="export-actions"><button type="button" onClick={() => download("lvw-prompt.txt", asText(draft), "text/plain;charset=utf-8")}>导出 TXT</button><button type="button" onClick={() => download("lvw-prompt.json", asJson(draft, adoptedRun), "application/json")}>导出 JSON</button></div></div>
        <div className="draft-grid">
          <div className="draft-field"><div className="field-label"><label htmlFor="draft-natural-zh">中文提示词</label><CopyButton value={draft.naturalZh} label="复制" accessibleName="复制中文提示词" /></div><textarea id="draft-natural-zh" value={draft.naturalZh} onChange={(event) => change("naturalZh", event.target.value)} placeholder="可直接输入中文创作描述" /></div>
          <div className="draft-field"><div className="field-label"><label htmlFor="draft-natural-en">English prompt</label><CopyButton value={draft.naturalEn} label="复制" accessibleName="复制 English prompt" /></div><textarea id="draft-natural-en" value={draft.naturalEn} onChange={(event) => change("naturalEn", event.target.value)} placeholder="English generation prompt" /></div>
          <div className="draft-field"><div className="field-label"><label htmlFor="draft-image-prompt">图像生成提示词</label><CopyButton value={draft.imagePrompt} label="复制" accessibleName="复制图像生成提示词" /></div><textarea id="draft-image-prompt" value={draft.imagePrompt} onChange={(event) => change("imagePrompt", event.target.value)} placeholder="面向图像模型的最终提示词" /></div>
          <div className="draft-field"><div className="field-label"><label htmlFor="draft-video-prompt">视频生成提示词</label><CopyButton value={draft.videoPrompt} label="复制" accessibleName="复制视频生成提示词" /></div><textarea id="draft-video-prompt" value={draft.videoPrompt} onChange={event => change("videoPrompt", event.target.value)} placeholder="采样画面支持的主体、场景和变化；可继续手写" /></div>
          <div className="draft-field"><div className="field-label"><label htmlFor="draft-negative">负向提示词</label><CopyButton value={draft.negative} label="复制" accessibleName="复制负向提示词" /></div><textarea id="draft-negative" value={draft.negative} onChange={(event) => change("negative", event.target.value)} placeholder="负向约束由模型建议，仍可人工修改" /></div>
        </div>
        <label className="tag-field"><span>标签</span><input value={draft.tags} onChange={(event) => change("tags", event.target.value)} placeholder="用逗号分隔" /></label>
        {run && <details className="raw"><summary>查看模型原始响应</summary><button type="button" onClick={() => download("lvw-model-run.json", JSON.stringify(run, null, 2), "application/json")}>保存本次分析原始 JSON</button><pre>{run.raw_response}</pre></details>}
      </section>
    </main>
    <footer><span>R1 图文与视频统一切片</span><span>当前内容只保存在本次页面会话中，请及时导出。</span></footer>
  </div>;
}
