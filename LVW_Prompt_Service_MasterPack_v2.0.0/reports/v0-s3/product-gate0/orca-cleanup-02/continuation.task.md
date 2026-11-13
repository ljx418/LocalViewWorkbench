你是LVW S3-P4-OFFLINE的ClaudeCode续接实现/验证负责人，替代已归档关闭的旧实例。root负责架构和门禁，你不能签StagePASS。用户明确要求清理废弃Agent后从中断处接续。工作区只能有你一个Agent；禁止派生子Agent。
本任务分两步，在同一会话完成：
STEP1仅只读核对并ask root，不执行fixture/模型/GPU/网络/原账本、不修改候选。读取工作区AGENTS与root当前控制（root路径下文）、原冻结合同、原用户明确批准和13节点绑定；确认源码HEAD763f3d561772ec8efa7aafe597b62ac77a3b7969及11 pins、原counter starts0/charges空/sessions空、原Python SHA，报告实际运行宿主/ClaudeCode身份、重试环境是否CLAUDE_CODE_MAX_RETRIES=0和CLAUDE_CODE_RETRY_WATCHDOG=0（仅这两个，禁止打印全环境/密钥）。若非0如实报未满足，不能自行改审批或永久配置。然后通过Orca ask root请求STEP2机器恢复，结束当前轮等待回复，不自行执行。
STEP2只有root回复counter已恢复及精确argv后，才直接执行原13项一次。用户已明确批准此前分类器拒绝后的这一次直接尝试，见root approval。若首次审批拒绝或超时立即停止/ask root，不重试、不包装、不改审批配置、不换执行器。FIRST429立即停止WAIT_BUDGET；不得自动重试、切换模型/账号/供应商或由Codex接手。保留所有原始错误与执行退出码；候选改动要先重绑。执行结果、固定13node、共享counter及清理完整回报，失败/UNKNOWN不补跑，未执行和SKIP不是PASS。
原文件实际有report.md未提交修改，是上一轮阻断报告，保留；不得清理未跟踪工件，不git add全部、不提交改变HEAD。生产worker/Pillow子进程、Windows服务/GPU/A06/真实质量12/发布均不在本轮fixture准入内。
完成后worker_done，状态如实；根协调器归档并及时回收你的窗口，默认不keep-open。
root仓库包绝对路径：/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0
必须读取root文件：
reports/v0-s3/product-gate0/s3-integration-offline-contract-01.md
reports/v0-s3/product-gate0/s3-integration-cpu-gate-review-06.json
reports/v0-s3/product-gate0/integration-fixture-explicit-retry-01.approval.json
reports/v0-s3/product-gate0/integration-fixture-classifier-block-01.json
plans/execution-control.json
root对旧实现17项PASS只是自检声明，未独审接受；固定24义务不能改。
