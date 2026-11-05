# 请求Schema与解析边界一致性修复

full-v0-auto-01的WDDM路径已真实通过静态/跟拍/快切；VFR首帧因observations单项505字符超过原400门限而PARSE_PARTIAL，done_reason=stop且未发布结果。全部文件安全负例通过，公开14/15局部成功；整个九项Stage仍NO_GO。该次失败及原清理全部保留。

问题在请求grammar未声明数组item.maxLength，parser却已按400/100拒绝。补齐这四类item的原上限并简短提示分条；不增加context/predict、不截断、不接受坏结果、不改变调用/重试预算。48定向测试与隔离审查通过；failed-response.json来自原始history，加入执行payload封存以保护回归输入。下一步完整offline36后自动派生full-v0-auto-02，不复用旧run或跨运行拼接。
