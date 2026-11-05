# 原子停止的中断恢复

570e231候选通过offline42（537测试/5检查），隔离审查仍发现一个Major：若root已停止而stdout/exit/JSON回传失败，Python尚未保存children baseline。原路径保持failclosed、清理不冒充成功，但可能保留无法安全清理的本轮子进程；尚未真实启动该候选。

纠正：同一原生操作在Kill前，把本轮run/candidate/auth、root精确birth、唯一nonce和children快照写至预登记隔离temp文件。FileStream CreateNew/WriteThrough/Flush(true)成功后才Kill。Python finally在解析stdout前恢复；只接受预登记plain/no-follow、有界稳定普通文件、无重复key、完整身份以及精确父子出生/链与CIM精度关系。损坏、缺失、替换均拒绝，不能猜空children或借旧baseline；成功stdout必须与持久化一致。复用原已绑定children清理和未知子进程拒绝策略。

复审过程中发现File.Open的FileOptions重载不存在，已纠正为六参数FileStream::new；本机Windows纯文件API验证实际持久化、restore和临时根删除成功，无进程查询、Kill、服务或模型动作。另补齐恢复记录的root/parent精确出生排序，拒绝子进程早于父进程。定向CPU51项通过（包括超时、坏JSON、missing、错auth、错parent/出生、symlink）。最终隔离复审及新候选离线门禁另记。

不更改任何公共产品合同、固定分母、resident/active义务或门限，不把定向结果拼接成Stage验收。
