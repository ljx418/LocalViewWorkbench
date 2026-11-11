# 15｜V2实现方案：结构化创作资产与Agent

## R3：镜头与时间

视频导入引用+hash，ffprobe/解码器读time_base、start_pts、best_effort_timestamp，帧索引保存实际PTS和time_base分子分母。规范时间t=(pts-origin_pts)*num/den，存整数ticks与有理数，展示ms四舍五入；片段[start,end)。VFR禁止frame_index/平均fps充当真时间。

PySceneDetect给候选切点，再映射实际解码帧；缺失/不单调PTS标time_unverified并可人工校订，不能伪造精确。人工改边界新版本保留旧，Prompt证据引用具体scene_revision。每镜头有限窗口，最多8帧需配置实测；长片只保留活动窗口，释放解码buffer，不线性增长内存。

## R3：资产、检索、配方与对比

asset是引用+类型+来源权限；content hash去重不是删除源文件依据。media、scene、prompt_revision、style_recipe组成关系；library搜索文件名/人工标签/描述/来源，FTS5明确不是视觉语义检索。中文采用经目标SQLite验证的trigram/确定性分词方案；不支持时降级有界LIKE并说明，1000引用性能仍需达标。

style_recipe append-only、版本化字段/锁定/来源；模板改动不修改旧Prompt。属性对比使用同一schema和双方版本，显示observed/inferred/unknown，**不是身份或真实性鉴定**。QC只输出黑帧/冻结/模糊候选、算法参数和采样证据，不自动删除或拒绝素材。导出分镜CSV/Markdown/JSONL+manifest+来源域；机器标签不冒充人工标注。

## R4：任务恢复

batch拆child job，独立状态、父进度是已终结项/总数；失败项不回滚成功项。claim用原子事务，lease过期转interrupted，重试新attempt；写入fencing令牌。临时工件在attempt目录，成功同卷原子rename后事务注册；重启扫描未注册临时文件按保留期清理，绝不删引用工件/原片。

明确at-least-once调度+幂等提交，不承诺任意副作用exactly-once。SQLite一次writer串行，busy_timeout/有限重试；磁盘满回滚并保留人工工作稿提示。备份通过SQLite backup API一致性snapshot，manifest哈希，先校验再restore。

## R4：MCP

8白名单工具见合同，stdio桥接已有服务，schema复用Pydantic；只传资产/镜头ID，不允许任意路径/SQL/Shell/URL。授权scope对应读/分析/修订，不包含内容审查。长任务立即返回job_id，后续poll/cancel，不占用会话直到视频完成。实际Codex或Claude Code客户端发现、调用、错误/取消测试必做。

## V1升级

迁移前backup，事务DDL加表/索引，原revision ID/hash不变，重建可重建的FTS索引。中途故障回旧代码+旧库。资产缺失显示offline_missing，用户选择根目录重绑定后hash校验，不偷偷联网补文件。

## 产物

时间与镜头模块、资产/配方UI、迁移SQL、数据导出、batch/recovery、MCP桥接、测试/兼容报告。关键验收A13–A17/F06/X04–X06，累计V1回归。


## 2026-11-11批准的V1范围与角色修订

R22短视频切镜/逐镜头子集提前到V1-M1；V2仍承担完整R13、长片、资产/FTS/配方等，不能用MS01替代完整A13/X04。 权威执行索引见[新版V1计划](30_V1_REVISED_EXECUTION_PLAN.md)、[详细架构/合同](31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md)、[验收与Orca协作](32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md)。本节覆盖此前“自动切镜全部只在V2”的范围表述，不回填任何产品PASS。
