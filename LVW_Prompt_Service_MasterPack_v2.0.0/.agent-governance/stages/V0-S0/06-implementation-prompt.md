# V0-S0 correction-09 Offline Remediation Prompt

```text
工作目录：LVW_Prompt_Service_MasterPack_v2.0.0。
当前坐标：V0 / V0-S0 / WP-S0-26 / GATE1_IMPLEMENTATION / RUNNING。先读 WP-S0-25 review、privacy incident 与候选 `57f7718...`。

只允许修改 `tools/v0_s0_live_probe.py`、其测试和 correction-09 offline receipt。不得启动/探测服务、联网、读取媒体、修改产品 candidate/合同/门限或历史 evidence。

关闭三项发现：只落目标匹配和不可逆进程计数，禁止全量命令行及嵌套编码标识进入 artifact；按 schema 接受非空 string camera_motion 并拒绝 list；运行前校验实际 harness 文件 SHA 与指定 commit blob，mismatch 稳定 fail-closed、零服务启动，并把 commit/blob/file hash 写入 artifact/receipt。保持既有 24 项 fixture。

输出 READY_FOR_REVIEW 和离线收据，不得 Stage PASS。无 live 授权，产品四项保持 NOT_RUN。
```
