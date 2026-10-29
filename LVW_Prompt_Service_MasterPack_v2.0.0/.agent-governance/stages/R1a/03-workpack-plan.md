# R1a Workpack Plan

## WP-R1A-00：R0 复用复核与冻结

锁定 OpenAPI 子集、V0 可复用 parser/模板、Python/Node 依赖、许可、目录和安全边界；生成 Stage manifest。只做离线检查。

## WP-R1A-01：同源 FastAPI 垂直路径

实现健康、受控上传、分析 job、job 查询、model-run 查询、同源静态资源和稳定错误；Ollama transport 可注入，离线测试不得真实调用模型。

## WP-R1A-02：React 单图工作台

实现图片选择/预览、上传、分析、轮询、raw/结构化域、显式采纳、四输出、复制和 TXT/JSON 下载；模型失败不覆盖人工稿。

## WP-R1A-03：离线 Stage Checkpoint

执行 Python 单元/API/合同负例、TypeScript、React build、静态外联/秘密/绝对路径扫描和 V0 回归。形成实现收据，只可报告 `READY_FOR_REVIEW`。

## WP-R1A-04：真实路径与独立审查

需一次性授权后，使用固定 `testSource` 非私有图片和本地 Ollama 运行同源生产入口；随后由隔离 reviewer 复算固定分母、生产接线、原始证据和清理。只有 Fatal=0、Major=0 才进入人工体验门槛。

## WP-R1A-05：人工体验签署

项目负责人检查上传、分析、编辑、复制/导出、错误提示和整体可用性。人工签署只批准 R1a 体验切片，不批准 V1 或生产发布。
