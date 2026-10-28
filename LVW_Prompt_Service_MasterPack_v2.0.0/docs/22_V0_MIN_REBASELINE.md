# 22｜V0 目标收缩决策：V0-Min / V0.1 / V0.2

状态：**APPROVED**  
批准人：项目负责人  
批准日期：2026-10-28  
变更原因：原始目标是尽快交付最简本地工作流；此前 V0 同时承担视频强化、完整质量矩阵、安装回滚和发布硬化，范围过重。

## 当前目标：V0-Min

用户在现有本机 ComfyUI 中完成一条最小闭环：

```text
固定本地图片 → 受控预处理 → 本地 Ollama → raw + suggestion
                                      ↓ 显式采纳
                              人工稿 → 四输出 → 复制/JSON/TXT
```

V0-Min 固定验收分母保持为 `V0-A01,V0-A03,V0-A04,V0-A05,V0-A08`。所有项目必须在同一 product candidate 上通过，独立审查 Fatal=0、Major=0，并取得人工签署。`NOT_RUN/BLOCKED/SKIPPED/PASS_CANDIDATE_FOR_REVIEW` 均不等于 PASS。

### V0-Min 非目标

- 视频上传、VFR、快切和受控四帧抽样。
- 10 图＋6 视频质量矩阵。
- 取消竞争、长期性能和完整资源压力矩阵。
- 跨中文/空格路径安装、完整卸载回滚和发布增量包。
- V1 独立 React/FastAPI 服务。

这些能力没有取消，只是后移。

## 后续分期

| 目标 | 新增范围 | 累计验收 |
|---|---|---|
| V0-Min | 图片、人工稿、四输出、失败不覆盖、无审批前置 | A01/A03/A04/A05/A08 |
| V0.1 | 最简视频四帧、文件安全、资源与取消 | V0-Min + A02/A07/A09/A10 |
| V0.2 | 离线迁移、增量包、安装卸载回滚、完整质量 | V0.1 + A06/A11/A12，即原 V0 十二项 |

旧 `V0` 发布门槛作为 `V0.2` 兼容别名保留，历史证据和失败不改写。

## checkpoint-01 证据边界

checkpoint-01 的原始终态继续保持 `NO_GO / CASE_PRIVACY_VIOLATION`。独立复审确认五项产品结构事实均达到 `PASS_CANDIDATE_FOR_REVIEW`，但 raw service log 过采集 traceback，且路径扫描器把 URL scheme 误判为盘符路径。目标收缩不能把该历史 NO_GO 改成 PASS。

V0-Min 门禁可以引用经独立复算的非泄漏结构事实，但必须：

1. 排除 raw service-log 内容。
2. 离线修正日志最小化与路径扫描器。
3. 对修正候选重新做独立离线审查。
4. 由 root 形成新的 V0-Min gate decision。
5. 人类明确签署 V0-Min 产品体验；这不自动授权 V0.1/V0.2。

默认不重跑 checkpoint-01。只有新的冻结门禁明确要求新鲜 live 证据时，才另行申请一次性授权和新证据槽。
