# Claude task boundary

先读AGENTS22、docs/30–32、plans/v1-revised-plan.json与v1-multishot-contract.json、本包及spec-manifest.json。仅实现checker/test和本窗口报告；spec/hash漂移停止ask Codex，不改合同/PRD/分母。执行python3 -B tools/verify_v1_plan.py与python3 -B -m pytest tools/test_verify_v1_plan.py -q；退出非零表示任务未完成，诊断日志本身不能PASS。报告真实candidate、commands/exit/loghash、files、生产工具入口、风险/provider信息（未知写unknown，不泄露配置）。提交本子分支，本地READY_FOR_REVIEW，向协调者worker_done。
