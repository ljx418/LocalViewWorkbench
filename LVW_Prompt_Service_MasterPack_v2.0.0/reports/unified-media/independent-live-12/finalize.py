from pathlib import Path
import json,hashlib
O=Path(__file__).resolve().parent;R=O.parents[2];result=json.loads((O/'recomputed.json').read_text());ctl=json.loads((R/'plans/execution-control.json').read_text())
def row(n,status,obligation,owner,oracle,evidence):return {'id':f'UM-{n:02d}','status':status,'obligation':obligation,'production_owner':owner,'oracle':oracle,'evidence':evidence}
rows=[
row(1,'PASS','图片旧路径及人工稿保护','React App / media upload / AnalysisService','live12真实图片raw与模型运行/显式采纳导出对应；raw只出现红方块和深蓝底，与输入相符；原人工稿保留由原浏览器断言和无错误终态证明',['live-12/image-model-run.json','live-12/image-draft.json','live-12/browser-result.json','live-12/launcher.log']),
row(2,'PASS','视频格式/大小/时长/像素/空损坏拒绝','MediaStore.ingest_video / validate_probe / HTTP body limit','实际public duration/corrupt422；本独审CPU public受控格式/像素拒绝与空视频拒绝，明确无job/provider/残留；60s/256MiB/8294400px exact及one-over由候选生产validator复算；streamed假Content-Length负例由候选测试通过',['live-12/negative-0.json','live-12/negative-1.json','independent-live-12/cpu_supplement.py','independent-live-12/cpu-results.txt']),
row(3,'PASS','真实PTS/四帧/少帧局限/源SHA','VideoDecoder frame_manifest / AnalysisService / OllamaProvider','1,3,5,7秒PTS、源视频SHA、四PPM SHA与ledger一致；已有PNG重序列化PPM精确hash匹配；2帧manifest不复制、空/重复PTS拒绝CPU复算。未重新decode，不继承旧审查结论',['live-12/video-model-run.json','live-12/runtime-evidence/provider.jsonl','independent-live-12/recomputed.json','independent-live-12/cpu_supplement.py']),
row(4,'FAIL','全采样帧真实语义/raw分离','OllamaProvider.analyze_video / parse / model','真实raw保留且计算metadata准确，仍断言红框相对网格consistent，并据red subject and grid stationary推lighting/compression；与可见位置变化及自述systematic spatial shift矛盾。offset/unknown字样不能消除错误观察；不要求相机物理方向',['live-12/video-model-run.json','independent-live-12/reconstructed-live12-sheet.png','independent-live-12/recomputed.json']),
row(5,'PASS','准备/运行/排队取消及晚到不发布','AnalysisService.cancel/run / MediaStore / decoder cleanup','真实第三次provider attempted后cancelled/released且无result_ref，导出维持已采纳源；CPU生产owner检查queued cancel无provider、preparing barrier清理后终态、晚到成功不发布，mock只替换外部原语',['live-12/cleanup-job-terminals.json','live-12/after-cancel.json','live-12/runtime-evidence/provider.jsonl','independent-live-12/cpu-results.txt','independent-live-12/cpu_supplement.py']),
row(6,'PASS','显式采纳/脏稿确认/导出归属','React adoption/export / draft state','before-video-adopt仍指图片run；video-adopted显式指视频run；after-cancel改稿保留源；JSON/TXT一致。原浏览器once dialog accept与生产采纳操作断言通过，无route/mock',['live-12/before-video-adopt.json','live-12/video-adopted.json','live-12/after-cancel.json','live-12/offline-draft.txt','live-12/browser-result.json']),
row(7,'PASS','失败/离线仍可人工','React editor/export / runtime stop','真实native stop后unreachable/pid null，人工video_prompt改为OFFLINE_EDIT_AND_EXPORT并保留TXT/JSON；CPU释放未证实失败分支resource_state unknown，不冒充成功',['live-12/runtime-stop.json','live-12/offline-draft.json','live-12/offline-draft.txt','independent-live-12/cpu-results.txt']),
row(8,'PASS','本机资源租约/释放/隔离','Provider.acquire/release / resources / NativeRuntime','3admission/lease/attempts，3释放各末3样本inventory_empty且GPU恢复baseline+1024内；峰21217<23552，RAM10032>=2048；native PID27672/birth639298255854124545/nonce匹配exited，NO_CLOUD/loopback日志；本次审查不改资源',['live-12/runtime-evidence/provider.jsonl','live-12/runtime-evidence/f7f76b0011ca4d92a735b14fbfc59c44.owner.json','live-12/runtime-start.json','independent-live-12/recomputed.json']),
row(9,'PASS','统一入口/真实headless组合','START_LVW.cmd / run_local / production React / FastAPI','候选真实launcher与default_app对端日志、Windows health构建ID、原浏览器closed/0page errors/0external；无本独审browser重启。工具当前hash全部匹配execution bindings',['live-12/launcher.log','live-12/windows-health.json','live-12/browser-result.json','live-12/bindings.json','independent-live-12/recomputed.json']),
row(10,'PASS','冻结身份/清理/独审','authority / program ledger / launcher cleanup / isolated reviewer','所有frozen/sample/tool hashes复算；START_LVW仅Git LF/工作树CRLF规范化等同；原生owner exited，API原PID birth不存在、/proc监听为空，launcher确证API退出和owned temp removed；SQLite child终态3/1/56s，全局15/5/1163且0active；固定10项独立检查。此PASS仅身份/清理/独审已完成，不代表总门禁PASS',['live-12/authorization.json','live-12/authorization.terminal.json','live-12/receipt.json','independent-live-12/raw-hashes.json','independent-live-12/recompute.py','independent-live-12/recomputed.json'])]
coverage={'schema_version':'lvw.independent-coverage/1','candidate_sha':result['candidate_sha'],'packet_version':'1.0.3','run_id':'live-12','denominator':10,'pass':9,'fail':1,'blocked':0,'skipped':0,'not_run':0,'items':rows,'rows':rows,'decision':'NO_GO','scope':'UNIFIED_MEDIA_EARLY only; not Stage/human/full V1 signature'}
(O/'coverage.json').write_text(json.dumps(coverage,indent=2,ensure_ascii=False)+'\n')
receipt={'schema_version':'lvw.independent-review/1','role':'isolated_read_only_reviewer','review_session':'/root/live12_independent_review','run_id':'live-12','candidate_sha':result['candidate_sha'],'product_source_ancestor':'d3b4ddde5311299083e398dfe08c1ab9c4e38ea8','packet_version':'1.0.3','packet_manifest_sha256':'c20246bd153136c91ce27f7e125716c8c0b3848ffa58e7fe9857ce5f2e343502','gate_version':'lvw-unified/1','slice_acceptance_ids':[x['id'] for x in rows],'denominator':10,'pass':9,'fail':1,'blocked':0,'skipped':0,'not_run':0,'Fatal':0,'Major':1,'Minor':0,'decision':'NO_GO','findings':[{'id':'M1','severity':'Major','acceptance_id':'UM-04','summary':'错误否认可见红框/网格相对位置变化，并提出无证据lighting/compression解释，且与systematic spatial shift自相矛盾。','raw_locations':['observations[4]','inferences[1]','inferences[2]'],'physical_camera_direction_required':False,'offset_unknown_alone_not_pass':True}],'model_actions':3,'completed_model_calls':2,'cancelled_attempts':1,'lease_releases':3,'child_recorded_elapsed_seconds':56,'global_ledger':result['budget_global'],'cpu_check_result':result['cpu_results'].strip(),'new_model_gpu_service_browser_probe_decode_downloads':0,'ledger_write':False,'candidate_modified':False,'prior_pass_inherited':False,'stage_pass_claim':False,'human_signoff':None,'full_v1_acceptance':False,'evidence':['review.md','coverage.json','raw-hashes.json','recompute.py','recomputed.json','cpu_supplement.py','cpu-results.txt','candidate-source-hashes.json']}
(O/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
outline='\n'.join(f"| {s['stage_id']} | {s.get('title','')} | {s['completed_substeps']}/{s['total_substeps']} | {s.get('machine_acceptance','')} / {s.get('independent_review','')} / {s.get('human_signoff','')} |" for s in ctl['development_outline'])
text=f'''# live12 独立只读验收

**建议 NO_GO：固定10项为9 PASS / 1 FAIL；Fatal0 / Major1 / Minor0。UM-04真实时序语义失败。** 这是隔离独审建议，不是Stage裁决、人类体验签署或整个V1验收。

候选 `{result['candidate_sha']}`，R1 packet1.0.3 / gate lvw-unified/1，精确raw哈希见raw-hashes.json。先读规范/候选，收到执行终态信号后才读live12。候选gitblob导出后只运行CPU原语与受控生产owner检查；未调用GPU/model/API服务/browser/媒体probe/video decode/下载，未写任何执行账本，未继承实现者或旧审查PASS。

## Major M1 — UM-04

原始模型 `observations[4]` 说红框相对网格位置“appears visually consistent across all source frames”；`inferences[1]` 以“red subject and grid appear stationary”为前提，把差异解释为lighting/compression的可能性。另一方面，`inferences[2]` 承认consistent x-offset suggests systematic spatial shift。技术字段仅复述x-offset与subject stationary，未修正错误的相对位置观察。unknown/物理相机unverified是允许的，但不能冲销已作出的错误观察与不受证据支持的优先因果解释。

本独审没有重新解码视频。直接把已有无损PNG像素序列化为PPM，四个SHA逐一精确匹配live12的FrameRef及provider ledger，故这些像素是本轮实际源帧的字节等价图像证据，不是沿用旧结论。红框bbox四帧均为 `[322,156,445,301]`；y=20网格首竖线x为 `88.5→69→50→30.5`，每段约左移19像素，网格相对红框位置显著变化。眼见四帧图与整数测量一致。这里仅裁定图像坐标中可见结构变化；不要求断言真实相机右移，也不把图像注册当物理相机分类。

独立枚举128×77灰度图、±10共同窗的441个偏移，得到每段next-to-previous `(3,0)`、唯一最优、误差降低约72.5%/77.9%/74.0%；与ledger逐字段一致。3是**降采样图像中用于把下一帧对齐到上一帧的偏移**，不是原视频精确3像素，更不是物理主体/相机运动。模型只提3 pixels而未说明坐标语义，不能据此补成正确的主体/网格关系。模型的34%左右变化比例本次正确，但语义关系仍错误。

输入保留F源完整帧+D明确派生图，一次Provider单PNG重建hash与ledger相同；没有写入样本答案、没有把CPU复算篡为原始模型结果。raw/parsed关键字段严格对应。建议修复路线须解决可见相对位置观察及因果自洽问题，不能只增加offset/unknown词。

## 其他逐项事实

固定10项生产owner→oracle→证据见coverage.json的10条items（rows为同一固定集合）。3 attempted推理含取消，2 completed；3lease各有3个稳定空inventory/GPU恢复样本；峰GPU21217MiB、RAM最低10032MiB。原生PID27672/birth639298255854124545/nonce f7f76b0011ca4d92a735b14fbfc59c44一致并exited；原API PID/birth已消失，/proc监听表无18780/11434，原launcher日志有API退出和owned temp删除。headless browser closed、0页面错误/外部请求，native NO_CLOUD/loopback有原始日志。没有重启服务补证。

真实duration/corrupt负例均422；按RUNTIME01 scope，其他边界/排队准备取消使用候选gitblob的生产owner+受控外部原语CPU检查，**未声称这些都是模型调用或真实媒体解码**。CPU10项通过（其中exact/one-over输入、空上传/无排队/无provider/无文件、少帧不复制/重复PTS拒绝、排队取消/准备清理/晚到不发布/错误资源终态）。原public采纳导出关联已逐字段复核，取消不会覆盖既有人工稿/来源，模型停止仍能编辑并导出TXT/JSON。

所有frozen/sample/tool字节哈希通过。START_LVW.cmd工作树为CRLF，Git blob为LF：二者仅行尾不同、规范化完全相等，实际执行字节与授权hash精确匹配，已在脚本明确保留这项比较。SQLite使用mode=ro；live12账本3动作/1完整/56秒、active0；全局15/1024动作、5/24完整、1163/172800秒、0 active。56秒是终态SQLite/收据记录值，未把模型17秒或provider跨度当全部运行时长。

## 十字段状态

- 当前坐标：R1 / WP-R1-U3，live12隔离独审已完成。
- 本批完成：固定10项独审、10项CPU检查、原始哈希/源/工具/样本/全局账本复算。
- 最后通过门禁：本轮身份/原始链路/资源/清理检查；不授予产品Stage PASS。
- 当前阻塞门禁：UM-04时序语义 Major1。
- 全局路线位置：V1前置最小图视频统一切片；旧V0-S2人工前置仍依坐标保留。
- 剩余工作：纠正模型真实语义后按授权有限复验与新独审；通过后实际人工体验签署。
- 下一责任人：gate owner接收NO_GO并决定技术路线。
- 所需授权：本次只读独审无新增权限；COMPLETE03仍有效，不代人类签署。
- 证据目录：reports/unified-media/independent-live-12。
- 精确停止原因：独审已完成，UM04_FAIL_VISIBLE_RELATIVE_POSITION_DENIAL_AND_UNSUPPORTED_CAUSAL_INFERENCE。

## V0–V3完整开发大纲

以下只抄唯一execution-control.development_outline的完成计数，非主观工时，非本独审重新签署既有Stage。

| Stage | 子阶段 | 完成/总数 | 机器 / 独审 / 人签 |
|---|---|---|---|
{outline}
'''
(O/'review.md').write_text(text)
manifest={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.rglob('*')) if p.is_file() and p.name!='review-artifact-hashes.json'}
(O/'review-artifact-hashes.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'decision':'NO_GO','pass':9,'fail':1,'Fatal':0,'Major':1,'Minor':0,'cpu':result['cpu_results'].strip()},ensure_ascii=False))
