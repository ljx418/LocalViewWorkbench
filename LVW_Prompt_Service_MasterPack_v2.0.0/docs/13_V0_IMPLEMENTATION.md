# 13｜V0实现方案：最简图片／视频反推

> 历史范围沿用 docs/22：V0-Min 单图/人工，V0.1 视频/资源，V0.2 离线/回滚/完整质量。2026-11-05 的全量执行清单与十二项追踪见 [24｜执行总纲](24_EXECUTION_MASTER_PLAN.md)；当前阶段、完成度及暂停原因只读 execution-control，不从本章历史标题推断。

本章只定义V0；不削减后续V1–V3。真实工作流由目标机生成。


这里的名称是**职责别名**，不是保证存在的ComfyUI class_type。节点真实名称/版本/输入输出由S0绑定。

## W-I 图片

```text
本地图片输入 → 旋转/色彩/像素限额 → 已装PA视觉调用 → raw + suggestion
                       ↓                  ↓finally
              预览/源hash/参数          Ollama释放核验
                                          │
建议区 ──用户采纳──→ 人工稿 ──CPU四视图──→ 复制/TXT/JSON
```

输入最多1张图。EXIF方向显式处理；RGBA透明以配置背景合成或明确保留策略；不静默丢失原始颜色解释。来源hash对原文件计算，预处理尺寸单独记录。

## W-V 视频

```text
本地视频上传 → ffprobe限额/可解码检查 → 按时间顺序有限抽帧
                                        ↓
                   4个缩小帧 + 时间性质 + 源hash
                                        ↓
                        PA多帧规则 / 同源薄适配
                                        ↓
                          raw/建议 → 人工稿/导出
```

默认4帧均匀分箱中心；短片不足4个可区分帧允许少帧但警告，不能复制同帧冒充多个观察。较长/快切只保证采样可追踪，不给“完整分镜”的标题。超60s要求用户先截取，不背地只看前60s。

现有视频节点若先把全部帧加载为tensor，即使最后选4帧也不合格。采用受控FFmpeg按需解码，最大待推理帧8、默认4。V0不装PySceneDetect作为必需。

## W-M 人工（独立于W-I/W-V成功）

```text
人工文本/上次导出 → 编辑 → 本地格式整理 → 复制/导出
```

无Ollama、推理失败、取消待清理都可运行。只有Comfy本身完全不可用时V0界面不可用，此时依赖已导出的文本；不承诺系统崩溃仍能提供UI。人工支路不能连接到必须执行的VLM节点。导出按钮应原生JS或独立纯CPU路径，不入GPU执行队列。

## 真实工作流交付要求

UI JSON与API JSON必须由同一个真实图生成；图中只有已安装/已随补丁提供的节点。载入无missing node，测试输入到输出可复跑。附`node-bindings.json`及上游版本；不能把本包`workflow_specs/*.json`改名为UI工作流来交付。

资源释放必须在调用者清理路径，非只在“正常输出之后的节点”。视频时间/错误/模型digest由代码填写，不让模型编造。



```text
ComfyUI 原生页面 / Prompt Assistant 面板
 ├─ 图片上传 → 受控缩放/规范化 ───────┐
 ├─ 视频上传 → ffprobe→有限抽帧/顺序 ├─ 现有PA视觉节点/经核验薄适配
 └─ 独立人工稿 → 格式整理→复制/导出  │              ↓
                   ↑                │  本地Ollama /api/chat
                   └── 显式采纳 ← 原文/建议         ↓
                                 finally清理→/api/ps与显存核验
```

## 1. 模块与新增边界

ComfyUI 负责上传、工作流可视化、已有任务执行；Prompt Assistant 尽量承担模型调用与规则。Ollama 独占模型执行。LVW 只补输入限额、统一结果、人工稿保护、受控导出与任务资源边界。

若现有节点完整满足合同，零额外扩展；否则增加 `custom_nodes/lvw_v0_bridge/` 一份包，使用宿主已有依赖/标准库。必要的原生JS面板从同源加载，无Node运行服务。不把整份PA代码复制成新项目，先核许可证。

## 2. 运行与结果状态（仅会话内，不建持久队列）

分析状态：`idle → preparing → running → succeeded | partial | failed`；取消经 `cancelling`，释放经独立 `resource_state`。会话临时 `run_id` 每次不同，当前run token不匹配的结果只可被丢弃或显式查看，不能改稿。

`resource_state = unknown | busy | releasing | released`。`cancelled`表示产品不再接收该结果，**不代表已停止GPU**；下一任务只有在资源确认释放后进入。宿主/后端崩溃不自动恢复任务，重开需显式重试，这属于V0边界。

会话工作稿维护 `draft_epoch`；每次用户改写递增。结果只进suggestion区，“采纳”显式创建新的草稿内容。导出记录是机器建议还是人工稿及来源run_id，允许纯手工 `run_id=null`。

## 3. 单 GPU 与取消清理

只允许1个LVW视觉请求，ComfyUI自动队列模式对本工作流关闭。锁只约束本扩展；不能宣称它控制其他独立生成工作流或Ollama客户端。使用者先暂停外部GPU任务；发现竞争提示并阻止本次分析，不强制杀进程。

推理调用自身使用 `try/finally` 请求清理。成功请求用 `keep_alive=0`；错误/取消时对本次模型做经本机验证的显式卸载，并轮询`/api/ps`。若存在别的用户请求，不能主动卸载或终止对方任务；报告资源占用及人工处理办法。

不能仅把“Unload Model”节点放在推理节点后：上游异常时它可能永不执行。关闭HTTP连接也不能直接判定停止计算。控制返回不等于驱动显存回收，二者分别验收。

## 4. 多帧处理

默认按视频时长取4个均匀分箱中心（例10s：1.25、3.75、6.25、8.75），不是承诺精确PTS。导出target_time和actual_pts（若可可靠取得），`time_basis`固定写明来源。V0允许目标时间近似；不可用平均fps反算结果冒充真实时间。

每次按顺序解码/缩小一帧，最多4帧进入模型；最多8帧是需另外实测的高级配置。不能一次载入整片HD帧tensor。变帧率、快切、画面内文字和音频均有局限，notes显式说明。重复帧不可伪造新时间内容。

## 5. 四输出与事实/创作分离

一个视觉调用返回观察、推断、未知和可用提示词/关键词。轻量CPU整理可同时生成四个视图；换格式无需再次推理。不能从纯中文通过确定性模板声称自动高质量翻译，英文应来自原始模型字段或用户输入，缺失需显示缺失。

单张静图的运动提示词属于 `creative_additions`，模型猜测的焦距/年代属于 `inferences`。负向词与生成器能力无关时可留空，不自动承诺某个下游工作流支持。

## 6. 后续架构

V1改为独立React/FastAPI/Ollama，不依赖Comfy进程；迁移templates/schema/测试集和纯函数，不迁移Comfy节点状态成为HTTP业务模型。V1已有最小SQLite修订/任务记录，V2再扩展批量恢复和资产，V3才跨项目执行。详见本包 docs/14_V1_IMPLEMENTATION.md。



权威任务源为 本包 `plans/tasks.json`。阶段冒烟与完整发布验收分开；S0不得要求尚未实现的导出/完整离线包先PASS。

## V0-S0｜本机基线与节点绑定

只读核对：Windows实际内存、显卡/驱动、ComfyUI版本与Python、PA安装目录/commit/配置/许可、Ollama端点和模型digest、FFmpeg。备份涉及文件并保存哈希，记录已有工作流加载状态。

读取真实节点注册信息，核实图像/视频输入、文本展示/编辑、取消/卸载、输出类型。分别运行真图和4帧最小分析；对比插件与必要的原生Ollama调用，仅用来选最小路径。检查PA实际发出的num_ctx/输入尺寸，不能只信UI值。

产物：`reports/runtime-inventory.json`、`reports/node-bindings.json`、`reports/reuse-audit.md`、baseline日志。只有read-only inventory通过才允许修改。模型阻断时仍能做S1人工部分，不得据此宣布V0完成。

## V0-S1｜图片与独立人工路径

先提供无模型可用的草稿编辑、复制、TXT/JSON导出；再接图片预处理和真模型。若原生面板没有可编辑输出，仅一个薄扩展补齐；不能要求用户另装通用UI平台。

固化默认规则和4输出，raw/建议/人工稿分离。捕获正常、格式无效、模型未回答、超时；错误不扔掉已有结果。输出的机器字段可空，导出仍是合法JSON且带状态，不伪造成功。

真实交付：`workflows/image_reverse_prompt_v0.ui.json`、对应 `.api.json`、`manual_prompt_v0.ui.json`或等价已验原生面板。测试图片输入、4输出、无模型导出、原图不变、注入和超限。

## V0-S2｜视频有限抽帧与资源控制

优先复用已安装视频加载节点，但需先证明解码与内存有界；否则调用已有FFmpeg实现CPU受控采样。上传/探测/抽帧都必须在本机完成；远程URL不作为输入。

显示4帧与时间性质，生成视频描述及运动推断；保存采样顺序与哈希。完成请求级锁、取消晚到、finally卸载/释放监测，验证下一任务不能抢入。真实交付视频UI/API工作流。真视频至少包括静态、跟拍、快切、VFR；高级8帧不通过就不开放，不能默默降级且仍标8帧。

## V0-S3｜完整验收、封装、回滚

冻结10图+6视频质量集，完成12组验收。限制外联、保留loopback，重启宿主/浏览器/Ollama再测试；只清浏览器应用缓存，不删除预置模型权重。记录外联尝试，不仅记录“被防火墙挡住所以没成功”。

资源测试将冷启动与热模型分开；检查默认卸载后恢复空闲。复用环境增量包换到含中文/空格的新路径安装，工作流导入、模型复用与导出正常；卸载本扩展并回滚配置后，原有Comfy工作流仍能打开运行。

最终产物：版本锁/节点依赖表、模型引用而非权重副本、实际工作流、必要扩展与静态JS、templates、diagnose/install/rollback、README_V0、tests及实际验收证据。工具和依赖只在构建准备时安装，正式运行不联网拉包。

## 目标交付目录（逐项状态见总纲，目录存在不代表已验收）

```text
LVW_V0_RuntimePatch/
  README_V0.md
  workflows/{image_reverse_prompt_v0,video_reverse_prompt_v0}.{ui,api}.json
  workflows/manual_prompt_v0.ui.json    # 或已验独立人工面板
  custom_nodes/lvw_v0_bridge/           # 仅确有缺口才提供
  templates/   contracts/   config/
  scripts/{diagnose,install,rollback}.ps1
  manifests/{versions,node-bindings,licenses,sha256}.json
  tests/   reports/                    # 无私密素材默认打包
```

## 修改与依赖纪律

保留用户未提交修改；不强行git reset/全局pip升级。标准库/宿主已装依赖优先；新依赖必须给出缺口证据并锁版本，不能隐含装FFmpeg大包或复制模型。改动在独立扩展实现，确须修PA才提供可逆小patch与文件原哈希校验。
