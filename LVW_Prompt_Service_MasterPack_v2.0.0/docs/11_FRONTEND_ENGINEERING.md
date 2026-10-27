# 11｜前端工程与界面原型

## V0

原生Comfy工作流/同源JS面板，输入、规则、raw/建议、人工稿四组。复制/导出脱离GPU链；必要独立纯CPU人工图或JS Blob导出。只读ShowText不算可编辑。raw不能经自动清理器覆盖用户稿。默认不localStorage持久化，平台现有缓存/历史另披露。

## V1–V3

React+TypeScript+Vite+CSS Modules，同源FastAPI托管dist；构建产物本地，不使用CDN图标/字体/分析脚本。开发Vite代理仅开发用，生产无Node服务，无通配CORS。初期React hooks/fetch即可；路由/状态库仅有实际需求时ADR，不重复前端框架。

```text
src/
  api/{client,types}.ts
  features/workbench/{MediaInput,AnalysisPanel,ShotEditor,PromptOutputs,RevisionHistory}.tsx
  features/library/{Search,AssetList,RecipeEditor}.tsx
  features/integrations/{ConnectionStatus,SourceReferences,HandoffReceipts}.tsx
  components/{Button,Field,Alert,Dialog,EmptyState}.tsx
  styles/{tokens,base}.css
```

工作稿带dirty flag和etag；建议到来不改变草稿；明确采纳/另存。切换模式/目标只重新编译，不能隐式调用模型。文件预览URL及时revoke；媒体不全量base64放React state。耗时操作poll带退避、AbortController与卸载清理，取消poll不伪装取消服务器任务。

F01–F07对应真实产品测试，见plans。键盘能操作所有关键控件，焦点清楚；360px核心动作无横向隐藏，200%可滚动操作；长中文字、错误、空状态必须覆盖。

## 原型说明

HTML预览示意设计和交互，不是生产React代码，不连接模型。四版本页面展示范围差异、六模式、四输出、人工输入与异常兜底、资产和集成样例。所有演示数据显式标记；上传仅在浏览器本地预览，模拟分析不分析图片内容。
