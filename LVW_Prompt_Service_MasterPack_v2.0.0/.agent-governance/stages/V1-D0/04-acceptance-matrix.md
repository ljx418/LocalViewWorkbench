# D0 acceptance

checker正常验证新版V1=29/V2=38/V3=47；原21/30/39原序列保留，MS8与R22/V1-M1一致；DAG无环，M1依赖R1、R2依赖M1；旧R1packet与canonical合同hash不变；现有人签仍空；预算不清零、原阈值不降。负例需非零退出并稳定错误类别，原始stdout/stderr/exit。独审须具体位置/触发/预期/实际/证据，区分Fatal/Major/Minor。只有文档/工具检查，不算产品验收。
