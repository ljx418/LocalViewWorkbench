# S3-PREP-C — 固定候选 eligibility / 预览准备（非质量验收）

此准备批在已批准S3 toward V1衔接与COMPLETE-03本机非私有testSource范围内，按sample-preparation-child-01.json一次执行。产品Gate0仍未通过，旧S2仍7/8；最终10图6视频质量分母和>=8/10、>=5/6、关键幻觉0不变。预览不是LVW结果，不能当成标注或质量通过。保留11人工留样，三项private-labelled排除；仅child里32个已绑定内容SHA候选可访问，不重新枚举testSource，不另挑备用。

角色/允许范围：Orca可见ClaudeCode实现并执行此准备工具，Codex冻结范围并最终选集，独立上下文在识别前预标。允许新增tools/s3_sample_preparation.py、tools/test_s3_sample_preparation.py、reports/v0-s3/preparation-05/implementation/。不改其它代码/合同/旧证据/plan/manifest。实际预览仅保存在.gitignore明确排除的独立runtime root，不能提交图片/帧/原片、复制原媒体或发送媒体到任何remote/provider。源码与文本证据可提交。0模型/GPU/服务/网络/下载/完整checkpoint，不启Comfy/Ollama。

实现顺序：先检查已有media decoder/fixture工具是否可最小复用，再实现单一有限CLI owner及必要负例；这不是新的媒体平台。CLI参数显式child、code candidate、preflight、runtime output、receipt。先提交脚本/测试候选，绑定其Git字节与执行脚本SHA、child/catalog/holdout SHA以及本机已有Python/Pillow/FFmpeg/ffprobe版本与二进制hash；没有工具则报告BLOCKED，不下载安装。工具路径发现只做已有可执行文件的有限检测，不遍历模型/用户盘。root/child预算均按冻结记录，不能从历史聊天另拿槽位。

强制控制流：全局preflight不通过，selected媒体stat/hash/probe/decode均0；先用公开verify_s3_handoff.py通过139项，验证候选实际Git对象/脚本blob和child/catalog/holdout固定集合及输出隔离，再进入真实源读取。preflight与terminal独立文件、不可覆盖；原始失败留存，终态即消费child，不盲重试。计数明确区分源文件hash读取、probe/decode调用、admitted bytes、输出bytes与未测decoder磁盘IO，不凭exit0称质量合格。

逐文件：拒绝symlink/路径逃逸，stat身份+大小匹配目录并只hash一遍SHA，hash与原catalog不符则整体终态SOURCE_CHANGED，不继续解码或换文件。源只读，Pillow图片单次decode，检查20MiB/40MP，EXIF转正后RGB无元数据thumbnail最长边640；保存派生JPEG，不修改原图。视频只ffprobe一次、finite timeout，检查MP4/MOV/<=256MiB、duration<=60s、源帧<=8294400pixels及可解码。合格视频最多4次FFmpeg单帧提取（10%/35%/65%/90%时点，若时长极短且采样点不独立应少帧并警告），-nostdin/-hwaccel none/threads1，协议仅file/pipe，禁止联网/硬件推理。每进程限时，wall1200s总限/output80MiB；只停本轮owned PID，不停其它进程。超出上限/损坏/不可解码只明确NOT_ELIGIBLE+稳定原因，不能以备用替换。尺寸/时间属于容器探测，不能伪称实际PTS已由完整解码证明；输出实际能证的采样信息与限制，重复hash帧如实披露。

输出：每张候选图thumbnail，每视频最多4张帧，带asset ID/不含预期语义答案的本地contactsheets与静态index.html。页面明确“独立预标前素材预览，不是项目识别输出”；用file相对路径可打开，可看到原始候选ID/类型/探测尺寸时长/排除理由/采样点与预览。不得调用产品分析，不自动编造人物/场景/动作标签。不建立额外NSFW审批门禁。原始样本路径只保留本机，不提交额外全路径或EXIF。截图/图像不上传Git。

临时staging一律finally清理并实测；成功preview runtime目录为下一步独立预标所必需，作为明确登记的保留产物而非“零残留”，记录绝对本地路径在runtime receipt、提交receipt只记project-relative或脱敏路径、树文件hash/大小。失败preview不得当未来正例；失败运行已有派生产物可保留在标注FAILED_NOT_QUALITY_EVIDENCE的同run目录供诊断，若本轮能完整清除则给实际测量，禁止伪造清理。证据收据含所选32固定分母、admitted/eligible/ineligible/notrun数量及原因，总和守恒。独立质量集最终10+6需Codex按预览和预标方案再冻结，不以eligible计数代替语义覆盖。

测试用合成小图/小片和假source adapter，测试全局preflight失败0源调用、child/candidate/catalog drift拒绝、symlinkescape、exact/one-over限额、changed source整体失败、损坏素材NOT_ELIGIBLE、少帧/重复提示、wall/output预算、终态不可覆盖及owned cleanup。测试可合成非私有小样，不访问child真实32项；整个真实运行只有一次。定向测试通过并提交候选后才运行child。保留命令/raw stdout stderr/exit、工具版本hash、candidate/child/preflight、真实终态、精确预算与retained-preview路径；只READY_FOR_REVIEW，不Stage PASS。遇连续两次无进展交接，不增加运行槽。所有新JSON合法，Git作者ljx418 <1173696783@qq.com>。完成提交候选和文本证据，worker_done full SHA、32候选资格结果、预览入口及剩余缺口。
