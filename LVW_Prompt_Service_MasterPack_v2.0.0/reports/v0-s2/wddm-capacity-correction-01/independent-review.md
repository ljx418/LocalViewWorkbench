# WDDM纠偏隔离复核

Reviewer `/root/s2_wddm_policy_review`，fork_turns=none，只读。首次发现Major2：缺实际XML原证据复算、派生ownership字段可造假；均在真实执行前关闭。最终Fatal0/Major0。独立五模块41测试PASS。原XML+首CSV+NVIDIA工具hash留证，测量重新解析比对WDDM/单GPU/PID/保守内存与全部派生owned/unowned/foreign/admission/resource_policy字段。未见数值、分母、性能/释放或模型控制/kill所有权放松。不是Stage PASS，尚须真实完整矩阵及Stage独审。
