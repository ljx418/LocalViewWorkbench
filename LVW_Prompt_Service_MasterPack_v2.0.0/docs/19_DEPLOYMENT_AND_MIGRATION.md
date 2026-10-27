# 19｜打包、本地部署与迁移

## 三种交付强度

V0：依赖已验证宿主的增量包，workflow+必要扩展+规则+绑定/安装/回滚。不复制Comfy/PyTorch/模型；同机重定位测试，不宣称任意机器即用。

V1：Windows便携Python/FFmpeg/前端dist/锁定依赖+启动诊断，外部已有Ollama与模型作为明确前置。无Node/npm/pip运行安装、无现场编译、无模型下载。venv不能未经验证直接当可移机运行时。

V2/V3：软件、数据、模型分开，项目轻包/完整包、SQLite一致性备份、升级/回滚、新用户/干净宿主验证。Linux发行不是V1必选；需要时单独按ABI构建，不能复制Windows二进制。

```text
LVW/
  releases/<version>/{python,app,frontend/dist,bin}
  launcher/ config/ manifests/
  data/{catalog.sqlite,artifacts,temp}
  projects/ exports/ backups/ reports/
# Ollama模型外置，项目包只记digest，不重复存权重
```

## 安装与诊断

检查OS/驱动、端口、写权限、剩余磁盘、FFmpeg、依赖hash、模型存在和能力、SDK版本。仅修改当前应用允许目录，保留用户未提交变更。供应链目录列license/SBOM、原始来源和可逆patch。运行禁止自动更新/拉包；依赖缓存只属于构建阶段。

## 离线

禁外联并观察尝试，保留127.0.0.1；预置权重不清除。浏览器无CDN字体/图片/分析脚本；Ollama云功能按实际版本关闭，插件云provider/回退禁用。所有配置需实测，不把开关当安全沙箱。

## 数据迁移和回滚

SQLite backup API取一致性快照，不只复制正在写的.db。备份manifest、hash、schema、模板和工件引用；先在新目录restore+integrity_check+foreign_key_check+计数/修订hash核对再切current。业务数据不放release内。升级失败恢复旧代码+匹配旧库；保留用户升级后新导出文件，不删除外部原媒体。

新机器媒体通过用户选根重绑定相对路径与hash，缺失可人工编辑但不能假称可回看。模型可复用按digest检验，不以同tag当相同权重。隐私导出不含凭据、绝对路径或默认全片。

## 预算

V0≤20MiB增量目标；V1核心≤2GiB目标，模型/用户媒体不计；超预算需依赖清单与批准而非默默增包。运行用户手动clone=0、pip/npm=0、CUDA编译=0。V3验证完整恢复时间并报告实测，不预先写无法支持的RTO。
