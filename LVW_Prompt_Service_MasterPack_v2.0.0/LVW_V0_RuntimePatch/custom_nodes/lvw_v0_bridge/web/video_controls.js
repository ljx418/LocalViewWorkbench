import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { rawMember, resultJson } from "./video_json.js";

app.registerExtension({
  name: "LVW.VideoControls",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "LVWVideoPromptOwner") return;
    const original = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      original?.apply(this, arguments);
      const box = document.createElement("div");
      Object.assign(box.style, { color: "#eee", background: "#252525", padding: "10px", overflow: "auto", boxSizing: "border-box" });
      const status = document.createElement("p");
      status.textContent = "等待视频分析。";
      const cancel = document.createElement("button");
      cancel.type = "button"; cancel.textContent = "取消本次视频分析"; cancel.disabled = true;
      const upload = document.createElement("input");
      upload.type = "file"; upload.accept = ".mp4,.mov";
      upload.setAttribute("aria-label", "选择并上传 MP4 或 MOV 视频，最大 256 MiB、60 秒");
      const gallery = document.createElement("div");
      Object.assign(gallery.style, { display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: "8px" });
      const limitation = document.createElement("p");
      limitation.textContent = "最多观察四个采样帧，不能证明未采样片段或连续运动。";
      const rawDetails = document.createElement("details");
      const rawTitle = document.createElement("summary"); rawTitle.textContent = "模型原始响应（采样帧）";
      const rawText = document.createElement("pre");
      const suggestionTitle = document.createElement("p"); suggestionTitle.textContent = "机器建议（不会自动覆盖人工稿）";
      const suggestionText = document.createElement("pre");
      for (const view of [rawText, suggestionText]) {
        Object.assign(view.style, { whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxHeight: "240px", overflow: "auto" });
      }
      rawDetails.append(rawTitle, rawText);
      box.append(upload, status, cancel, limitation, gallery, rawDetails, suggestionTitle, suggestionText);
      this.addDOMWidget("lvw_video", "custom", box, { serialize: false });
      let token = null, timer = null, removed = false, cancelled = false;
      const owns = (detail) => !removed && String(detail.node_id) === String(this.id)
        && (!app.graph || !this.graph || app.graph === this.graph);
      const headers = { "X-LVW-Control": "local-ui" };
      const editorNote = document.createElement("p");
      editorNote.textContent = "人工稿仅保留在当前页面会话，离开前请导出；模型忙碌或不可用时仍可编辑与导出。";
      const adopt = document.createElement("button"); adopt.type = "button"; adopt.textContent = "采纳当前机器建议"; adopt.disabled = true;
      const editors = {};
      const fields = { natural_zh: "中文自然描述", natural_en: "English description", image_prompt: "图像提示词",
        video_prompt: "视频提示词", tags: "标签（逗号分隔）", negative: "负向词", edit_instruction: "编辑指令" };
      let revision = 0, adoptedResult = null, adoptedSourceJson = null, draftEdited = false, replaceArmed = false;
      let request = null, actionBusy = false, suggestionReady = false;
      const downloadUrls = new Set();
      const draftStatus = document.createElement("p"); draftStatus.setAttribute("role", "status");
      box.append(adopt, editorNote);
      for (const [name, title] of Object.entries(fields)) {
        const label = document.createElement("label"); label.textContent = title;
        const input = document.createElement("textarea"); input.rows = 3; input.value = "";
        input.maxLength = 40000; input.setAttribute("aria-label", title); input.setAttribute("data-lvw-field", name);
        Object.assign(input.style, { width: "100%", boxSizing: "border-box", resize: "vertical" });
        input.oninput = () => {
          revision++; draftEdited = true; replaceArmed = false;
          adopt.textContent = "采纳当前机器建议"; draftStatus.textContent = "人工稿已修改，尚未导出。";
        };
        editors[name] = input; label.append(input); box.append(label);
      }
      const copy = document.createElement("button"); copy.type = "button"; copy.textContent = "复制人工稿 TXT";
      const txt = document.createElement("button"); txt.type = "button"; txt.textContent = "导出人工稿 TXT";
      const json = document.createElement("button"); json.type = "button"; json.textContent = "导出人工稿 JSON";
      box.append(copy, txt, json, draftStatus);
      const updateActions = () => {
        adopt.disabled = actionBusy || !suggestionReady || cancelled;
        for (const button of [copy, txt, json]) button.disabled = actionBusy;
      };
      const callWorkbench = async (body) => {
        request = new AbortController();
        const response = await api.fetchApi("/lvw/v0/video/workbench", { method: "POST",
          headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(body), signal: request.signal });
        const raw = await response.text();
        const value = JSON.parse(raw);
        if (!response.ok) throw new Error(value.error?.message || `人工稿操作失败 (${response.status})`);
        return { ...value, sourceJson: body.action === "adopt" ? rawMember(raw, ["result", "source"]) : null };
      };
      const download = (name, payload, type) => {
        const url = URL.createObjectURL(new Blob([payload], { type })); downloadUrls.add(url);
        try {
          const anchor = document.createElement("a"); anchor.href = url; anchor.download = name;
          anchor.click();
        } finally {
          setTimeout(() => { URL.revokeObjectURL(url); downloadUrls.delete(url); }, 0);
        }
      };
      const operate = async (operation) => {
        if (actionBusy || removed) return;
        actionBusy = true; updateActions();
        try { await operation(); }
        catch (error) { if (!removed) draftStatus.textContent = error.message; }
        finally { request = null; actionBusy = false; updateActions(); }
      };
      adopt.onclick = () => {
        if (!suggestionReady || cancelled || actionBusy) return;
        if (Object.values(editors).some((input) => input.value.length > 0) && !replaceArmed) {
          replaceArmed = true; adopt.textContent = "再次点击确认替换人工稿";
          draftStatus.textContent = "当前人工稿有内容。再次点击采纳才会替换。"; return;
        }
        replaceArmed = false; adopt.textContent = "采纳当前机器建议";
        const expectedToken = token, expectedRevision = revision;
        return operate(async () => {
          const value = await callWorkbench({ action: "adopt", run_token: expectedToken });
          if (removed || cancelled || token !== expectedToken || revision !== expectedRevision) {
            if (!removed) draftStatus.textContent = "分析或人工稿已变化，未应用迟到的采纳结果。";
            return;
          }
          if (value.result?.run_id !== expectedToken || !Array.isArray(value.result.draft?.tags)
              || value.result.draft.tags.some((tag) => typeof tag !== "string")
              || Object.keys(fields).some((name) => name !== "tags" && typeof value.result.draft[name] !== "string")) {
            throw new Error("采纳结果格式无效，人工稿未改变。");
          }
          for (const name of Object.keys(fields)) editors[name].value = name === "tags"
            ? value.result.draft.tags.join(", ") : value.result.draft[name];
          adoptedResult = value.result; adoptedSourceJson = value.sourceJson; revision++; draftEdited = false;
          draftStatus.textContent = "已显式采纳，可继续编辑；缺失语言未自动翻译。";
        });
      };
      const exportDraft = (kind) => {
        const expectedRevision = revision;
        const snapshot = adoptedResult, sourceSnapshot = adoptedSourceJson, edited = draftEdited;
        const values = Object.fromEntries(Object.keys(fields).map((name) => [name, editors[name].value]));
        return operate(async () => {
          const value = await callWorkbench({ action: "preview", fields: values });
          if (removed) return;
          if (!value.result?.draft || typeof value.txt !== "string") throw new Error("人工稿导出结果格式无效。");
          const result = snapshot ? { ...snapshot, draft: value.result.draft,
            draft_origin: edited ? "edited" : "model_adopted" } : value.result;
          if (kind === "copy") await navigator.clipboard.writeText(value.txt);
          else download(`lvw-video-draft.${kind}`, kind === "json" ? resultJson(result, snapshot ? sourceSnapshot : null) : value.txt,
            kind === "json" ? "application/json;charset=utf-8" : "text/plain;charset=utf-8");
          if (!removed) draftStatus.textContent = revision === expectedRevision ? "人工稿已复制或导出。"
            : "已导出操作开始时的人工稿；后续修改仍需再次导出。";
        });
      };
      copy.onclick = () => exportDraft("copy"); txt.onclick = () => exportDraft("txt"); json.onclick = () => exportDraft("json");
      let uploading = false, uploadRequest = null;
      upload.onchange = async () => {
        const file = upload.files?.[0];
        if (!file) return;
        const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
        if (![".mp4", ".mov"].includes(extension) || file.size < 1 || file.size > 256 * 1024 * 1024) {
          status.textContent = "请选择不超过 256 MiB 的 MP4/MOV 视频。"; upload.value = ""; return;
        }
        uploading = true; upload.disabled = true; status.textContent = "正在上传视频，完成后请运行工作流。";
        uploadRequest = new AbortController();
        try {
          const response = await api.fetchApi("/lvw/v0/video/upload", {
            method: "POST", headers: { ...headers, "Content-Type": "application/octet-stream", "X-LVW-Video-Extension": extension }, body: file, signal: uploadRequest.signal,
          });
          const value = await response.json();
          if (!response.ok) throw new Error(value.error?.message || `上传失败 (${response.status})`);
          if (removed) return;
          const reference = this.widgets?.find((widget) => widget.name === "video_reference");
          if (!reference) throw new Error("未找到视频输入字段，请重新加载工作流。");
          reference.value = value.video_reference;
          reference.callback?.(value.video_reference);
          this.setDirtyCanvas?.(true, true);
          token = null; gallery.replaceChildren(); cancel.disabled = true;
          suggestionReady = false; replaceArmed = false; updateActions();
          rawText.textContent = ""; suggestionText.textContent = "";
          status.textContent = "视频已上传。请运行工作流；分析前将检查容器、时长和画面尺寸。";
        } catch (error) { if (!removed) status.textContent = error.message; }
        finally { uploading = false; uploadRequest = null; upload.disabled = false; upload.value = ""; }
      };
      const refresh = async () => {
        if (removed) return;
        try {
          const response = await api.fetchApi("/lvw/v0/video/status", { headers });
          if (!response.ok) throw new Error(`服务检查失败 (${response.status})`);
          const value = await response.json();
          if (!uploading && token && value.run_token === token) {
            status.textContent = `任务：${value.status}；资源：${value.resource_state}`;
            cancel.disabled = !["preparing", "running"].includes(value.status);
            upload.disabled = ["preparing", "running", "cancelling"].includes(value.status);
          }
        } catch (error) { status.textContent = error.message; }
        if (!removed) timer = setTimeout(refresh, 750);
      };
      cancel.onclick = async () => {
        if (!token) return;
        cancelled = true;
        suggestionReady = false; replaceArmed = false; updateActions();
        cancel.disabled = true;
        try {
          const response = await api.fetchApi("/lvw/v0/video/cancel", {
            method: "POST", headers: { ...headers, "Content-Type": "application/json" },
            body: JSON.stringify({ run_token: token }),
          });
          if (!response.ok) throw new Error(`取消未受理 (${response.status})`);
          status.textContent = "取消已受理，等待当前调用停止并释放资源。";
        } catch (error) { status.textContent = error.message; }
      };
      const preview = ({ detail }) => {
        if (!owns(detail) || cancelled || !token || detail.run_token !== token) return;
        token = detail.run_token; gallery.replaceChildren();
        for (let index = 0; index < detail.images.length; index++) {
          const figure = document.createElement("figure"); figure.style.margin = "0";
          const image = document.createElement("img"); image.src = detail.images[index];
          image.alt = `采样帧 ${index + 1}`; image.style.width = "100%";
          const caption = document.createElement("figcaption");
          caption.textContent = `${index + 1} · ${detail.frames[index]?.time_seconds ?? "未知"}s`;
          figure.append(image, caption); gallery.append(figure);
        }
        status.textContent = detail.limitation; cancel.disabled = false;
      };
      const started = ({ detail }) => {
        if (!owns(detail)) return;
        token = detail.run_token; cancelled = false;
        suggestionReady = false; replaceArmed = false; adopt.textContent = "采纳当前机器建议"; updateActions();
        rawText.textContent = ""; suggestionText.textContent = "";
        gallery.replaceChildren(); cancel.disabled = false;
        upload.disabled = true;
        status.textContent = "准备视频采样，可取消。";
      };
      api.addEventListener("lvw.video.started", started);
      api.addEventListener("lvw.video.preview", preview);
      const oldExecuted = this.onExecuted;
      this.onExecuted = function (message) {
        oldExecuted?.apply(this, arguments);
        if (!owns({ node_id: this.id }) || cancelled || !token || !Array.isArray(message?.text)
            || message.text.length !== 3 || message.text.some((value) => typeof value !== "string")) return;
        try {
          const metadata = JSON.parse(message.text[2]);
          const suggestion = JSON.parse(message.text[1]);
          if (metadata.run_token !== token || metadata.cancel_epoch !== 0 || suggestion.schema_version !== "lvw.prompt/1") return;
          if (!Array.isArray(metadata.frames) || metadata.frames.length < 1 || metadata.frames.length > 4) throw new Error("invalid frame count");
          rawText.textContent = message.text[0];
          suggestionText.textContent = JSON.stringify(suggestion, null, 2);
          suggestionReady = true; updateActions();
          const count = metadata.frames.length;
          limitation.textContent = `仅观察 ${count} 个采样帧，不能证明未采样片段或连续运动。`
            + (count < 4 ? "本轮采样未取得四个不同时间点，未复制帧。" : "");
          status.textContent = `${count} 帧分析完成。机器建议与人工稿分开，采样限制仍适用。`;
        } catch { status.textContent = "分析结果格式无效，未更新展示。"; }
      };
      refresh();
      const oldRemoved = this.onRemoved;
      this.onRemoved = function () {
        removed = true; clearTimeout(timer); api.removeEventListener("lvw.video.preview", preview);
        uploadRequest?.abort();
        request?.abort();
        for (const url of downloadUrls) URL.revokeObjectURL(url);
        downloadUrls.clear();
        api.removeEventListener("lvw.video.started", started);
        gallery.replaceChildren(); oldRemoved?.apply(this, arguments);
      };
    };
  },
});
