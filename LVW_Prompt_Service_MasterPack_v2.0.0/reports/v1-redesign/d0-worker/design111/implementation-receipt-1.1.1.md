# D0-B-IMPL 实现收据 — V1 设计 1.1.1 checker 重新冻结

状态 **READY_FOR_REVIEW**。没有 Stage PASS、没有产品 PASS、没有人签、没有自证。
本收据不是独审结论，也不是 N1–N6 的独立验收。

## 权威来源

| 项 | 值 |
| --- | --- |
| 权威提交 | `743e028474909be02326facd6f14ca0ac26aa56f`（Codex，1.1.1 封权） |
| 载入方式 | `git merge --no-ff 743e028…`，无冲突，合并提交 `14884bcb17024fc8d47ef9ae41ed95181cac1652` |
| 上一候选 | `172d176271a6722bab3d91ff4d1deefbb9f81bbe` |
| 分支 / 工作树 | `ljx418/lvw-v1-d0-implement` / `…/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement` |
| 父工作树 | 未触碰 |

owner 文件（docs / plans / contracts / .agent-governance / reports/v1-redesign/d0-review）一律未改；
owner 哈希未重生成，只把 checker 里的硬编码 pin 随代码一起重新冻结。

## 重新冻结的 pin 与清单

* `FROZEN_D0_PACKET_MANIFEST_SHA256` → `04d3bfb4af3c2d7be68e494a6d59624a96051a0ebf28e81d6a0367aa32aa6710`
  （owner 在启动时给出的新 payload 哈希 = `.agent-governance/stages/V1-D0/PAYLOAD_MANIFEST.sha256` 的 sha256）。
* 旧 pin `56e6f07b…`（1.1）与 `9bffdf2d…`（1.0）都不再能通过该 packet（各有 CLI 级测试）。
* 24 文件 spec fence 全部重新核对，0 处不一致；10 文件 D0 payload inventory 全部重新核对，0 处不一致。
* spec fence 改为**封闭清单**：少一项、多一项、总数不对都报错。

## 六项 minor 义务（N1–N6）的确定性 guard

| Finding | 义务 | 新 guard（节选） |
| --- | --- | --- |
| N1 | 强 ETag 机器化声明 + 严格合并规则 | `E_ETAG_MISSING` / `E_ETAG_FORMAT` / `E_ETAG_WEAK` / `E_OVERLAY_HEADER_TARGET_MISSING` / `E_OVERLAY_HEADER_COLLISION` / `E_OVERLAY_HEADER_NOT_ALLOWED` / `E_OVERLAY_METADATA_TARGET_MISSING` / `E_OVERLAY_BASE_MUTATED` |
| N2 | additive_paths / additive_operations 与 overlay 精确一致（含既有 Scene 路径上的新 GET） | `E_ADDITIVE_SURFACE`（按 (path, method) 冻结 8 操作 / 7 路径）/ `E_ADDITIVE_PATHS` / `E_ADDITIVE_OPERATIONS` |
| N3 | 7 条 reuse 路径 / 8 个方法全部标注，且只允许两个 metadata key | `E_REUSE_PATHS` / `E_REUSE_METADATA` / `E_OVERLAY_METADATA_KEY` / `E_OVERLAY_METADATA_COLLISION` / `E_OVERLAY_METADATA_VALUE` |
| N4 | ShotFrameRef 真实整数 PTS、正 timebase、无不可达 null 分支 | `E_FRAME_REF_CONSTRAINT` |
| N5 | 双语顺序、条目顺序、序列化（不翻译/不 trim/不去重/raw 原样）、人工域不受影响 | `E_DOMAIN_MAPPING`（并用合同自身示例重算序列化结果） |
| N6 | 11 个 hash 字段 ↔ DDL 列别名（含 tb_num/tb_den/version）与 0/1→bool | `E_SCENE_HASH_MAPPING` |

另外新增：`E_111_ADJUDICATION`（owner 纠偏仍必须记为待独立复核，不得记为已接受/产品门禁/样本已落地）、
`E_PRODUCT_COORDINATE`（产品坐标必须停在 R1 / WAIT_HUMAN）。

合并规则在 checker 内部**离线重放**：允许的改动只有新增方法、两个 allowlisted `x-*` 键、
allowlisted 响应头；其余（request body、参数、状态码、`x-product-version`、V2 路由语义）
必须逐字节不变。这只是离线检查，没有向生产引入任何通用 metadata patch 引擎。

## 保留的既有检查

1.1 的全部数值/样本/预算/冻结分母检查全部保留并继续通过：29/38/47 分母与 21/30/39 legacy 前缀、
MS01–MS08 各一次且 NOT_RUN、R1→V1-M1→R2 DAG 无环、R22 覆盖、Q01/MS 阈值 token、
450*n+90 父预算公式、有限整数限额、65+7=72 动作 / 21600 s 墙钟 / 20735 s 阈值估算与"非实测 P95、非最坏情况"声明、
12 clips / 47 shots / 21 hard cuts / 18 行质量子集与待物化占位符、overlay 只增不改、
canonical Scene 精确别名、ShotFrameRef 收窄、公开/内部 binding 拆分、旧 R1 packet 与 canonical 合同不可变。

## 测试

`tools/test_verify_v1_plan.py`：共 **164** 个（原 1.1 的 107 个全部保留，仅 1 个因 1.1.1 规格变更改名并加强断言）。

* 唯一改名：`test_overlay_metadata_may_not_claim_the_existing_body_changed`
  → `test_overlay_metadata_may_not_replace_the_existing_body`。1.1.1 把扁平 prose metadata map
  换成逐方法 map 且只允许两个 `x-` 键，所以同一意图现在由更严格的 `E_OVERLAY_METADATA_KEY` 规则守住。
* 新增 57 个测试，覆盖 N1–N6 的每个判定分支、产品坐标与 adjudication 状态。
* 其中一组测试直接复制**真实 owner 产物**（权威 743e028）到临时目录，改动其中一件产物，
  再让真实 checker 对该副本做判定——不是只比对常量。

## 实跑命令与退出码（日志在 `logs/`，含 sha256）

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `python3 -B tools/verify_v1_plan.py` | 0 | `RESULT: PASS`（24 文件 fence、10 文件 inventory、8 操作/7 路径 additive 面、7 条 reuse 路径） |
| `python3 -B -m pytest tools/test_verify_v1_plan.py -q` | 0 | `164 passed` |
| `python3 -B reports/v1-redesign/verify-design111.py`（owner 架构探针，跑在 owner 树的临时副本上） | 0 | `{"checks": 72, "failed": 0}`；重出的 `design111-owner-checks.json` 与已提交版本逐字节相同，故未弄脏 owner 文件 |
| `python3 -B tools/verify_pack.py` | 0 | passed 7408 / failed 0（文档与合同校验，非产品验收） |
| `python3 -B tools/verify_governance.py` | 0 | errors [] / failed 0 |

非零退出即表示 notready；本轮全部为 0。

## 未做与边界

未执行产品代码、GPU、媒体/FFmpeg、服务、浏览器、网络、安装下载、provider 切换；未打开产品数据库；
未写任何 owner 文件；未合并父工作树；未推送；未宣布 Stage PASS / 产品 PASS / 人工签署。
candidate 迁移 SQL 只被当作文本解析，未执行。
ETag 校验的是声明的 schema，不是运行时响应头；domain 映射校验的是被冻结的规则文本与合同示例的重算，不是真实模型响应到 canonical Domains 的适配器运行；
scene hash 校验的是字段名↔列别名的绑定，不是对真实行重算哈希。

## 已知风险 / 未决

1. 本 checker 不接受 N1–N6：adjudication 仍记为待独立复核；组合的"代码 + N1–N6"独审由 Codex 委托，我方不自证。
2. 原 22 项只在设计层解决，本 workpack 不关闭它们，也不是独立复核。
3. 产品停在 R1 / WAIT_HUMAN；真实样本、来源哈希、授权与标注都不存在，占位符保持 pending。
4. 12 clips / 47 shots / 21 hard cuts / 18 行质量子集只是设计分配，不是已冻结 fixture。
5. MS 用例、V1-M1 stage、R22 固定为 NOT_RUN；在真实 checkpoint 合法产生 PASS 之前，这些 guard 预期 fail-closed。
6. 无 jsonschema 的宿主上，metaschema 探针与保留帧实例探针会退化为结构化兜底。

下一步：Codex → 隔离的 D0-B-REVIEW 实例。仅 READY_FOR_REVIEW。
