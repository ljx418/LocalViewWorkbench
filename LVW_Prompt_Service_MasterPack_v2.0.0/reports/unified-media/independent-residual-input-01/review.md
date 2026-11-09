# 独立残差输入审查 01

结论：离线检查支持将本候选提交一次有新增预算、候选绑定的有限真实验证。Fatal 0 / Major 0 / Minor 0。本结论不是模型语义 PASS、UM-04 PASS、Stage PASS 或人工签署。R1 完整槽 3/3 已耗尽；母授权 ACTIVE 和用户“继续到人工门槛”都不自动增加额度，当前不得执行 live08。

审查角色为 AGENTS11 要求的独立只读实例；仅证据目录写入。已读 AGENTS.md、治理 README、execution-control、docs24 最新章节、R1 packet、program02 request/approval。packet 内旧母授权文字不复活，当前采用 request/approval 明确预算和最新 docs24 边界。基线 c8f2880，最终提交 SHA 96e77ea3691cf68422ccd159c85985b4d9a118ec 已按 Git blob 字节核对并由 receipt 绑定；精确源码/测试及保护文件 SHA256 见 raw/reviewed-hashes.json。

## 方法与独立性

不使用实现测试结果作结论。从候选复制 provider/errors/models 和系统模板到新建 /tmp 隔离根，直接执行生产 build_temporal_sheet、temporal_pixel_measurements、analyze_video 与 _analyze_images。隔离资源模块为空 stub，不能探测 GPU；HTTP 客户端为纯内存异步替身。测试启动前封锁 socket.socket/create_connection、subprocess.Popen/run 和 os.system。原始结果记录 external attempts=0。未启动服务、浏览器、模型，未读真实媒体、probe 或视频解码。生产内存请求只是替身收据，不计为真实模型请求或验收。

独立检查器 raw/independent_probe.py 生成非均匀 RGB 合成图，覆盖源边缘/角点/内部。1–4 帧分别覆盖 19×13、768×432、432×768、768×768、768×1、1×768。共 158 个断言通过，最终标准输出与空 stderr 归档。首次、第二次检查器自造响应分别缺 done 和 done_reason，被现有 parser 正确拒绝，原失败 stderr 保留；修正的是独立测试响应格式，未改候选或放松 parser。

## 发现与证据

- 源数据：每个输入仅 convert RGB 后生成完整等比 thumbnail，不 crop、不拉伸、不替换、不复制输入帧。24 组布局中所有源区域的全部像素与各自完整源 thumbnail 逐字节一致，输入 bytes 不变。缩略图允许自然的信息损失，不声称原始 768 像素逐像素显示。
- 布局：输出为 1 帧 384×256、2 帧 768×512、3/4 帧 768×768；上部每格 384×256、图像区域最多 376×224。三帧的空源格保持空白。下部 1/2/3 个相邻残差分别用 768/384/256 宽格；最右边界精确闭合。横、竖及极窄图完整保留纵横比。0/5 帧、manifest 数不符及尺寸不符被拒绝。
- 残差：独立 oracle 用 Python 对每一个 RGB 字节计算 abs(a-b)，再独立 thumbnail，与候选输出所有残差区域逐像素相等。没有依赖 ImageChops.difference 计算 oracle。黑代表 RGB 不变，非零不证明运动或运镜。1/6 像素变化独立数值 oracle 为 16.6667%、RGB 均值 4.0，静态为 0。源帧原始尺寸上先算残差，再缩略，避免先缩略抵消变化。
- 标识：预览 preview-1..4-source-panels.png 已生成，四帧图已人工目视。上方 F1..F4 含实际秒数；底部 D1->2 等标签含 DERIVED abs RGB，无截断或遮挡。提示明确 D 是派生差分、不是源帧/场景/方向估计。没有样本路径、预期动作、答案标签、运动分类硬编码。缩略和残差仅为观测辅助，实际语义有效性必须真实验证。
- 生产接线：实际 analyze_video 生成 ONE PNG、向实际 _analyze_images 传全部 manifest、逐帧 SHA 和元数据。纯内存截获单次 post，images 长度1、PNG<=768；源数量4、wire数量1分别记账。num_ctx4096/num_predict768、temperature0.2、keep_alive0、无stream/think、raw 保留和 parser 保留。模板为 temporal-sheet/2-residual 与视频1.2.0。未增加调用/重试。全部时间和源 hash 与合成输入一致。
- 范围：相对 c8f2880 的候选代码差异只有 provider.py 与 test_provider.py。公共 DTO、分母、质量与资源阈值、守卫及 raw 没有差异；保护文件 SHA 留证。未改控制或授权文件。

## CPU 与内存界

生产 decoder 的 parse_ppm 明确限制每边<=768，VIDEO_LONG_EDGE768，seek_targets 最大四个实际样本；这里只静读源码，未运行 decoder。因此该路径最多 4×768×768 RGB，残差顺序处理，canvas 最多768²，工作量 O(4×768²)。源 RGB、copy thumbnail、单残差及canvas数目固定；temporal_pixel_measurements 的4个RGB/单残差/通道也在此固定界内，无随视频时长增大的列表。PPM 输入约<=6.75MiB；Pillow 内部通常每像素4字节，4源约9MiB，含临时图、输出/base64/元数据仍是数十MiB量级额外内存。实际本独立进程峰值RSS 83,056KiB，包含Python/Pillow/httpx/Pydantic和合成oracle，不能替代真实服务资源门限验证。

函数本身不重复强制768输入上限，依赖现有唯一 VideoKernel/decoder 归一化边界；未作为任意外部图像入口新增暴露。极端非生产超大图不在本测试范围。CPU归一化边界和模型GPU/RAM资源门限是不同证明，后者仍需新预算下真实收据。

## 剩余门槛

有限真实验证必须有预算增量裁决和新鲜子授权，绑定最终 SHA/harness/样本/模型工具/预算/清理；不得借总512动作剩余额度、旧slot或旧失败复活。本次只给离线可送验判断，不签模型语义、10/10、Stage或人类体验。原 live05/06/07 失败完整保留，不拼接为通过。
