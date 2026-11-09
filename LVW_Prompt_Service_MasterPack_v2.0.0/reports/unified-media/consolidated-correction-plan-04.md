# R1 U3 统一纠偏批次04（Gate0准备）

当前正式真实结果仍是live14：7PASS/1FAIL/2BLOCKED，未到人签。独立报告不改写。所有资源/模型/真实操作继续由已批准COMPLETE03自动派生有限子收据；不再申请逐GPU、候选或Stage执行权限。任何真实人签/发布仍不能代签。

## 已取得的根因边界

原固定tracking四源帧在灰度/色分量、thinking1536、全分辨率4图下仍被模型误判静止；不得再调同类提示盲跑。独立原生四图合成witness04确证本次模型分别读到了全部四幅内容，存在三角形位置误差，不能把可见性当视频质量通过。思考模式没有改善原样本，生产默认不启用。

架构兼容复核temporal-owner-contract-review-01为有条件GO_FOR_INTERNAL_DESIGN：COMPLETE03允许内部owner/输入组织修正，公开camera/action字符串未规定必须由VLM作精密几何判断。必须重新冻结R1内部packet；UM04仍要求有用、受支持的采样空间变化、所有raw错误仍FAIL，不能用纯数值+普遍未知自动过门。未来V0-A12/Q01原始输出质量评分和门限不变，本批不宣称满足它们。

## 顺序与唯一owner

1. **Fixture/Gate0准备**：prepare_real_rejections.py有限CPU子运行，生成真实像素超限MP4、256MiB+1字节输入、空文件；结合既有fake-extension/corrupt/truncated/over-duration形成完整类型拒绝集合。每个输入真实hash封存，外部受控大文件不进Git。完成后记录内部owner/input变更决定，冻结packet1.0.4和真实验收recipe；固定UM10与公开Schema/hash不动。
2. **C1 实现**：模型只负责每个实际frame_id可见外观/姿态和共享风格，一次真请求全部完整源PNG、thinkingFalse。新增内部逐帧响应Schema，严格实际编号/数量/类型；保留全raw原文，不能删除错误时序句子。现有纯像素/注册算法迁至VideoKernel所属纯CPU模块，单独生成带单位/alias/局限的时序证据；AnalysisService在可取消准备阶段真实计算，CPU组合器将模型外观与程序事实明确分开。公开PromptSpec/ModelRun形状不变，图片路径不变，人工稿不自动覆盖。原tracking输出必须承认有支持的空间变化，物理相机/主体动作不能凭注册硬判。
3. **C2 实现**：真实harness对每个类型输入执行公开POST/media并验证稳定失败码、无写入残留、无模型/发布；公开真实queued/preparing/running取消，终态released、result_ref为空、旧稿保留。现有running UI取消保留；利用真实准备窗口排队/取消，不用mock代替生产owner。记录每个公开analyze请求与202job绑定，复算ModelRun.config_sha；保留实际Provider payload/response指纹。Node UI及Python控制器/authority同步新recipe/hash/packet支持，0新增外部服务。
4. **C3 收口**：同一批全部离线（后端/共享解码负例/前端test/typecheck/build/文档治理）、隔离代码与反假绿审查后，一次全新完整UM10 checkpoint（8模型动作上限/1800秒/同原tracking+devimage+完整否定集合），再隔离独审。问题一次汇总，不拼接组件结果给PASS。只有10/10且Fatal/Major=0才进入统一人类体验。

## 允许与禁止

允许：lvw/backend/app、lvw/tests、必要React说明、templates、reports/unified-media、R1 packet、execution-control、相关确定性校验。新依赖不需要；纯Pillow/现有FFmpeg即可。原始独审与失败保留。

禁止：contracts、全局acceptance_cases/release_gates、固定UM分母、原tracking样本、11个人工留样、模型权重下载/迁移、云/付费/可见浏览器、永久配置、非本轮进程、远程发布。不得把程序配准称为物理事实核验，不改写模型错误原文、不将未知自动计PASS、不替代V0-A12/Q01原始质量义务。

本文件是纠偏执行设计，不是产品验收或人工授权替代。当前唯一运行坐标仍读plans/execution-control.json。
