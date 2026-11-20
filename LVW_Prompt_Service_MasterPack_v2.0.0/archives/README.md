# 历史过程产物归档

用户批准本轮整理后，将历史combined-raw、candidate-source和pytest临时过程树无损压缩。当前生产代码、冻结合同、阶段结论、人签、原始执行器输出/收据及失败历史未改写。

[逐文件目录与SHA256](history-2026-11-20/catalog.json)记录原路径、Git blob、大小、内容SHA256；[压缩包](history-2026-11-20/process-artifacts.tar.gz)保留成员原始字节。归档验明后才移除工作树副本，Git历史不改写。旧SHA256SUMS或报告引用的过程树复现前需要恢复；缺失不允许被当成PASS。部分未跟踪缓存/测试链接移到仓库外隔离区，索引见reports/development-refresh-2026-11-20/cache-cleanup.json；不跟随链接读取目标。

在产品包目录运行：

```bash
python3 -B tools/archive_history.py verify
python3 -B tools/archive_history.py restore --destination /tmp/lvw-history-replay
```

恢复目标必须全新或空目录，工具拒绝覆盖当前项目。目录下重建原仓库相对路径，文件哈希验证后供历史调查；这不是重启旧授权、复用旧PID或重新宣布旧运行成功。

当前入口改由docs/INDEX.md、docs37/38和唯一execution-control引导。旧阶段设计文本保持原文，避免破坏冻结合同与旧证据引用。源码提取和pytest整树以后不再默认加入新报告；保存Git身份、必要原始输出及恢复所需最小集合。
