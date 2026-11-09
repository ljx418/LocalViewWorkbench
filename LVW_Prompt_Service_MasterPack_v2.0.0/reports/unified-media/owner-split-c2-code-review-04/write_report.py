from pathlib import Path
import json,hashlib
R=Path.cwd();O=R/'reports/unified-media/owner-split-c2-code-review-04';h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before=json.loads((O/'source-before.json').read_text());after={f:h(R/f) for f in before};(O/'source-after.json').write_text(json.dumps(after,indent=2)+'\n');x=json.loads((O/'independent-checks.json').read_text())
report='''# C2 harness 独立代码初审04

结论：**CHANGES_REQUIRED，仅代码就绪判断**。Fatal0 / Major1 / Minor2。指定8个C2源码/测试文件在本次审查前后SHA完全一致；未修改候选、测试、控制、旧证据或全局账本。53项CPU测试通过，但独立真实只读recipe加载反例发现DrvFS合法目录别名被误拒绝。未调用模型/GPU/服务/真实浏览器/网络/媒体探测或解码；未消耗完整验收额度。本报告不替代未来真实UM10、质量独审或人签，也不改变live14的7PASS/1FAIL/2BLOCKED。

## Major C2-M1：合法DrvFS工作区别名使冻结recipe在启动前失败

位置：acceptance_recipe.py:63。本次指定工作区为 `/mnt/c/workSpace/videoWorkLine/LocalViewWorkbench/LVW_Prompt_Service_MasterPack_v2.0.0`。从该真实目录执行 `load(Path.cwd(), approved())` 会在 `external.resolve()==expected.resolve()` 处抛AssertionError。recipe中的已批准外部根采用 `/mnt/c/workspace/videoworkline/.lvw-runtime/lvw-prompt-service/R1-unified-fixtures/real-rejection-fixtures-04`，从工作区推导的根采用 `/mnt/c/workSpace/videoWorkLine/...`。实际DrvfS上两者存在、非symlink、samefile=True，但Path.resolve保留大小写，字符串比较为False。

authority.ROOT来自实际导入文件路径，live_checkpoint在创建子授权/启动服务前无条件加载recipe，因此合法指定目录的普通运行会被阻断；不能将目前53项测试通过当成代码就绪。独立检查还证明同一文件系统的全小写工作区别名可以加载，确认不是缺文件、owner不匹配或资产损坏。应使用文件系统身份核验允许的同目录别名，同时保留词法穿越、父组件symlink和外部owner/hash约束，不应简单全面放宽路径边界。应加入实际大小写别名回归以及samefile不同目录拒绝回归。

证据：checks-initial-root-alias.stderr.log、independent-checks.json.actual_workspace_recipe_load；未为复现修改任何生产路径或建立新外部别名。

## Minor C2-m1：导航页可仅凭两个输出文件宣称取消释放序列已执行

位置：build_handoff.py:16–19。has_outputs只判断image-model-run.json和video-model-run.json存在，completion_note随即宣称“真实图片、视频、取消和释放序列已执行”。如果两个输出已产生、后续取消阶段尚未执行或失败，仍会生成该肯定陈述。独立CPU只求值这个纯表达式，以has_outputs=True且取消FAIL_OR_MISSING为输入，复现错误摘要；未执行会写生产HTML的renderer。行19还有无条件“真实媒体边界拒绝已有本轮执行记录”的陈述。

逐项表、原始NO_GO、独审链接及NOT_RUN仍保留，因此此处是诊断/摘要失真，不是机器通过门禁的漏洞。建议从逐项真实收据推导完成语句，或使用只陈述现有输出的中性文字。

## Minor C2-m2：非JSON失败响应的原始诊断丢失

位置：checkpoint_checks.py:46–48。先response.json()，再保存重序列化body。若公开上传返回非JSON错误页/损坏JSON，解析抛错时不会保存HTTP状态/原始响应体，只留下异常类型和说明。独立纯CPU输入500+HTML诊断，NV-CPU正确记录FAIL、整体NO_GO并抛错，但response文件不存在，原始诊断未保留。这不产生假PASS；仍应在解析前保存状态/原始text或bytes，让失败证据可复查。已有service/provider/launcher日志归档不受此问题影响。

## 已确认的就绪基础与边界

- 冻结R1packet1.0.4的manifest硬绑定为38ca0ae572cc74a412a411635e04f21bce3fdcd29d51456fde677f188dd9f307。recipe/control/批准内部amendment/公开合同/资产准备收据/owner标记均复算；在合法全小写别名下，9份样本的字节数和SHA全部一致。原4份前缀保留，正例仍是dev-image+原tracking.mov，未以protocol witness或新素材替换真实质量样本。外部资产为已声明保留输入，不是run临时目录。
- 新recipe要求active_program.global_only=True及complete03固定路径；actual approved()验证ACTIVE、project_owner、request绑定及前母授权哈希，complete03选中后撤销/损坏不会回退旧授权。authority中的旧分支仍是历史兼容代码，但本次live_checkpoint先加载新recipe，且create_program02再次验证，不会借旧live05授权复活。母授权累计账本继续使用，per-child仍8model/provider、1full、1800秒，API/Ollama/headless各1，下载/cloud/paid/holdout0；无增加额度代码。
- acceptance_recipe验证9份唯一路径、7真拒绝条目、精确错误/422、类别、原4前缀、3取消阶段、request receipt必需、holdout0、外部根owner/hash/bytecount；路径穿越和symlink拒绝保持。现有测试覆盖删项、重复、换tracking、错误状态/代码/类别、缺阶段/请求收据、holdout、越界/符号链接。M1正是未被这些结构测试覆盖的实际加载路径。
- negative_uploads通过公开media端点发送7个真实文件，启动模型前逐项检查稳定HTTP/错误码、无发布、无provider_call_started；media/video-temp树和API公开proc FD文件回到之前基线，最多等5秒。行状态先NOT_RUN，失败记录FAIL并抛错；只有全部完成才宣称矩阵PASS。此处CPU反假绿测试仅证明oracle拒绝能力，未假称已跑7个真实负例。
- browser保持生产React/default_app原路径；实际video仍上传原tracking.mov。运行中取消先观察真实running；另外用真实公开submit构造preparing持有者及其后queued，重新核对preparing仍存在后取消，不用fixture barrier或直接修改service状态。若窗口错过则失败，不得补成覆盖。各阶段要求cancel_epoch1、cancelled/released/result_ref=null及≤1秒反馈。preparing/queued通过公开API执行，running通过UI执行；不虚称全部三个阶段都由UI按钮触发。最终controller再与provider账本join，pre-inference取消不得有模型调用，人工稿/已采纳来源保持。真实调度竞争仍需C3实际运行验证；CPU/源码不能证明届时一定观察到所有阶段。
- browser捕获实际公开POST正文、Idempotency-Key和job_id；成功图/视频ModelRun按原始AnalyzeRequest归一化+video_num_ctx重新算config SHA，缺失、重复、变更正文、未知字段或旧digest拒绝。不是只查digest存在。取消任务无ModelRun，公开请求仍归档用于解释。
- 所有raw/modelrun/export、provider原始日志、native stdout/stderr/owner、negative/cancel/config逐项文件保留，异常默认NO_GO且browser非零退出使controller拒绝。UM04仍BLOCKED待独立内容审查，JSON/HTTP成功不自动通过。finally仍对已知公开/lease jobs取终态、停止原身份runtime、归档后结束自身API并检查listener/根清理；不清理外部保留输入，不回写旧失败轮次。代码审查不能代替这些真实清理证明。两个Minor为失败诊断保真/摘要问题，详见上述。

## 可复现验证

1. `PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest lvw/tests/test_acceptance_recipe.py lvw/tests/test_checkpoint_oracles.py tools/test_local_program_authority.py -q -p no:cacheprovider -o addopts= --basetemp=reports/unified-media/owner-split-c2-code-review-04/pytest-temp`：exit0，53passed/2.93s。只使用synthetic响应、隔离临时测试根/账本及源码检查；未触及真实全局账本。
2. `PYTHONDONTWRITEBYTECODE=1 python3 -B reports/unified-media/owner-split-c2-code-review-04/independent_checks.py`：最终exit0，保存真实只读加载反例、全小写别名正例、9样本hash/stat、两个Minor纯CPU反例和语法检查。脚本的exit0表示诊断成功完成，不表示被审代码PASS。最初辅助脚本缺sys.path导入exit1，保留checks-initial-import.stderr.log；修正仅该审查脚本后实际recipe加载exit1，保留checks-initial-root-alias.stderr.log；随后诊断显式捕获该已确认缺陷以完成其余检查。
3. `node --check reports/unified-media/live_browser.cjs`：exit0，不启动浏览器；7个Python文件AST解析通过，不执行live_checkpoint/build_handoff顶层运行逻辑。

源码围栏：source-before.json与source-after.json，8/8相同。全部CPU原始stdout/stderr、实际命令与退出码、独立复算和失败日志保留本目录。下一步仅修正C2-M1并补回归、处理两项Minor后重新独审；C1由另一独立实例审查，本报告不裁决C1。C3真实运行、固定10分母、原tracking原始回答质量、A12/Q01及人签均未完成、未豁免。
'''
(O/'review.md').write_text(report);commands=[{'command':['python3','-B','-m','pytest','lvw/tests/test_acceptance_recipe.py','lvw/tests/test_checkpoint_oracles.py','tools/test_local_program_authority.py','-q','-p','no:cacheprovider','-o','addopts=','--basetemp=reports/unified-media/owner-split-c2-code-review-04/pytest-temp'],'exit_code':0,'passed':53},{'command':['python3','-B','reports/unified-media/owner-split-c2-code-review-04/independent_checks.py'],'attempt':'initial_import','exit_code':1},{'command':['python3','-B','reports/unified-media/owner-split-c2-code-review-04/independent_checks.py'],'attempt':'actual_recipe_load_before_diagnostic_capture','exit_code':1},{'command':['python3','-B','reports/unified-media/owner-split-c2-code-review-04/independent_checks.py'],'attempt':'complete_diagnostic','exit_code':0},x['node_syntax_command']]
receipt={'kind':'INDEPENDENT_C2_CODE_READINESS_REVIEW_NOT_RUNTIME_PASS','decision':'CHANGES_REQUIRED','fatal':0,'major':1,'minor':2,'findings':[{'id':'C2-M1','severity':'Major','path':'reports/unified-media/acceptance_recipe.py:63','summary':'Legitimate assigned DrvFS alias fails real recipe loading despite samefile=True.'},{'id':'C2-m1','severity':'Minor','path':'reports/unified-media/build_handoff.py:18','summary':'Output existence overstates completed cancellation/release sequence.'},{'id':'C2-m2','severity':'Minor','path':'reports/unified-media/checkpoint_checks.py:46','summary':'Non-JSON failed response body/status lost before archival.'}],'packet_version':'1.0.4','packet_manifest_sha256':x['packet_manifest_sha256'],'source_before':before,'source_after':after,'source_unchanged':before==after,'commands':commands,'runtime_quality_verified':False,'stage_pass_claim':False,'human_signoff':None,'real_model_calls':0,'real_service_starts':0,'real_browser_starts':0,'new_media_probes_decodes':0,'global_ledger_writes':0,'output_hashes':{p.name:h(p) for p in O.iterdir() if p.is_file() and p.name!='receipt.json'}};(O/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'decision':receipt['decision'],'source_unchanged':receipt['source_unchanged'],'review_sha256':h(O/'review.md'),'receipt_sha256':h(O/'receipt.json')},indent=2))
