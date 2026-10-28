# V0-S0 Checkpoint Plan

## 实现内循环

每次只运行受影响的只读诊断和定向合同检查。原始命令、退出码和日志不可由手写摘要替代。

## Stage checkpoint

1. 校验 Stage manifest、产品合同和固定分母指纹。
2. 复算 inventory/node binding 与目标环境一致性。
3. 从真实公开入口追踪单图和四帧调用，不接受内部 fake 代替 owner。
4. 核对超限、VFR、取消、晚到、未知占用和资源释放证据。
5. 扫描秘密、绝对私有路径和原媒体泄漏。
6. 独立审查者报告 Fatal/Major/Minor；Fatal/Major 必须为零才可由 Codex 给出 baseline 出口。
7. 人类签署不在 S0 baseline 自动化范围；任何真实运行授权单独保存。

correction-03 checkpoint 还必须一次性复算 R2-IR-01 至 R2-IR-07。公开入口、内容 oracle、`<23 GiB`、远程连接观察与每个失败 run 清理缺一不可；局部修复不得逐项换取提前 PASS。

correction-11 checkpoint 必须逐分支证明：零 owned start 的身份/preflight stop 将所有未执行派生检查标为 `NOT_REACHED`；owned 资源不存在与 target integrity 未比较分别表达；服务启动后的真实失败仍为 `FAIL`。历史 correction-10 receipt 不得改写，固定产品分母仍为四项 `NOT_RUN`。

## 允许裁决

`STAGE_BASELINE_COMPLETE` 仅表示 S0 盘点和最小探测完成；产品用例仍为 NOT_RUN。否则使用 `NO_GO/BLOCKED/WAIT_BUDGET/WAIT_AUTH`。下一 Stage 必须另建并冻结 packet，不能自动推进。
