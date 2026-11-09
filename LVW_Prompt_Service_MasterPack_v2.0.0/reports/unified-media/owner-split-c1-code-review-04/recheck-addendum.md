# C1-RAW-01 定向复审

C1-RAW-01 已关闭。当前 C1 代码复审无开放阻塞：Fatal0 / Major0 / Minor0。本结论不代表 Stage PASS、真实模型质量通过或人签。

初审 review.md、receipt.json、compose-raw.log 保留原 Major 与失败复现；本文件和 recheck-receipt.json 仅记录修复后结论。对比初审围栏，只有 service.py 与 test_unified_video.py 改变，其他10个 C1 文件 SHA 保持。

修复位置 service.py 的 AppError 分支：raw=getattr(error,"raw_response",raw)。异常附带 Provider 原始响应时仍使用该响应；后续 CPU 组合异常未附 raw 时保留已经收到的原文。不改变取消后的禁止发布规则，也不把失败 parsed_spec 作为建议发布。

独立重跑原合成复现：成功外观模型响应之后，程序时序 policy 被拒绝；结果仍 failed/PARSE_PARTIAL，actual_raw_preserved 从 false 变为 true。原 wire SHA218505c7b0b66f4f73ef5054e098408aff477907eb3b0cc7e96bf605d124565f 未变。原复现无需改写，输出见 compose-raw-recheck.log。

独立定向测试 test_unified_video.py：13passed，原始输出 pytest-recheck.log。新增三分支覆盖正常组合、模型额外运动字段拒绝、CPU composition_policy 拒绝；错误分支断言 raw exact、failed/PARSE_PARTIAL、parsed_spec None，同时验证四源单调用、源证据、配置 SHA 与清理。既有取消/资源释放等视频测试也通过。未重复整套81测试，因为其余 C1 源未改且定向测试已覆盖唯一修复。

新 SHA 见 source-hashes-recheck-before.json 与 source-hashes-recheck-after.json，复审期间一致。完整 tracked HEAD diff 另存 git-diff-HEAD-recheck.patch。所有复审写入限定本目录；无真实模型、真实服务、GPU、网络或浏览器。CPU 模拟及既有 CPU 视频夹具不替代 C2/C3 真实覆盖。初审记录中的其他质量/原 raw 独立打分/固定分母/人工签署边界继续适用。

当前坐标 R1/WP-R1-U3-C1；本批完成定向修复复审；最后通过 C1代码/CPU复审；当前阻塞转 C2独审及C3真实质量/覆盖；全局路线仍冻结1.0.4；剩余完整离线/真实/独审/人签；下一责任人 parent Codex；无需新增本范围授权；证据本目录；精确停止原因是本次C1复审完成，不是Stage通过。完整 V0–V3 大纲沿用初审 review.md，无完成项增加。
