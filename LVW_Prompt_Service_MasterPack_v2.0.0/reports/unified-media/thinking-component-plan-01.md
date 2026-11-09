# thinking能力组件诊断：一次，不是Stage验收

先决事实：metadata-only探测以5秒、0模型/0媒体/0有效完整轮完成并清理。实际/api/show列出vision与thinking；/api/tags未列vision不能据此误判安装为纯文本。未下载/迁移/改动模型或永久配置。

本轮在既有R1范围内对同四个保留PPM样本调用一次实际OllamaProvider，显式private thinking=True。默认图片和视频公共请求仍think=False；未暴露新前端选项。Provider必须先得到有效list-of-str /api/show thinking能力，再经原model_action冻结/预算门禁发送；没有能力不发送。num_predict768、ctx4096、23552MiB/2GiB/420秒分析与30秒释放不变。

诊断不是公开入口完整验收，不消耗/声称一个完整checkpoint。有限子授权1模型动作/600秒/1native服务/0下载云付费浏览器，绑定源码/工具/模型/四PPM、同F+D图与源计量，运行中资源监测、真实lease释放、原PID/birth/nonce退出及私有temp清理。失败不会自动再试。

只保留模型最终content原文、wire响应hash、token统计和thinking字段存在/长度，不保存内部thinking内容；因此这份组件材料不能代替最终公共ModelRun原始证据或Stage质量结论。若被768预算截断，记录为配置诊断而非语义通过；不自行放宽门限。

独审发现并修复的执行器初始化终态缺口、能力类型校验及注释问题均保留初始复现。修复后组合138项通过；actual默认请求与前候选一致。封存+独审通过才执行一次组件调用。之后先统一补齐UM02真实类型拒绝、UM05准备/排队取消及分析请求/配置证据，再考虑一次完整真实复验；不继续同候选盲跑，不请求重复GPU或候选权限。
