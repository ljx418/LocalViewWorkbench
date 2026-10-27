# 17｜数据、来源和版本设计

## 实体及权威

V0仅一次run/会话draft/显式导出。V1：media_ref、shot、model_run、prompt_revision、job/attempt。V2：asset_link、scene_revision、recipe_revision、batch、FTS、backup_manifest。V3：external_link、evidence_ref、outbox、handoff_receipt、workflow_allowlist。SQL是建表起点，版本化迁移和字段校验由实际实现补齐，不把设计DDL称为完整数据库实现。

shot_id是可编辑工作对象；revision_id不可变；prompt_id/模型任务ID不混用。analysis结果带model_digest、template_hash、input_hash、config_hash、采样记录；raw不可自动覆写。null表示未知，不用空字符串伪装已确认。人工锁定字段优先，模板升级不传播到既有revision。

## 四来源域

observation来自可见内容及对应帧；inference有不确定解释；user_evidence有来源引用与权限；creative_intent是用户扩展。引用来源不证明真实；史实/科学确认由用户依据外部资料承担，不自动“已验证”。静图运动只能在creative_intent。

## 时间与关联

frame_index是显示顺序，source_pts/time_base才是真时间；time_basis=sample_target或decoded_pts。scene [start,end)并带版本。下游Prompt引用scene_revision和evidence而非可变“当前镜头”。迁移不得将V0近似time改成精确。

## 修订与删除

append-only revision事务保存规范内容hash（UTF-8、排序key、数字格式固定）。shot head通过ETag CAS更新；已有revision没有更新删除API。用户删除资产默认tombstone/解除引用，原始媒体不删除；独立隐私清理工具在用户授权下按引用图删除LVW自有工件与相应记录，并生成不含内容的审计清单，不伪称append-only永久不可依法清理。

## 项目包

manifest列schema_version、app_version、IDs、内容hash、模板hash、媒体相对引用/可选复制、许可/来源备注；禁止绝对路径、凭据和任意代码。轻包不含模型/原片；完整包只含显式选择的媒体。校验所有路径、压缩比/解压上限、哈希、Schema、外键和来源授权后事务导入。

ID碰撞同hash复用，不同hash拒绝或生成映射并保留原ID，不能最后写覆盖。升级迁移先snapshot；回滚旧代码和对应snapshot，不能旧代码打开新schema硬撑。
