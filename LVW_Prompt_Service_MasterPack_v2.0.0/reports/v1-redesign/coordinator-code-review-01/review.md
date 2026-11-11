# Codex协调者代码审查：CHANGES_REQUIRED

候选372575b，收据f3675c2。变更范围遵守D0工作包，2工具文件及实现报告；原命令/输出SHA核对吻合。34项自检不替代本次审查。

## D0-CODE-M01 Major：空职责/命令清单被放行

位置tools/verify_v1_plan.py check_ownership：if allowed and allowed != expected / if commands and commands != expected。as_list对空数组返回空数组后跳过比较。真实设计D0 stage-control不在spec-manifest文件集合中，校验器也未验证D0 PAYLOAD_MANIFEST，所以仅将该文件allowed_files或commands改为[]，不更新任何权威fence，CLI仍exit0/RESULT PASS。

期望空清单/空命令必拒绝，冻结D0包任何字节/清单漂移须被payload校验识别。三个真实布局临时副本反例见checks.json和原日志，原始权威文件未改；baseline0、两个坏例实际均0而期望非0。修复须由原实现者完成，不改plans/docs/合同/权威hash；增加独立负例并保留原失败。

尚未合并、未Gate0/StagePASS、未产品/人签。只有0产品动作；临时副本由TemporaryDirectory实际移除。代码就绪须待修复复验和隔离设计审查结论。
