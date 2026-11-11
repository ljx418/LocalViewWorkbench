# S3-PREP-C-01 — 候选资格探测与本地预览准备实施收据

状态：`READY_FOR_REVIEW`。**不是** Stage PASS，**不是**产品 Gate0，**不是**质量通过，
**不是**人工签署。本准备批只做“资格 + 本地预览”，供下一步独立预标使用。

## 1. 绑定

| 项目 | 值 |
|---|---|
| root 唯一基准 / 合并 | `20e408db8371a1058a5c44c059d1601caf964d85`（`git merge --no-edit`，无冲突） |
| 代码候选（运行绑定） | `e1798f33ba51dcadbf9f0333641d62d14a801491` |
| 代码候选（首次提交） | `63e195c8b585d670ace1f0bf13079a923a79f16a` |
| 工具脚本 blob sha256 | `3ad680f94854e56c0796ae33d143a363f81c79a42f74b6713467d27b4f271a6e` |
| 测试脚本 blob sha256 | `30076940ff98bbb8653774912b7a4eb6c7d46a3fdcfa7c1037effb6c8e5b36e3` |
| 借用的有界进程 runner blob sha256 | `563402a9c2f466c1484173c6a4dd2b9a8dbe46fd939ad92a6264975217508954` |
| child（`S3-PREP-C-01`）sha256 | `9989089a4dae7e39949f603482fd118a5228e6ccba9e405ba5678170e20c902b` |
| catalog sha256 | `5bb786928a143886abc29f8ee2424daa82cfc06476df7a1578bb736926ac7d65` |
| holdout FREEZE.json sha256 | `3a8313c6e44dbf22dfbe8abd84f24a42ff15539ec4d19da13ac9d68b5419288c` |
| stage packet sha256 | `a3f98ec3bd76b8c79dcf73bc92370ac32c06e9bf0f583595e9ce0dd3788951da` |
| 公开 handoff guard | `HANDOFF_READINESS_VERIFIED`，139/139，authority `AUTHORITATIVE` |

本机已装工具（预检绑定真实可执行文件，非别名假定）：

| 工具 | 真实路径 | 版本 | 二进制 sha256 |
|---|---|---|---|
| Python | `/usr/bin/python3.12` | 3.12.3 | `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f` |
| Pillow | `/home/administrator/.local/lib/python3.12/site-packages/PIL` | 12.2.0 | `Image.py` = `1a3d2ef3dbcbd056fbb4de3415302873348c60e90129a9a107b8829395ea47ea` |
| ffmpeg | `/usr/bin/ffmpeg` | 6.1.1-3ubuntu5 | `ed16af623947494a72e284b6eb8ff225f2da22b38b5d5069c2fd4b4ba3384e41` |
| ffprobe | `/usr/bin/ffprobe` | 6.1.1-3ubuntu5 | `272f6ebc634a63d9c8b4ca68e964119d980f25154e5aa2c35e5487da48e9a58f` |

没有下载、没有安装、没有缺工具，因此不存在 BLOCKED。

## 2. 新增文件（仅允许范围内）

- `tools/s3_sample_preparation.py` — 唯一有限 CLI owner（`preflight` / `run` 两个显式子命令）。
- `tools/test_s3_sample_preparation.py` — 45 个定向测试，全部用合成小样与假 source adapter，
  不接触 child 真实 32 项。
- `reports/v0-s3/preparation-05/implementation/run-01/` — 文本证据（JSON + 脱敏 raw log + 本收据）。

未改动任何其它代码、合同、旧证据、plan、manifest。

## 3. 控制流与两次 preflight 记录

强制顺序：**提交代码候选 → 派生 preflight → 真实运行**。preflight 不通过则
selected 媒体的 stat/hash/probe/decode 全部为 0。

| 尝试 | 文件 | 结果 | 媒体访问 |
|---|---|---|---|
| 01 | `preflight-attempt-01-rejected.json` | `PREFLIGHT_REJECTED`（48 项中 1 项失败：`holdout.content_sha256_exact`） | **0**（stat/hash/probe/decode 均为 0） |
| 02 | `preflight.json` | `PREFLIGHT_PASSED`，48/48 | 0（preflight 阶段仍不触媒体） |

尝试 01 的失败是本工具的检查过严，不是数据问题：child 的
`holdout_content_sha256` 列 13 项 = 11 个受保护人工留样 + FREEZE.json 自身的
`expected_sha256` 与 `assets_manifest_sha256`；原检查只允许与 11 个视频哈希完全相等。
修正后的检查更严且方向正确：必须覆盖全部 11 个留样；除 FREEZE 自身声明的两个哈希外
不得有其它条目；任何被选候选都不得与列表中任一项同哈希。修正提交为
`e1798f3`，新增 3 个测试覆盖“漏一个留样”“多一个未知条目”“真实形态通过”。
原始失败收据保留，未覆盖。

## 4. 真实终态（唯一一次实际运行）

`reports/v0-s3/preparation-05/implementation/run-01/receipt.json`
决策：`PREPARATION_COMPLETE_READY_FOR_REVIEW`。

**32 项资格计数守恒**：`selected_total 32 == eligible 32 + not_eligible 0 + not_run 0`
（`conservation_ok: true`）。admitted 32，admitted_bytes 83,043,322（与 child 的
`selected_bytes`、与 root-readiness-01 的 `admitted_source_bytes` 完全一致）。

| ref | 类型 | 状态 | 探测尺寸 | 时长(s) | 采样帧 | 帧去重 |
|---|---|---|---|---|---|---|
| C01 | image | eligible | 3905x5857 | - | 1 缩略图 | - |
| C02 | image | eligible | 512x512 | - | 1 缩略图 | - |
| C03 | image | eligible | 1172x1420 | - | 1 缩略图 | - |
| C04 | image | eligible | 360x300 | - | 1 缩略图 | - |
| C05 | image | eligible | 360x300 | - | 1 缩略图 | - |
| C06 | image | eligible | 2600x744 | - | 1 缩略图 | - |
| C07 | image | eligible | 1920x1080 | - | 1 缩略图 | - |
| C08 | image | eligible | 360x330 | - | 1 缩略图 | - |
| C09 | image | eligible | 1328x524 | - | 1 缩略图 | - |
| C10 | image | eligible | 320x250 | - | 1 缩略图 | - |
| C11 | image | eligible | 500x500 | - | 1 缩略图 | - |
| C12 | image | eligible | 320x250 | - | 1 缩略图 | - |
| C13 | image | eligible | 1440x1200 | - | 1 缩略图 | - |
| C14 | image | eligible | 360x300 | - | 1 缩略图 | - |
| C15 | image | eligible | 3072x4096 | - | 1 缩略图 | - |
| C16 | image | eligible | 320x250 | - | 1 缩略图 | - |
| C17 | image | eligible | 400x225 | - | 1 缩略图 | - |
| C18 | image | eligible | 1344x768 | - | 1 缩略图 | - |
| C19 | image | eligible | 400x225 | - | 1 缩略图 | - |
| C20 | image | eligible | 1920x1080 | - | 1 缩略图 | - |
| C21 | video | eligible | 1920x1080 | 5.167 | 4 | 4 distinct |
| C22 | video | eligible | 1920x1088 | 2.333 | 4 | 4 distinct |
| C23 | video | eligible | 1280x720 | 30.000 | 4 | 4 distinct |
| C24 | video | eligible | 720x960 | 18.532 | 4 | 4 distinct |
| C25 | video | eligible | 864x480 | 5.167 | 4 | 4 distinct |
| C26 | video | eligible | 1280x720 | 3.708 | 4 | 4 distinct |
| C27 | video | eligible | 1280x720 | 3.708 | 4 | 4 distinct |
| C28 | video | eligible | 864x480 | 5.167 | 4 | 4 distinct |
| C29 | video | eligible | 1280x720 | 3.708 | 4 | 4 distinct |
| C30 | video | eligible | 1280x720 | 5.167 | 4 | 4 distinct |
| C31 | video | eligible | 1920x1080 | 22.267 | 4 | 4 distinct |
| C32 | video | eligible | 1280x720 | 10.010 | 4 | 4 distinct |

32 个候选的内容哈希与冻结 catalog 完全一致（32 次单遍 SHA-256 全部匹配），
因此没有 `SOURCE_CHANGED`，没有换文件，没有重试，没有第二次真实运行。
12 个视频每个 4 个采样帧且 4 个内容哈希互不相同（无重复帧需要披露，无少帧警告）。
所有候选都未触发 20MiB/40MP、256MiB、60s、8294400 像素的排除线。

## 5. 精确预算（计数严格区分）

| 计数 | 实测 | 上限 |
|---|---|---|
| 源文件 hash 读取（次数） | 32 | 32 文件 × 1 遍 |
| 源文件 hash 字节 | 83,043,322 | admitted ≤ 1,073,741,824 |
| admitted 源字节 | 83,043,322 | 1,073,741,824 |
| 图片 Pillow decode 调用 | 20 | 每图 1 |
| ffprobe 调用 | 12 | 每视频 1 |
| ffmpeg 帧提取调用 | 48 | 每视频 4 |
| 保留输出字节（runtime 树） | 3,963,572 | 80 MiB |
| 临时 staging 字节（已删除） | 1,493,073 | — |
| wall 时间 | 13.293 s | 1200 s |
| 子进程 | 60 | 仅本轮 owned PID |
| 模型 / GPU / 服务 / 网络 / 下载 / 产品完整 checkpoint | 0 / 0 / 0 / 0 / 0 / 0 | 0 |
| decoder 磁盘 IO | **未测量，未声称** | — |

## 6. 清理实测

- staging `<runtime>/staging`：`staging_removed: true`，`staging_residual_entries: 0`，
  创建 1 / 删除 1。
- 60 个子进程全部由本轮创建并回收，只停本轮 owned PID，未触碰其它进程。
- 源文件修改 0、删除 0；源只读，未复制任何原片（无原片拷贝，未发送任何媒体到远端）。
- 保留产物是**明确登记的保留工件**，不是“零残留”：`runtime.is_zero_residue: false`。

## 7. 预览入口（下一步独立预标所需）

本机精确入口（绝对路径只写在 runtime receipt 与本节）：

```
/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0/.agent-governance/runtime/receipts/s3-preview-c01/run-01/index.html
```

project-relative：`.agent-governance/runtime/receipts/s3-preview-c01/run-01/index.html`
（该目录被 `.agent-governance/runtime/.gitignore` 的 `receipts/*` 排除，未提交任何媒体）。

运行时树 342 个文件 / 3,963,572 字节：32 张 contact sheet、20 张图片缩略图、
48 张视频帧、`index.html`、`runtime-receipt.json`、240 份 raw 命令日志。
`index.html` 内 100 个链接全部为相对路径，页面顶部明确写明
“独立预标前素材预览，不是项目识别输出”，并列出候选 ref / 原始候选 ID / 类型 /
相对路径 / 状态 / 探测尺寸时长 / 采样点 / 排除理由 / 预览与 contact sheet，
不含任何语义标签或预期答案。

## 8. 证据与脱敏

- 精确 raw（未脱敏，含绝对路径，仅本机）：
  `.agent-governance/runtime/receipts/s3-preview-c01/run-01/raw/`
- 提交用脱敏 raw（240 份，108 处替换，绝对源根 → `<SOURCE_ROOT>`）：
  `reports/v0-s3/preparation-05/implementation/run-01/raw/`
- 提交侧无任何 `/mnt/c/workSpace` 绝对路径、无 EXIF 载荷、无媒体文件
  （该目录只有 3 个 JSON + 249 个 log）。

## 9. 不声称的事（限制）

- 资格 ≠ 质量。eligible 32 不代表质量分母通过，也不代表语义覆盖。
- 探测尺寸与时长是容器事实，不是完整解码已证明实际 PTS；采样点是“请求的采样点”，
  不是已证明的实际呈现时间戳。
- 没有运行 LVW 或任何产品分析，没有生成语义“标准答案”，没有识别。
- 旧 S2 仍 7/8；10 图 6 视频正式质量阈值（>=8/10、>=5/6、关键幻觉 0）与 11 项人工留样
  全部不变；11 项留样与 3 项 private-labelled 均未被读取或选中。
- 全局预算不变，未扩大任何预算，未占用其它 child 槽位。

## 10. 剩余缺口（交接给 Codex / 独立预标）

1. 独立上下文尚未预标：32 项仍需独立预标 owner 按预标方案打分并冻结。
2. 正式质量集 10 图 + 6 视频需由 Codex 依预览与预标方案再冻结；本批的 32 项 eligible
   只是候选池，不替代冻结。
3. 产品 Gate0 与 S3 十二项总账未动；旧 S2 人工签署仍缺。
4. 需要独立复算（isolated review）本批终态与预览索引的可核对性。
5. 本批不产生任何质量结论。
