# V0-S0 / WP-S0-28 correction-09 独立离线复审

审查日期：2026-10-27（Asia/Shanghai）  
审查角色：`codex_isolated_reviewer`  
审查入口：候选 `d1f268f6c9c3996ba64d49c29343cd87aa7ec1d7`，packet `a9a4931adec6f5196e29692f973ac71e497655ca`  
审查方式：只读、离线；未启动或探测 ComfyUI/Ollama，未访问网络或媒体，未修改实现、合同、packet 或历史证据。

## 结论

Fatal **0** / Major **0** / Minor **1**

WP-S0-25 的 F-01、M-01、M-02 均已在 correction-09 候选中得到**前瞻性离线关闭**：新 harness 不再持久化全量进程/命令行，视频 Oracle 与 string schema 一致，且 live 路径会在 preflight 与服务启动前校验指定 harness commit/blob/file SHA。30/30 离线测试独立重跑通过。

建议 root 接受 `d1f268f...` 为 **OFFLINE_REMEDIATION_READY_FOR_SEALING**，但 S0 正式状态仍保持 **NO_GO**，不得宣布 Stage PASS：历史 correction-08 隐私事故与 root 的 NO_GO 裁决没有被离线修复倒写；本轮没有 live 授权、公开路径重跑或产品验收。四个固定产品用例继续为 `NOT_RUN`。

## Finding

### N-01 — Minor — correction-09 离线收据尚未用候选/证据提交封存

- **位置**：`reports/v0-s0/implementation-receipt-correction-09-offline.json:14-17,39-54`；候选 commit `d1f268f...` 的 changed paths。
- **触发**：把给定候选 SHA、实际 commit changed paths、root manifest 和 offline receipt 的 binding 字段互相复算。
- **预期**：最终封存收据应绑定实际候选/证据提交，并使 changed-files/manifest 边界可明确复算；收据本身的 hash 应由后续 sealing 记录绑定。
- **实际**：收据如实标记 `candidate_sha` 和 `evidence_commit` 为全零占位，状态均为 `PENDING_ROOT_SEALING`。其 `changed_files` 是实现 owner 的三项输出，而候选 commit 另含 sealing owner 更新的 `MANIFEST.sha256`，因此收据还不是最终 commit-level 封存证明。该缺口没有制造假绿：状态明确 pending，receipt 仍为 `READY_FOR_REVIEW` 且 `stage_pass_claim=false`。
- **证据**：候选实际四项 changed paths 为 root manifest、两个 tool 文件和 correction-09 receipt；receipt SHA-256 独立复算为 `8b70dc62b5994745cf3fe0ce643ce7b34942fd590dbbe38ec4009fe40fadb8fb`。root manifest 已正确绑定两个 tool 文件，但不包含该 receipt。
- **复现**：`git diff --name-status a9a4931..d1f268f`；`rg -n 'candidate_sha|evidence_commit|PENDING_ROOT_SEALING' reports/v0-s0/implementation-receipt-correction-09-offline.json`；`sha256sum reports/v0-s0/implementation-receipt-correction-09-offline.json`。
- **建议**：由 root sealing owner 另建封存提交，填入候选/证据关系并绑定 receipt hash；不得由实现者或本 reviewer 回写候选。封存只关闭本 Minor，不构成 live 授权或 Stage PASS。

## 三项发现关闭复算

### F-01：隐私最小化 — CLOSED_OFFLINE

- `evaluate_windows_preflight()` 仍在内存中读取 `ExecutablePath`/`CommandLine` 以识别 target，但返回并持久化的进程信息只有 `windows_process_count`、`target_process_count` 与 `{process_id, match_kind}`；listener 只保存 `{local_port, owning_process}`。没有 `windows_processes`、完整行、命令行、可逆编码字段或路径进入 preflight result。
- `windows_native_preflight()` 将上述最小 result 写入 `preflight-baseline.json`；live receipt 的 preflight details 读取同一最小 artifact，不再复制原始 CIM 表。枚举解码/JSON 失败只保存 error code、字节数、SHA-256 和位置，不保存 raw bytes。
- 新隐私 fixture 输入含无关进程的 CommandLine、私有路径形态及 Base64-shaped user/path 字段。对 canonical result 的断言确认：process count 为 2，仅目标 PID/type 被保留，完整 CommandLine、fixture 编码载荷和路径标识均不存在。correction-09 offline receipt 自身也不含 `CommandLine`/`ExecutablePath` 或全量进程表。
- 限制：本轮没有产生新的真实 preflight/live receipt；这里证明的是代码路径与确定性 fixture，不能声称历史泄漏已从 Git object database 消失。

### M-01：`camera_motion` 类型 Oracle — CLOSED_OFFLINE

- `contracts/prompt-spec.schema.json:121-123` 规定 `technical.camera_motion` 为 string；合同在 packet→candidate diff 中未修改。
- `tools/v0_s0_live_probe.py:707-720` 现在以默认空字符串读取该字段，只接受 `isinstance(motion, str) and motion.strip()`；非空 string 通过，list 与空白 string 都稳定抛出 `video suggestion has no camera_motion`。
- `VideoOracleTests` 的三项独立重跑全部通过：明确无变化的非空 string PASS，list FAIL，空白 string FAIL。该改动关闭 correction-08 的 harness 假阴性，但不追溯改写旧 receipt，也不把旧视频探测升级为产品 PASS。

### M-02：运行时 harness 身份 — CLOSED_OFFLINE

- live CLI 现在强制要求 `--harness-candidate-sha`。`Probe.run()` 的顺序为：验证 authorization/product commit → `verify_harness_identity()` → `windows_native_preflight()` → 样本/target snapshot/temp → `start_services()`；identity gate 明确早于 preflight 和任一 service start。
- identity artifact 同时记录指定 harness commit、该 commit/path 的 Git blob object ID、blob SHA-256、执行中 `__file__` SHA-256、`matched` 和 `service_starts=0`。实际候选 tool blob SHA-256 独立复算为 `999cb17e42ef9f2fd4f2ba87e6cb2cf2c9009b0485d6a075b97957658e6fc810`，与当前文件及 receipt artifact hash 一致。
- mismatch fixture 让 sealed blob 与执行文件字节不同；结果为 exit 2、decision `BLOCKED`、exact stop `HARNESS_IDENTITY_MISMATCH`，identity artifact 与 receipt 均保留 mismatch，且 `windows_native_preflight()`、`start_services()` 均未调用，服务启动数为 0。match fixture 证明 commit/blob/file 三类字段被记录且两个 SHA-256 相等。
- 限制：这是未来 live run 的 fail-closed 机制；本轮没有 live authorization，不能据此补造 correction-08 当时缺失的 runtime identity。

## 测试、manifest 与收据复算

- 独立执行 `python3 -B -m unittest -v tools/test_v0_s0_live_probe.py`：30 tests / 30 PASS / 0 FAIL。测试名称逐项计数为原有 24 项加隐私 1、identity 2、camera-motion 3；不是仅采信 receipt 摘要。
- AST parse、`--help`、`--self-check` 独立通过；self-check 报告 `service_started=false`。未产生网络、模型、媒体或服务动作。
- `tools/v0_s0_live_probe.py` SHA-256 为 `999cb17e...fc810`；`tools/test_v0_s0_live_probe.py` 为 `faee610c...84c9b`。二者与 receipt `artifact_sha256`、候选 Git blob materialization 和 root `MANIFEST.sha256` 全部一致。
- root `MANIFEST.sha256` 全项校验通过；Stage `PAYLOAD_MANIFEST.sha256` 9/9 通过；`verify_pack.py --schema` 为 1056/0；`verify_governance.py` 为 37/0，自测为 42/0。它们都是离线文档/治理检查，不是产品验收。
- 固定分母重新按排序 ID 加末尾 LF 计算为 `78b158e135be4da756e27ced9f57c74e78feb926bcaf95eda2e2a6992c9a7b42`。receipt 的 `test_counts` 为 denominator 4、not_run 4，其余 0；`V0-A01/V0-A02/V0-A09/V0-A10` 全部 `NOT_RUN`。

## 历史隔离与假绿判断

- `8fa8140dc7d58bb65fe9eefbc9992f7ad08a8f70` 仍是候选历史中的可达祖先，原始事故事实没有被改写或替代。当前树的 containment derivative 已移除 `windows_processes`，保留不可逆 summary 与 `evidence_view`；`privacy-incident-correction-08.md` 明确禁止推送、发布、附件或引用原 artifact，并说明本地 Git 历史对象仍存在。
- packet `a9a4931...` 到候选 `d1f268f...` 的 diff 只含 root manifest、两个 harness tool 和新 offline receipt；没有触碰 correction-08 evidence、产品 candidate、合同或 acceptance plan。
- **无新增假绿**：receipt 使用 `READY_FOR_REVIEW`，明确 `stage_pass_claim=false`、`production_path_status=NOT_RUN_OFFLINE_WORKPACK`、外部动作全 0、产品四项 NOT_RUN。N-01 的 pending sealing 也被显式披露。
- **不得作出的推论**：F/M 三项的离线关闭不能消除历史 Fatal、不能重新解释 correction-08 的 live 结论、不能授权重跑、不能证明新的 public `/prompt` E2E，也不能把 S0 或任何产品用例标为 PASS。

## 建议出口与限制

1. root 可在修复 N-01 的封存绑定后接受 correction-09 作为未来 harness 的离线预防性基线。
2. S0 状态继续 **NO_GO**；若未来仍需 live 证据，必须由人类负责人另立新授权与预算，不能复用 correction-08 授权。
3. 继续隔离原始 `8fa8140...` 对象；本报告不授权历史重写、推送、发布或删除。
4. correction-09 未执行任何产品分母；下一 Stage 仍需新 packet，四项产品用例保持 `NOT_RUN`。
