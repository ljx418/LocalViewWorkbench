import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, controlOllama, getModelRun, getReadiness, getRuntimeStatus, startAnalysis, uploadImage, waitForJob } from "./api";
import { adopt, asJson, asText, canAnalyze, emptyDraft, hasContent, type Draft } from "./domain";
import type { ContentProfile, MediaRef, Mode, ModelRun, Readiness, RuntimeStatus } from "./types";

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

type Phase = "idle" | "uploading" | "analyzing" | "ready" | "failed";

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

  useEffect(() => () => { controller.current?.abort(); if (preview) URL.revokeObjectURL(preview); }, [preview]);
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
  const spec = run?.parsed_spec ?? null;
  const statusText = phase === "uploading" ? "正在检查图片" : phase === "analyzing" ? "本地模型正在观察" :
    phase === "ready" ? "分析完成，等待你采纳" : phase === "failed" ? "本次分析未完成" :
    readiness === null ? "正在检查本地模型" : readiness.ready ? "模型已就绪，等待图片" : "模型未就绪，可人工编辑";
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
    controller.current?.abort();
    if (preview) URL.revokeObjectURL(preview);
    setFile(next); setMedia(null); setRun(null); setError(""); setPhase("idle");
    setPreview(next ? URL.createObjectURL(next) : null);
  }

  async function analyze() {
    if (!file) return;
    controller.current?.abort();
    const abort = new AbortController(); controller.current = abort;
    setError(""); setPhase("uploading"); setRun(null);
    try {
      const ready = await getReadiness(abort.signal); setReadiness(ready);
      if (!ready.ready) throw new ApiError("MODEL_UNAVAILABLE", `本地模型未就绪：${ready.reason ?? "UNKNOWN"}`, true);
      const uploaded = await uploadImage(file, abort.signal); setMedia(uploaded); setPhase("analyzing");
      const initial = await startAnalysis(uploaded.id, mode, contentProfile,
        customGuidance.trim(), abort.signal);
      const finished = await waitForJob(initial, abort.signal);
      if (finished.status !== "succeeded" || !finished.result_ref) {
        const code = finished.error_code ?? "ANALYSIS_FAILED";
        const message = code === "MODEL_REFUSAL"
          ? "本地模型拒绝了这次分析。可切换“艺术裸体／成人内容”后重试；若仍失败，这是模型自身限制。"
          : code === "PARSE_PARTIAL" ? "模型返回内容不符合结构化结果格式，请重新尝试。"
          : "本地模型没有返回可用结果";
        throw new ApiError(code, message);
      }
      const result = await getModelRun(finished.result_ref, abort.signal); setRun(result); setPhase("ready");
    } catch (caught) {
      if ((caught as Error).name === "AbortError") return;
      const value = caught as ApiError; setError(`${value.message}${value.code ? `（${value.code}）` : ""}`); setPhase("failed");
    }
  }

  function change(field: keyof Draft, value: string) { setDraft((current) => ({ ...current, [field]: value })); setDirty(true); }
  function adoptSuggestion() {
    if (!spec) return;
    if (dirty && !window.confirm("当前人工稿有未导出的修改。确定用机器建议替换吗？")) return;
    setDraft(adopt(spec)); setDirty(false);
  }

  return <div className="shell">
    <header className="topbar">
      <div><span className="mark" aria-hidden="true">LVW</span><h1>本地图像提示词工作台</h1></div>
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
        <button data-testid="runtime-start" type="button" onClick={() => runRuntimeAction("start")} disabled={!runtime?.actions.can_start || Boolean(runtimeAction)}>{runtimeAction === "start" ? "启动中…" : "启动模型服务"}</button>
        <button data-testid="runtime-reset" type="button" onClick={() => runRuntimeAction("reset")} disabled={!runtime?.actions.can_reset || Boolean(runtimeAction)}>{runtimeAction === "reset" ? "重置中…" : "重置"}</button>
        <button data-testid="runtime-stop" type="button" onClick={() => runRuntimeAction("stop")} disabled={!runtime?.actions.can_stop || Boolean(runtimeAction)}>{runtimeAction === "stop" ? "关闭中…" : "关闭"}</button>
      </div>
      {runtimeError && <p className="runtime-error" role="alert">{runtimeError}</p>}
    </section>

    <main className="workspace">
      <section className="light-table" aria-labelledby="input-title">
        <div className="section-head"><div><h2 id="input-title">观察图像</h2><p>图片只在本机处理，不发送到云端。</p></div><span className="step">输入</span></div>
        <label className={`frame ${preview ? "has-image" : ""}`}>
          <input data-testid="image-input" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => choose(event.target.files?.[0] ?? null)} />
          {preview ? <img src={preview} alt="待分析图片预览" /> : <div className="empty-frame"><strong>选择一张图片</strong><span>JPEG、PNG 或 WebP · 最大 20 MiB</span></div>}
          <i className="corner corner-a"/><i className="corner corner-b"/><i className="corner corner-c"/><i className="corner corner-d"/>
        </label>
        <div className="input-controls">
          <div className="analysis-options">
            <label>视觉表达方式<select value={mode} onChange={(event) => setMode(event.target.value as Mode)}>{modes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            <label>内容处理<select data-testid="content-profile" value={contentProfile} onChange={(event) => setContentProfile(event.target.value as ContentProfile)}>{contentProfiles.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          </div>
          <button data-testid="analyze" className="primary" type="button" onClick={analyze} disabled={!canAnalyze(Boolean(file), phase, readiness?.ready === true)}>{phase === "uploading" || phase === "analyzing" ? "分析中…" : "分析这张图片"}</button>
        </div>
        <p className="profile-hint">{contentProfiles.find((item) => item.value === contentProfile)?.hint}</p>
        <label className="custom-guidance" htmlFor="custom-guidance">
          <span>附加分析要求 <small>{customGuidance.length}/800</small></span>
          <textarea id="custom-guidance" data-testid="custom-guidance" maxLength={800}
            value={customGuidance} onChange={(event) => setCustomGuidance(event.target.value)}
            placeholder="例如：重点描述布光、镜头视角和油画笔触；不要美化皮肤质感。" />
          <small>只作为分析偏好；不能修改固定输出结构或事实／推断边界。</small>
        </label>
        {readiness && !readiness.ready && <div className="error" role="status"><strong>本地模型尚未就绪</strong><p>{readiness.model}：{readiness.reason}</p><span>页面会自动重试；人工编辑与导出仍可使用。</span></div>}
        {media && <dl className="media-facts"><div><dt>原始尺寸</dt><dd>{media.width} × {media.height}</dd></div><div><dt>文件</dt><dd>{media.display_name}</dd></div><div><dt>内容指纹</dt><dd>{media.sha256.slice(0, 12)}</dd></div></dl>}
        {error && <div className="error" role="alert"><strong>没有完成分析</strong><p>{error}</p><span>你的人工稿没有改变，可以继续编辑或重新尝试。</span></div>}
      </section>

      <section className="analysis" aria-labelledby="analysis-title">
        <div className="section-head"><div><h2 id="analysis-title">拆解与表达</h2><p>先看事实，再决定是否采纳机器建议。</p></div><span className="step">结果</span></div>
        <div className="evidence-grid">
          <article><h3>看见的事实</h3>{spec?.domains.observation.length ? <ul>{spec.domains.observation.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="empty-copy">分析后显示可见主体、环境、构图与光线。</p>}</article>
          <article><h3>可能的推断</h3>{spec?.domains.inference.length ? <ul>{spec.domains.inference.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="empty-copy">推断会与可见事实分开，不冒充确定信息。</p>}</article>
          <article><h3>仍不确定</h3>{spec?.domains.unknowns.length ? <ul>{spec.domains.unknowns.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="empty-copy">无法从图像确认的信息会保留在这里。</p>}</article>
        </div>

        <div className="suggestion-bar">
          <div><strong>机器建议不会自动改稿</strong><span>{spec ? "结果已就绪，你可以检查后显式采纳。" : "即使模型不可用，下方人工稿仍能编辑和导出。"}</span></div>
          <button type="button" className="secondary" onClick={adoptSuggestion} disabled={!spec}>采纳到人工稿</button>
        </div>

        <div className="draft-head"><div><h3>人工工作稿</h3><span>{dirty ? "有未导出的修改" : draftHasContent ? "已采纳，可继续编辑" : "可直接手写"}</span></div><div className="export-actions"><button type="button" onClick={() => download("lvw-prompt.txt", asText(draft), "text/plain;charset=utf-8")}>导出 TXT</button><button type="button" onClick={() => download("lvw-prompt.json", asJson(draft, run), "application/json")}>导出 JSON</button></div></div>
        <div className="draft-grid">
          <div className="draft-field"><div className="field-label"><label htmlFor="draft-natural-zh">中文提示词</label><CopyButton value={draft.naturalZh} label="复制" accessibleName="复制中文提示词" /></div><textarea id="draft-natural-zh" value={draft.naturalZh} onChange={(event) => change("naturalZh", event.target.value)} placeholder="可直接输入中文创作描述" /></div>
          <div className="draft-field"><div className="field-label"><label htmlFor="draft-natural-en">English prompt</label><CopyButton value={draft.naturalEn} label="复制" accessibleName="复制 English prompt" /></div><textarea id="draft-natural-en" value={draft.naturalEn} onChange={(event) => change("naturalEn", event.target.value)} placeholder="English generation prompt" /></div>
          <div className="draft-field"><div className="field-label"><label htmlFor="draft-image-prompt">图像生成提示词</label><CopyButton value={draft.imagePrompt} label="复制" accessibleName="复制图像生成提示词" /></div><textarea id="draft-image-prompt" value={draft.imagePrompt} onChange={(event) => change("imagePrompt", event.target.value)} placeholder="面向图像模型的最终提示词" /></div>
          <div className="draft-field"><div className="field-label"><label htmlFor="draft-negative">负向提示词</label><CopyButton value={draft.negative} label="复制" accessibleName="复制负向提示词" /></div><textarea id="draft-negative" value={draft.negative} onChange={(event) => change("negative", event.target.value)} placeholder="负向约束由模型建议，仍可人工修改" /></div>
        </div>
        <label className="tag-field"><span>标签</span><input value={draft.tags} onChange={(event) => change("tags", event.target.value)} placeholder="用逗号分隔" /></label>
        {run && <details className="raw"><summary>查看模型原始响应</summary><pre>{run.raw_response}</pre></details>}
      </section>
    </main>
    <footer><span>R1a 本地切片</span><span>当前内容只保存在本次页面会话中，请及时导出。</span></footer>
  </div>;
}
