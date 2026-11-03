import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

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
      box.append(upload, status, cancel, gallery);
      this.addDOMWidget("lvw_video", "custom", box, { serialize: false });
      let token = null, timer = null, removed = false;
      const owns = (detail) => !removed && String(detail.node_id) === String(this.id)
        && (!app.graph || !this.graph || app.graph === this.graph);
      const headers = { "X-LVW-Control": "local-ui" };
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
        if (!owns(detail)) return;
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
        token = detail.run_token; gallery.replaceChildren(); cancel.disabled = false;
        upload.disabled = true;
        status.textContent = "准备视频采样，可取消。";
      };
      api.addEventListener("lvw.video.started", started);
      api.addEventListener("lvw.video.preview", preview);
      refresh();
      const oldRemoved = this.onRemoved;
      this.onRemoved = function () {
        removed = true; clearTimeout(timer); api.removeEventListener("lvw.video.preview", preview);
        uploadRequest?.abort();
        api.removeEventListener("lvw.video.started", started);
        gallery.replaceChildren(); oldRemoved?.apply(this, arguments);
      };
    };
  },
});
