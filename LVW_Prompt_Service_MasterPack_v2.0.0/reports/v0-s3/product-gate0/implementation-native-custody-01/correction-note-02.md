# N1 纠正记录 02：抄写错误的第二处，与本批真实结果

> 根授权：`msg_a468b84960db`（ACK 一次 54 节点批次，仅 root 冻结执行包）
> 本记录状态：**批次已执行一次，结果为 FAIL（8 failed / 46 passed）**；失败原样保存，未重跑。
> 关联：`correction-note-01.md`（第一份勘误，被 root 计划 pin，**原样保留未改**）、
> `native-custody-01.execution-report.md`（本批完整执行报告）、
> `commands.json`（精确命令与权威绑定）。

---

## 1. 第一份勘误里的一处**未被发现**的抄写错误

`correction-note-01.md` 的错误清单列了两处旧 owner 摘要抄写错误，并写道
"根已静态核对实际摘要与本记录一致"。**这句话对第二处不成立。**

| 项 | `correction-note-01.md` 写的 | 实测 / root 计划 pin 的 | 判定 |
|---|---|---|---|
| `tools/v0_s3_production_controller.py` | `…91020c09948f9bf9583a2b38` | `…91020c09948f9bf9583a2b38` | ✅ 一致 |
| `tools/v0_s3_coordinator.py` | `…bff8f4ca0708d958b56f12b` | `…bff8f4ca0708d958b56f12c` | ❌ **末位 `b` 应为 `c`** |

* 我最初把两个摘要各抄错一处：controller 是 `…c09948f8bf…`（应为 `f9bf`），
  coordinator 是 `…bff8c4a0708…`（应为 `f4ca`）**且**末位 `b`（应为 `c`）。
* 根的消息指出了这两处里的**第一类**（`8c4a`→`f4ca`），但它引用的参照值本身来自**我抄错的字面量**，
  因此**末位**那一处没有被纠正，我照抄进了被执行的测试模块。
* root 自己的**冻结计划**重新实测得到 `…f12c` 并据此 pin；root 的 runner 在运行时逐项校验
  全部 pins，**没有 PIN_DRIFT**，因此**旧 owner 文件本身自始至终未改一字**，
  被 pin 的值与磁盘上的值一致。
* 后果：本批的 `test_the_old_owners_are_unchanged` 节点**失败**（期望字面量末位是 `b`，
  实测是 `c`）。这是**测试侧的字面量错误**，不是旧 owner 的漂移。

**更正**：旧 owner `tools/v0_s3_coordinator.py` 的权威摘要为
`14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12c`。
`correction-note-01.md` 因被 root 计划 pin 而**原样保留**，以本记录为准。

---

## 2. 本批的真实结果（一批，未重跑）

| 口径 | 值 |
|---|---|
| 权威计划 | root `validation-plan-02/plan.json`，sha256 `f028d42a3f652a09f798e4d2269e8726c9cefc89235d11dce9738c8fd9f84cd9`（与 ACK 一致） |
| 执行对象 | root 的 `guard.py` + `runner.py` + `outer_counter_read.py`；**我提交的 runner 未被执行** |
| pytest 退出码 | **1** |
| 调用 / 通过 / 失败 / skip | 54 / **46** / **8** / 0 |
| 功能节点通过 | **45 / 52**（**不是** 54 项功能通过） |
| integrity 节点 | 2 个，1 通过 1 失败 |
| collection 与冻结顺序 | 逐项相等且顺序一致 ✓ |
| guard | 先于候选与 pytest ✓；自检 6 拒 ✓；运行时越界 **0** ✓ |
| FD | before 3 / after 3；新增或复用 **0**；unknown **0**；`cleanup_proven_for_batch=true` ✓ |
| 线程 | `['MainThread']` → `['MainThread']`，无残留 ✓ |
| 原 counter | 前后**逐字节相同**（`acbdb8b1…`，inactive，28 / 240 / 12.362，charges 相同），未写、未退款、未清零、未复活 ✓ |
| 墙钟 | 三条命令合计 0.709 s，受保护批次 0.655 s（上限 300 s），批次数 1（上限 1） |
| 真实 native 动作 | **无**（无 Windows API / 服务 / 模型 / GPU / 端口 / 媒体 / 网络 / 下载） |

**批次结论：FAIL。** 8 个失败全部保留，根因逐条在
`native-custody-01.execution-report.md` §4：**1 条产品源码缺陷**
（闭合计划的日志引用未拒盘符绝对路径）+ **7 条测试侧缺陷**（假 façade 的调用记录与错误码、
一条帧数期望、一处字面量末位）。

---

## 3. 本次**没有**做的事

* **没有**重跑、**没有**补跑、**没有**追加节点、**没有**换路由、**没有**修改任何被 root
  计划 pin 的文件（18 个 source/tool 项、root 的 `plan.json`/`guard.py`/`runner.py`/
  `outer_counter_read.py`、我提交的 `plan.json`/`guard.py`/`runner.py`/`correction-note-01.md`/
  被取代版本的原始字节）——全部**逐字节保留**。
* **没有**改旧 controller / worker / quality_phase / supervisor / coordinator / runtime /
  driver / budget authority / local_program_authority / 协议 / 拒绝点 / MANIFEST / 旧证据。
* **没有**应用 §4 的修正清单：那需要 root 重新冻结计划并重新 ACK。
* **没有** clean / reset / 批量 add；既有工件与失败原样保留。
* **没有**主张任何 native / GPU / 端口 / 父崩溃 / Windows stdin EOF 能力；
  `grant_authority` 仍 `NOT_VERIFIED`；**不签 Stage PASS、不签产品 Gate0**。
