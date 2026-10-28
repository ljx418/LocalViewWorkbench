# 14｜V1实现方案：独立服务与版本

## R0：从MVP转独立运行

复用V0模板、样本、模型配置、预处理纯函数与已知失败；直调Ollama的图/4帧再测。确认Structured Outputs支持；不支持则保留raw和PARSE_PARTIAL，不自动换云。关闭Comfy后测试，证明独立性。模板搬运记录原许可。

R0 在当前批准顺序中紧接已验收 V0-Min，不再等待 V0-S3。它只复核独立服务所需接口、复用边界、依赖和许可；不得把尚未完成的 V0.1/V0.2 发布项改写成已通过。

## R1a：单图简易前端提前切片

R1a 在 R0 后、V0-S2 前执行，使用最终 React/FastAPI 工程交付第一条可用产品路径：受控单图上传→本地 Ollama 分析→raw/观察/推断/未知与建议→显式采纳→人工编辑四输出→复制/TXT/JSON。模型离线、失败或超时时，人工编辑与导出仍可用。

后端只实现正式 OpenAPI 的必要子集，不新增临时 endpoint；浏览器不直连 Ollama。分析采用单 GPU、单请求的有界执行，保留 job 身份和明确终态，使 R2 能在不改变前端调用语义的前提下补齐 attempt/CAS、取消晚到、幂等和恢复。R1a 不宣称完整修订、CLI、便携包、视频、资产库或 V1 PASS。

## R1：人工优先骨架完成

FastAPI同源SPA、受控媒体multipart streaming、ShotSpec、六模式/四目标、纯CPU编译先落地。SQLite foreign_keys/WAL；shot可更新、revision append-only、job记录。初始DDL见contracts/storage.sql，生成迁移而非运行时随意改表。已存在介质hash相同可复用内容引用但业务asset不同。

R1 复用并扩展 R1a，不另建前端。React和CLI共用Application Service。人工新建无媒体shot；保存传If-Match；同事务读取当前etag、验证、插入revision、更新head。冲突412显示当前版本，不覆盖。revision hash只针对规范化内容，服务器时间/随机ID不参与内容相同判定。

## R2：模型与任务

submit分析获得202；单worker领取queued，分配attempt_id/lease_token，输入预处理和Ollama请求。请求一律本地固定base_url；不传工具或外部URL。format校验后保存raw/parsed，partial可带建议。模型返回不写人工revision；用户采纳再保存。

cancel：queued直接终止；running设置cancel_epoch并关闭/停止当前调用，资源仍busy直至实际释放。终结CAS必须匹配attempt_id+epoch；晚到丢弃。异常try/finally卸载并轮询，不能仅依赖下游节点。默认并发1，竞争外部GPU返回RESOURCE_BUSY。

V1进程重启把running标interrupted，不自动重放，用户显式retry新attempt。幂等submit同键同载荷返回原job；同键异载荷409。取消/保存幂等各有作用域，不能重用一个键覆盖不同动作。

## 编译和目标映射

从四来源域和人工锁定字段生成目标文本，按用户锁定>镜头>场景>项目配方>模板>机器建议合并；冲突列表可见。natural输出中英已有内容；image选自然或tags；edit输出源保持/变更/约束；motion输出主体动作/相机/节拍/时长。缺事实留unknown，缺英文留待补，不额外偷偷调用LLM。

## 导出与便携

TXT/JSON/轻项目包显式导出；V0 JSON导入创建新的来源和revision，不能假称V0已保存不可变版本。发布包包含便携Python、FFmpeg、dist、依赖锁/许可；模型仍外置。no npm/pip运行安装。中文路径、无开发工具宿主、恢复和断网验收。

## 测试与产物

24组合编译、API/Schema/类型、ETag/幂等/取消、原图不变、无模型编辑、真实推理/资源、12图+6片、便携包。R1/R2所有产物必须是代码和真实测试，不以HTML设计稿代替React。
