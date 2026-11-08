"""Build the offline human-review companion; never starts product services."""
import hashlib
import html
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'人工验收指南.html'
REPORT=ROOT/'reports/v0-s2/full-v0-auto-08'
control=json.loads((ROOT/'plans/execution-control.json').read_text())
receipt=json.loads((REPORT/'receipt.json').read_text())
review=json.loads((REPORT/'independent-review.json').read_text())
evidence=json.loads((REPORT/'human-review-evidence.json').read_text())
candidate=control['implementation_candidate']
assert candidate==receipt['candidate_sha']==review['candidate_sha']=='719c74559393a6489b2f630a1e0d3bc3303eb655'
ps=r'''$ErrorActionPreference = 'Stop'
$lvwPack = 'C:\workSpace\videoWorkLine\LocalViewWorkbench\LVW_Prompt_Service_MasterPack_v2.0.0'
$lvwPython = 'C:\ComfyUI-aki-v2\python\python.exe'
$lvwMain = 'C:\ComfyUI-aki-v2\ComfyUI\main.py'
$lvwFfmpeg = 'C:\ComfyUI-aki-v2\python\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe'
foreach ($lvwFile in @($lvwPython, $lvwMain, $lvwFfmpeg)) {
    if (!(Test-Path -LiteralPath $lvwFile -PathType Leaf)) { throw "Missing installed dependency: $lvwFile" }
}
$lvwSource = Join-Path $lvwPack 'LVW_V0_RuntimePatch\custom_nodes\lvw_v0_bridge'
if (!(Test-Path -LiteralPath $lvwSource -PathType Container)) { throw 'LVW source folder is missing.' }
if (Get-NetTCPConnection -State Listen -LocalPort 8191 -ErrorAction SilentlyContinue) {
    throw 'Port 8191 is occupied. Identify its owner; do not terminate an unknown process.'
}
$lvwSession = Join-Path $env:TEMP ('lvw-s2-experience-' + [guid]::NewGuid().ToString('N'))
foreach ($lvwDir in @('input','output','temp','user','custom_nodes\lvw_v0_bridge')) {
    New-Item -ItemType Directory -Path (Join-Path $lvwSession $lvwDir) | Out-Null
}
$lvwTarget = Join-Path $lvwSession 'custom_nodes\lvw_v0_bridge'
Get-ChildItem -LiteralPath $lvwSource -Recurse -File | Where-Object {
    $_.FullName -notlike '*\__pycache__\*' -and $_.Extension -ne '.pyc'
} | ForEach-Object {
    $lvwRelative = $_.FullName.Substring($lvwSource.Length + 1)
    $lvwDestination = Join-Path $lvwTarget $lvwRelative
    New-Item -ItemType Directory -Path (Split-Path $lvwDestination -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $lvwDestination
}
foreach ($lvwName in @('LVW_NATIVE_CHECKPOINT','LVW_WARM_BENCHMARK','LVW_FFPROBE_EXE','PYTHONPATH','PYTHONHOME','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY')) {
    Remove-Item ('Env:' + $lvwName) -ErrorAction SilentlyContinue
}
$env:LVW_FFMPEG_EXE = $lvwFfmpeg
$env:LVW_VIDEO_PROBE_BACKEND = 'pyav'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONNOUSERSITE = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_DATASETS_OFFLINE = '1'
$env:NO_PROXY = '127.0.0.1,localhost'
$lvwServiceTemp = Join-Path $lvwSession 'temp\service-os'
New-Item -ItemType Directory -Path $lvwServiceTemp | Out-Null
$env:TEMP = $lvwServiceTemp
$env:TMP = $lvwServiceTemp
$env:TORCH_HOME = Join-Path $lvwServiceTemp 'torch'
$env:HF_HOME = Join-Path $lvwServiceTemp 'huggingface'
$env:XDG_CACHE_HOME = Join-Path $lvwServiceTemp 'cache'
Write-Host "Temporary LVW session: $lvwSession"
Write-Host 'Open http://127.0.0.1:8191 manually. Keep this window open.'
& $lvwPython -s -B $lvwMain --listen 127.0.0.1 --port 8191 --base-directory $lvwSession --user-directory (Join-Path $lvwSession 'user') --disable-auto-launch --disable-api-nodes --disable-all-custom-nodes --whitelist-custom-nodes lvw_v0_bridge
Write-Host "After exporting your work and confirming this session stopped, remove only: $lvwSession"'''
checks=[
 {'id':'video_entry','title':'进入视频工作流','route':'视频 / 必要体验','action':'按“启动视频”打开临时 ComfyUI，导入 video_reverse_prompt_v0.ui.json。','expect':'看到 LVW Video 节点、上传控件、人工编辑区；没有“缺失节点”。','required':True},
 {'id':'video_analysis','title':'上传与反推','route':'视频 / 必要体验','action':'从 testSource 选一个不超过 60 秒的 MP4/MOV；上传完成后点击 ComfyUI“运行”。','expect':'能看到准备、分析、终态和采样帧；机器建议与原始响应可查看。最多四个采样帧，不代表连续观察整片。','required':True},
 {'id':'draft_protection','title':'分析不覆盖人工稿','route':'视频 / 必要体验','action':'分析前在“中文自然描述”写一段自己的文字，再运行分析。','expect':'分析结束后原文字仍在；机器建议没有自动写进人工稿。','required':True},
 {'id':'explicit_adopt','title':'显式采纳与继续编辑','route':'视频 / 必要体验','action':'点击“采纳当前机器建议”；有旧稿时再次确认替换，然后修改一段文字。','expect':'只有主动采纳才替换；之后可继续编辑。缺失语言如实为空，不伪装成已翻译。','required':True},
 {'id':'export','title':'复制与导出','route':'视频 / 必要体验','action':'复制人工稿 TXT，导出 TXT、JSON，再打开文件对照刚才修改的文字。','expect':'导出内容与人工稿一致，中文可读；不用再次调用模型。工作稿只在本页面会话中，离开前先导出。','required':True},
 {'id':'cancel','title':'取消后的体验','route':'视频 / 必要体验','action':'保留人工稿，发起一次新的分析，在准备或分析期间点击“取消本次视频分析”。','expect':'有明确取消反馈；晚到结果不覆盖旧稿，仍可编辑与导出。若任务已完成，记录“暂不可测”，不要假称测试了取消。','required':True},
 {'id':'offline','title':'模型不可用时保留人工能力','route':'视频 / 必要体验','action':'只停止你自己通过图片工作台启动的 Ollama，保持 ComfyUI 开着；继续编辑并导出视频节点的人工稿。','expect':'模型不可用时人工编辑/导出仍可用。不要关闭 ComfyUI，也不要结束不明进程；外部模型服务不能由页面强制关闭。','required':True},
 {'id':'image','title':'图片工作台复体验','route':'图片 / 可选复体验，R1a 已签','action':'在图片工作台上传 JPEG/PNG/WebP，点击“分析图片”，查看建议后“采纳到人工稿”，编辑并导出。','expect':'能完成单图反推与人工编辑。该入口目前不支持视频；不会将它算作 S2 视频体验。','required':False},
 {'id':'preferences','title':'自定义分析偏好','route':'图片 / 可选复体验','action':'选择表达方式、内容处理预设，填写附加分析要求后分析一张适合的非私有图片。','expect':'预设与要求可填写，结果仍区分观察/推断/未知；模型拒答时明确报错，不覆盖人工稿，也不承诺任何内容一定成功。','required':False}
]
data={'schema':'lvw.manual-review-guide/1','candidate':candidate,'stage':'V0-S2','generated_on':'2026-11-08','machine_run':'full-v0-auto-08','machine_cases':receipt['cases'],'review':review['findings'],'checks':checks,'signature':f'批准 V0-S2 人工体验签署，候选 {candidate}；确认当前 ComfyUI 最简短视频、显式采纳、取消与离线人工工作流满足本阶段目标，并接受验收材料列明的范围及非阻断限制。该签署不批准 V0.2、完整 V1 或生产发布。'}
assert len(data['machine_cases'])==9 and all(v=='PASS' for v in data['machine_cases'].values())
e=lambda x:html.escape(str(x),quote=True)
check_html=''
for i,c in enumerate(checks):
 check_html+=f'''<article class="check" id="check-{c['id']}"><div class="check-head"><span class="step-number">{i+1:02d}</span><div><small>{e(c['route'])}</small><h3>{e(c['title'])}</h3></div></div><p><strong>操作：</strong>{e(c['action'])}</p><p class="expected"><strong>应看到：</strong>{e(c['expect'])}</p><div class="record-row"><label>我的体验<select data-result="{c['id']}" aria-label="{e(c['title'])}体验结果"><option value="NOT_TRIED">未体验</option><option value="PASS">体验通过</option><option value="ISSUE">发现问题</option><option value="UNAVAILABLE">暂不可测</option></select></label><label class="note-label">备注<textarea rows="2" maxlength="4000" data-note="{c['id']}" aria-label="{e(c['title'])}备注" placeholder="记录实际现象或错误码，不必重做机器回归。"></textarea></label></div></article>'''
outline=''.join(f'<tr><td>{e(s["delivery"])}</td><td>{e(s["stage_id"])}</td><td>{s["completed_substeps"]}/{s["total_substeps"]}</td><td>{e(s["title"])}</td></tr>' for s in control['development_outline'])
source_report='reports/v0-s2/full-v0-auto-08/'
PAGE=r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>LVW 人工验收指南</title>
<style>
:root{--paper:#f3f6fa;--ink:#19334c;--muted:#54677b;--line:#d4dfe9;--blue:#285dc0;--navy:#173c64;--teal:#167762;--amber:#87571b;--white:#fff;--red:#a13434}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:26px}body{margin:0;color:var(--ink);background:var(--paper);font:15px/1.75 "Microsoft YaHei UI","PingFang SC",system-ui,sans-serif}button,input,select,textarea{font:inherit}button,a,select,input,textarea{outline-offset:4px}a{color:var(--blue);text-underline-offset:4px}a:hover{color:var(--navy)}button{cursor:pointer}button:disabled{cursor:not-allowed;opacity:.52}:focus-visible{outline:3px solid #df9b31}header{height:74px;display:flex;align-items:center;justify-content:space-between;background:var(--white);border-bottom:1px solid var(--line);padding:0 36px;gap:18px}.brand{display:flex;align-items:center;gap:12px;color:var(--navy)}.brand svg{width:34px;height:34px}.brand strong{font:700 23px Bahnschrift,"Microsoft YaHei UI",sans-serif}.brand span{padding-left:12px;border-left:1px solid var(--line);font-size:14px}.badge{font-size:13px;color:var(--amber);background:#fff3dd;padding:5px 12px;border-radius:4px}.layout{display:grid;grid-template-columns:226px minmax(0,1050px);gap:42px;max-width:1370px;margin:0 auto;padding:30px 32px 60px}aside{position:sticky;top:24px;align-self:start;min-width:0}aside p{margin:0 0 14px;color:var(--muted);font-size:13px}nav a{display:flex;gap:13px;text-decoration:none;color:var(--ink);padding:10px 6px;border-left:3px solid transparent}nav a:hover,nav a:focus{background:#e7eef8;border-left-color:var(--blue)}nav a span{font:500 14px Bahnschrift,sans-serif;color:var(--muted);min-width:22px}.review-progress{border-top:1px solid var(--line);margin-top:24px;padding-top:18px}.progress-track{height:7px;background:#dae3ee;overflow:hidden;border-radius:4px}.progress-track i{display:block;width:0;height:100%;background:var(--teal);transition:width .15s}.review-progress b{font-size:20px;font-family:Bahnschrift,sans-serif}.sidebar-foot{margin-top:18px;font-size:12px;color:var(--muted)}main{min-width:0}h1{font-size:clamp(26px,3.1vw,40px);line-height:1.35;letter-spacing:-.02em;margin:0 0 18px;max-width:22ch}h2{font-size:24px;line-height:1.4;margin:0 0 18px}h3{font-size:17px;line-height:1.45;margin:0 0 8px}h4{font-size:15px;margin:20px 0 7px}p{max-width:78ch;margin:9px 0 15px}.intro{padding:30px 34px;background:var(--navy);color:white;border-radius:6px;position:relative}.intro p{color:#d8e6f5;max-width:66ch}.flow{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:24px;font-size:14px}.flow span{padding:7px 11px;border:1px solid #7290ae;border-radius:3px}.flow b{font-weight:400;color:#c0d6eb}.state-strip{display:flex;flex-wrap:wrap;gap:12px 24px;padding:15px 0;border-bottom:1px solid var(--line);font-size:13px}.state-strip strong{color:var(--teal)}section{margin-top:42px}.notice{padding:15px 18px;background:#e8eff8;border-left:4px solid var(--blue);margin:18px 0}.notice.warning{background:#fff3dd;border-left-color:#bb812b}.notice.success{background:#e7f3ee;border-left-color:var(--teal)}.split{display:grid;grid-template-columns:1fr 1fr;gap:24px}.route{background:white;border:1px solid var(--line);padding:23px}.route p{font-size:14px;color:var(--muted)}.route-label{color:var(--teal);font-weight:600;font-size:13px}.path{display:block;padding:12px 14px;background:#eaf0f7;overflow-wrap:anywhere;font:13px/1.7 Consolas,monospace;margin:10px 0}.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:15px 0}.button,button{border:1px solid #bdcddd;border-radius:4px;padding:9px 15px;background:white;color:var(--ink);font-weight:600;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:7px}.button:hover,button:hover{background:#edf3fa}.primary{background:var(--blue);color:white;border-color:var(--blue)}.primary:hover{background:#204ca1;color:white}.small{font-size:13px;padding:6px 10px}.quiet{background:transparent}label{display:block;font-size:14px}input,select,textarea{color:var(--ink);border:1px solid #b9c9d8;background:white;border-radius:4px;padding:9px 10px;max-width:100%}textarea{width:100%;resize:vertical}input[type="checkbox"]{width:17px;height:17px;vertical-align:middle;accent-color:var(--blue)}.checkbox-label{display:flex;align-items:flex-start;gap:9px;margin:12px 0}ol{padding-left:24px}li{margin:8px 0}.codebox{background:#e9eff6;border:1px solid var(--line);border-radius:4px;padding:16px;max-height:360px;overflow:auto;font:12px/1.7 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}.check{padding:23px 0;border-bottom:1px solid var(--line)}.check:first-child{padding-top:0}.check-head{display:flex;align-items:center;gap:14px;margin-bottom:12px}.step-number{align-self:flex-start;font:600 29px/1.1 Bahnschrift,sans-serif;color:#6385a8}.check small{color:var(--muted);font-size:12px}.check h3{margin:0}.check p{font-size:14px}.expected{padding:10px 14px;background:#eaf0f7}.record-row{display:grid;grid-template-columns:155px 1fr;gap:16px}.record-row select{display:block;width:100%;margin-top:5px}.record-row textarea{display:block;margin-top:5px}.check[data-state="ISSUE"]{border-left:4px solid var(--red);padding-left:16px}.check[data-state="PASS"] .step-number{color:var(--teal)}.check[data-state="UNAVAILABLE"] .step-number{color:var(--amber)}details{border-bottom:1px solid var(--line);padding:12px 0}summary{cursor:pointer;font-weight:600}details p,details li{font-size:14px}table{border-collapse:collapse;width:100%;background:white;font-size:14px}th,td{text-align:left;padding:11px 12px;border-bottom:1px solid var(--line)}th{background:#e7eef6;font-weight:600}.table-wrap{overflow:auto}.metrics{display:flex;flex-wrap:wrap;gap:22px;padding:18px 0}.metrics div{border-left:2px solid #91b4b2;padding-left:14px}.metrics b{font:600 25px Bahnschrift,sans-serif;display:block}.metrics small{display:block;color:var(--muted)}.decision-panel{padding:23px;background:white;border:1px solid #bccdde}.grid-form{display:grid;grid-template-columns:1fr 1fr;gap:18px}.grid-form input{display:block;width:100%;margin-top:5px}.proposal{white-space:pre-wrap;overflow-wrap:anywhere;padding:17px;background:#eaf0f7;font-size:14px}.status-line{font-size:13px;color:var(--muted);min-height:25px}.status-line[data-kind="error"]{color:var(--red)}.signature-state{font-weight:600;color:var(--amber)}.fallback{margin-top:12px}.fallback textarea{font-size:13px}.caption{font-size:12px;color:var(--muted)}footer{margin-top:38px;padding-top:16px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}.skip{position:absolute;left:10px;top:-80px;z-index:20;background:white;padding:10px}.skip:focus{top:8px}
@media(max-width:920px){.layout{grid-template-columns:minmax(0,1fr);gap:20px;padding:24px 18px}aside{position:static}nav{display:flex;overflow:auto;gap:7px}nav a{white-space:nowrap;border-left:0;border-bottom:2px solid var(--line);padding:8px 10px}aside>p,.sidebar-foot{display:none}.review-progress{margin-top:14px;padding-top:12px}.review-progress p{display:block}header{padding:0 18px}.brand span{display:none}.split{grid-template-columns:1fr}.intro{padding:26px 22px}section{margin-top:32px}}@media(max-width:520px){.record-row,.grid-form{grid-template-columns:1fr}.badge{font-size:11px}.intro h1{font-size:27px}.actions>*{max-width:100%}th,td{padding:9px}.brand strong{font-size:21px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.progress-track i{transition:none}}@media print{header,aside,button,.actions,.import-row{display:none}.layout{display:block;padding:0}.intro{background:white;color:black;padding:10px 0}.intro p{color:black}details{display:block}.check{break-inside:avoid}.codebox{max-height:none}body{background:white}}
</style></head><body><a class="skip" href="#main">跳到验收内容</a><header><div class="brand"><svg viewBox="0 0 40 40" aria-hidden="true" fill="none"><path d="M6 8h28v24H6z" stroke="currentColor" stroke-width="2"/><path d="m12 24 6-10 5 7 4-3 5 8H12Z" fill="currentColor"/><circle cx="28" cy="13" r="2" fill="currentColor"/></svg><strong>LocalView</strong><span>人工验收指南</span></div><span class="badge">S2 待人工签署 · 7/8</span></header>
<div class="layout"><aside><p>按顺序体验，随手记录</p><nav aria-label="验收导航"><a href="#start"><span>01</span>选对体验入口</a><a href="#image-start"><span>02</span>启动图片工作台</a><a href="#video-start"><span>03</span>启动视频工作流</a><a href="#experience"><span>04</span>逐项体验</a><a href="#machine"><span>05</span>已完成的机器证据</a><a href="#record"><span>06</span>导出记录与签署</a><a href="#roadmap"><span>07</span>完整开发路线</a></nav><div class="review-progress"><p>必要体验项的记录进度</p><b id="progress-text">0 / 7</b><div class="progress-track" role="progressbar" aria-label="人工体验记录进度" aria-valuemin="0" aria-valuemax="7" aria-valuenow="0"><i id="progress-fill"></i></div><p id="issues-count">尚未体验</p></div><div class="sidebar-foot">记录仅保存在当前浏览器。<br>正式签署仍需在对话中确认。</div></aside><main id="main">
<div class="intro"><h1>亲自走一遍，<br>从媒体到你的提示词。</h1><p>先启动产品，再按下面的清单体验。你负责判断是否顺手、结果是否满足阶段目标；固定分母回归、安全、性能与清理已经由机器和独立审查完成。</p><div class="flow" aria-label="产品体验路径"><span>选择图片 / 短视频</span><b>›</b><span>本地分析</span><b>›</b><span>显式采纳</span><b>›</b><span>编辑与导出</span></div></div>
<div class="state-strip"><span><strong>机器 9/9 已通过</strong>（2026-11-06）</span><span><strong>独审阻断项 0</strong></span><span>当前服务状态：未检测</span><span class="signature-state">人工签署：尚未提交</span></div>
<section id="start"><h2>先分清两个入口</h2><div class="split"><article class="route"><span class="route-label">图片体验 · 已签 R1a</span><h3>独立图片工作台</h3><p>双击 START_LVW.cmd。可以上传单图、设置分析偏好、采纳和编辑、导出，并管理本轮 Ollama 服务。这个入口当前不支持视频。</p><a href="#image-start" class="button primary">按图片步骤开始</a></article><article class="route"><span class="route-label">视频体验 · 本次 S2</span><h3>ComfyUI 原生视频工作流</h3><p>使用临时隔离的 ComfyUI 运行 LVW 视频节点。支持四帧观察、机器建议、显式采纳、人工编辑、取消和模型离线导出。</p><a href="#video-start" class="button">按视频步骤开始</a></article></div><div class="notice">这是一份验收引导与记录页，不是新的产品前端。打开本页不会启动服务、调用模型或读取媒体。看过历史截图不代表已经亲自体验。</div><p class="caption">建议准备一张非私有图片和一个短片，按正常使用走一遍即可。无需你重做全部安全边界、20 次性能测试或进程清理回归。</p></section>
<section id="image-start"><h2>启动图片工作台</h2><ol><li>在 Windows 资源管理器打开项目目录，双击 <strong>START_LVW.cmd</strong>，保留启动窗口。</li><li>浏览器通常自动打开 <strong>http://127.0.0.1:18765</strong>。若端口占用，启动器会选择 18766–18775；以窗口显示地址为准。</li><li>查看页面顶部“本地后端服务”。如 Ollama 未运行，点击 <strong>启动模型服务</strong>；确认本机有 <strong>gemma4:26b</strong>。不要通过此页下载模型。</li><li>上传 JPEG / PNG / WebP（≤20 MiB、4000 万像素），点击“分析图片”，查看机器建议，点击“采纳到人工稿”，编辑后导出 TXT / JSON。</li></ol><code class="path" id="launcher-path">C:\workSpace\videoWorkLine\LocalViewWorkbench\LVW_Prompt_Service_MasterPack_v2.0.0\START_LVW.cmd</code><div class="actions"><button data-copy="launcher-path">复制启动器路径</button><label>实际端口 <select id="port" aria-label="图片工作台端口">__PORTS__</select></label><a id="image-link" class="button primary" href="http://127.0.0.1:18765" target="_blank" rel="noopener noreferrer">打开图片工作台</a></div><p class="caption">点击“打开”只打开地址，不能替代双击启动。若浏览器无法连接，先看启动窗口，不要把本页当成服务已就绪的证明。</p><details><summary>遇到 MODEL_UNAVAILABLE、404 或无法连接</summary><ul><li>MODEL_UNAVAILABLE：先看服务面板的 Ollama、模型可用性与装载状态。模型未安装或已迁移时，记录问题；本次不会自动下载权重。</li><li>runtime/status 404 或提示旧后端：确认使用本目录 START_LVW.cmd，并使用它本次显示的端口。不要连接到旧服务窗口。</li><li>“重置 / 关闭”只对本轮工作台启动的 Ollama 生效；外部服务不允许由页面强制终止。</li><li>模型拒答会显示错误；模型自身仍可能拒绝特定输入，不把失败说成成功。人工稿应保留。</li></ul></details></section>
<section id="video-start"><h2>启动本次视频工作流</h2><p>本机安装位置是 <code>C:\ComfyUI-aki-v2</code>。2026-11-08 只读核对时，常驻 custom_nodes 中没有 lvw_v0_bridge。直接打开普通 ComfyUI 再拖入工作流，可能会提示缺失节点。</p><ol><li>先按上一节启动图片工作台，从服务面板启动本轮 Ollama，供视频流程复用。图片分析是可选的。</li><li>新开一个 <strong>Windows PowerShell</strong> 窗口，复制下面的命令并粘贴执行。它只把现有扩展源码复制到新的临时目录，使用已有 Python / FFmpeg / PyAV，不覆盖常驻 ComfyUI。</li><li>看到服务启动地址后，手动打开 <strong>http://127.0.0.1:8191</strong>。保持此 PowerShell 窗口开着。</li><li>把项目内 <strong>video_reverse_prompt_v0.ui.json</strong> 拖进 ComfyUI 或用“打开”导入。使用下方路径找到文件；浏览器可能只显示 JSON，需在 ComfyUI 中导入。</li><li>在 LVW 视频节点中选择并上传 MP4/MOV，等“视频已上传”后点击 ComfyUI <strong>运行</strong>。模型使用 gemma4:26b。</li></ol><details><summary>展开临时视频启动命令</summary><p>请在单独的新窗口运行；环境变量只作用于该窗口。命令不是下载器，也不修改执行策略。8191 占用时会停止提示，不会结束占用进程。</p><div class="actions"><button data-copy="video-command">复制完整启动命令</button></div><pre class="codebox" id="video-command">__PS__</pre></details><code class="path" id="workflow-path">C:\workSpace\videoWorkLine\LocalViewWorkbench\LVW_Prompt_Service_MasterPack_v2.0.0\LVW_V0_RuntimePatch\workflows\video_reverse_prompt_v0.ui.json</code><div class="actions"><button data-copy="workflow-path">复制工作流路径</button><a class="button" href="http://127.0.0.1:8191" target="_blank" rel="noopener noreferrer">打开视频工作流地址</a><a href="LVW_V0_RuntimePatch/workflows/video_reverse_prompt_v0.ui.json">查看工作流 JSON</a></div><div class="notice warning"><strong>本次只观察有限采样帧。</strong>视频输入为 MP4/MOV，≤256 MiB、≤60 秒，源单帧≤8294400像素；默认观察四个不同时间点。极短片可少帧并提示，不能据此推断未采样片段。当前不开放八帧模式。</div><details><summary>结束体验与清理</summary><ol><li>先导出人工稿，本页也导出一份验收记录。</li><li>在图片工作台只关闭由它本轮启动的 Ollama；若标为外部服务，不结束不明进程。</li><li>在视频 PowerShell 窗口按 Ctrl+C，确认本轮 ComfyUI 结束。然后在图片启动窗口按 Ctrl+C。</li><li>记录视频窗口打印的 Temporary LVW session 路径。确认该会话停止且已导出后，只删除这个 lvw-s2-experience- 开头的临时目录；不删除既有 ComfyUI 或模型目录。</li></ol></details><p class="caption">以上是给你手动运行的隔离体验步骤，不是重新执行过的正式验收运行；本页不声称当前服务已启动。完整安装、迁移和回滚包仍属于 S3。</p></section>
<section id="experience"><h2>边体验，边记录</h2><p>每一项由你选择实际体验结果。机器已通过的项目不会自动帮你勾选。暂不可测与未体验都不会计作“体验通过”。</p>__CHECKS__</section>
<section id="machine"><h2>机器已经替你完成了什么</h2><p>以下是 full-v0-auto-08 的历史证据快照，绑定候选 <code>719c745</code>。它不表示今天模型已装载，也不代替你的体验判断。</p><div class="metrics"><div><b>541</b><small>CPU 回归通过</small></div><div><b>9 / 9</b><small>累计固定用例通过</small></div><div><b>20 / 20</b><small>热性能样本通过</small></div><div><b>0</b><small>独审 Fatal / Major / Minor</small></div></div><div class="table-wrap"><table><thead><tr><th>检查</th><th>结果</th><th>冻结门限 / 范围</th></tr></thead><tbody><tr><td>图片热 P95</td><td>9.422 秒</td><td>≤180 秒，10 次</td></tr><tr><td>四帧视频热 P95</td><td>24.500 秒</td><td>≤300 秒，10 次</td></tr><tr><td>热测 GPU 峰值</td><td>21470 MiB</td><td>&lt;23552 MiB</td></tr><tr><td>最低可用 RAM</td><td>7443 MiB</td><td>≥2048 MiB；OOM=0</td></tr><tr><td>取消、失败与清理</td><td>真实运行及独审闭合</td><td>取消反馈≤1秒，释放≤30秒；只处理本轮资源</td></tr><tr><td>完整依赖封存</td><td>5 次 / 每次97078文件</td><td>每次15810055916字节；候选与实际工具绑定</td></tr></tbody></table></div><details><summary>九项固定义务与详细证据</summary><p>A01 图片、A02 视频抽帧、A03 四输出复用、A04 人工编辑导出、A05 异常不覆盖、A07 文件安全、A08 离线人工、A09 资源性能、A10 取消卸载均已通过。它们是机器固定九项；上面的人工体验清单不会改写该分母。</p><ul><li><a href="reports/v0-s2/full-v0-auto-08/receipt.json">完整机器终态收据</a></li><li><a href="reports/v0-s2/full-v0-auto-08/independent-review.md">独立审查与覆盖边界</a></li><li><a href="reports/v0-s2/full-v0-auto-08/human-review.html">实际输出、取消及离线导出的原始材料页</a></li><li><a href="reports/v0-s2/full-v0-auto-08/native-workbench.png">故障注入后原始截图（红色错误提示为预期故障）</a></li></ul><p>独审核验既有真实 FFmpeg 结构/时间线、来源与帧 hash 关联；没有冒充新一轮像素解码，也未做第六次全树重哈希。</p></details><details><summary>全项目如何验收，哪些地方需要人类</summary><ol><li>冻结范围、合同、所有权、固定分母与预算。</li><li>同 Stage 内连续完成 Workpack，并保存定向测试与收据。</li><li>Stage 集中离线验收，再执行新鲜、隔离的真实固定矩阵和清理。</li><li>隔离独立审查重算真实证据；Fatal/Major必须为0。</li><li>人类确认体验、阶段范围和取舍，明确签署候选。</li><li>保存签署、立即提交并推送 Git，然后进入下一 Stage。版本发布另行签署。</li></ol><p>已签：V0-Min 与 R1a 单图切片。当前待签：S2 最简视频与资源控制。后续 S3 另需离线迁移/增量包及独立质量集验收；V1、V2、V3 各有对应的累计独审与人工签署，不能用本次签署替代。</p></details><div class="notice warning"><strong>本阶段的接受边界：</strong>结构样本不代表完整内容质量。历史结构样本中文结果为空、图像与视频 Prompt 相同均如实保留；不能称作已完成翻译。S3 的独立 10 图/6 片质量集、增量安装、断网迁移与回滚尚未完成。若真实使用不满足你的阶段目标，请记录问题。</div></section>
<section id="record"><h2>保存体验记录，再决定是否签署</h2><div class="decision-panel"><div class="grid-form"><label>体验人（可选）<input id="reviewer" maxlength="80" autocomplete="off" placeholder="你的名字或代号"></label><label>使用的样本说明（可选）<input id="samples" maxlength="300" autocomplete="off" placeholder="仅写样本名称，不必提供媒体或私有路径"></label></div><label style="margin-top:15px">整体意见<textarea id="overall" maxlength="4000" rows="3" placeholder="哪些地方顺手？哪些结果或错误影响了你的使用？"></textarea></label><label class="checkbox-label"><input type="checkbox" id="scope-ack"><span>我已阅读阶段范围与未完成项，理解本次仅为 S2，不批准 V0.2、完整 V1 或生产发布。</span></label><p id="readiness" class="signature-state">尚有必要体验项未记录。</p><div class="actions"><button id="export" class="primary">导出体验记录 JSON</button><button id="export-text">导出问题记录 TXT</button><button id="copy-signature" disabled>复制拟签署文本</button></div><details><summary>查看候选绑定的拟签署文本</summary><p>清单只是辅助工具，不新增或降低正式门限。勾选或复制不会写入项目状态。最终仍需你把确认文本发回对话；有问题时请先导出记录。</p><div class="proposal" id="signature-text">__SIGNATURE__</div></details><p class="caption">导出记录始终标记“人工签署尚未提交”，不会把浏览器本地记录当成正式审批。人工签署后由 Codex 立即保存签署并推送 Git。</p><div class="actions import-row"><label class="button small">导入此前的体验记录<input id="import-file" type="file" accept="application/json,.json" hidden></label><button id="reset" class="small quiet">清空本页记录</button></div><p id="storage-status" class="status-line" role="status">正在检查本地记录存储…</p><p id="action-status" class="status-line" role="status" aria-live="polite"></p><div id="copy-fallback" class="fallback" hidden><label>复制未成功，请手动选择下方文字并复制<textarea id="fallback-text" readonly rows="5"></textarea></label></div><noscript>浏览器未启用 JavaScript，仍可阅读步骤；请把体验结果另存文本。本页不会自动签署。</noscript></div></section>
<section id="roadmap"><h2>完整开发路线</h2><p>完成数是子阶段数量，不是工时百分比。S0 历史 NO_GO 保留；R0 仅确认前置子集。</p><div class="table-wrap"><table><thead><tr><th>交付</th><th>Stage</th><th>已完成 / 总数</th><th>内容</th></tr></thead><tbody>__OUTLINE__</tbody></table></div></section><footer>资料更新：2026-11-08。正式候选 <code>__CANDIDATE__</code>。<br>本页仅保存验收笔记，无云服务、无模型请求、无后端控制。<a href="docs/26_MANUAL_ACCEPTANCE_GUIDE.md">文字版体验说明</a> · <a href="docs/24_EXECUTION_MASTER_PLAN.md">开发执行总纲</a></footer>
</main></div><script type="application/json" id="guide-data">__DATA__</script>
<script>
'use strict';
const GUIDE=JSON.parse(document.getElementById('guide-data').textContent);
const KEY='lvw.manual-review.v1.'+GUIDE.candidate;
const validResults=new Set(['NOT_TRIED','PASS','ISSUE','UNAVAILABLE']);
const byId=id=>document.getElementById(id);
const required=GUIDE.checks.filter(c=>c.required);
let storageOK=true;
function blank(){return {schema:GUIDE.schema,candidate:GUIDE.candidate,stage:GUIDE.stage,reviewer:'',samples:'',overall:'',scope_ack:false,checks:Object.fromEntries(GUIDE.checks.map(c=>[c.id,{result:'NOT_TRIED',note:''}]))};}
let state=blank();
function message(text,error=false){byId('action-status').textContent=text;byId('action-status').dataset.kind=error?'error':'info';}
function validate(value){
 if(!value||value.schema!==GUIDE.schema||value.candidate!==GUIDE.candidate||value.stage!==GUIDE.stage)throw new Error('记录版本或候选不匹配；不能沿用其他候选的体验结果。');
 if(!value.checks||typeof value.checks!=='object'||Array.isArray(value.checks)||Object.keys(value.checks).length!==GUIDE.checks.length)throw new Error('体验项集合不完整。');
 const clean=blank();
 for(const [key,max] of [['reviewer',80],['samples',300],['overall',4000]]){if(typeof value[key]!=='string'||value[key].length>max)throw new Error('记录文字格式或长度不正确。');clean[key]=value[key];}
 if(typeof value.scope_ack!=='boolean')throw new Error('范围确认格式不正确。');clean.scope_ack=value.scope_ack;
 for(const c of GUIDE.checks){const v=value.checks[c.id];if(!v||!validResults.has(v.result)||typeof v.note!=='string'||v.note.length>4000)throw new Error('体验结果格式不正确。');clean.checks[c.id]={result:v.result,note:v.note};}
 return clean;
}
function update(){
 const done=required.filter(c=>state.checks[c.id].result==='PASS').length;
 const issues=GUIDE.checks.filter(c=>state.checks[c.id].result==='ISSUE').length;
 const unavailable=required.filter(c=>state.checks[c.id].result==='UNAVAILABLE').length;
 byId('progress-text').textContent=done+' / '+required.length;
 byId('progress-fill').style.width=(100*done/required.length)+'%';
 document.querySelector('[role="progressbar"]').setAttribute('aria-valuenow',String(done));
 byId('issues-count').textContent=issues?issues+' 项发现问题':unavailable?unavailable+' 项暂不可测':done===0?'尚未体验':'已记录 '+done+' 项体验通过';
 for(const c of GUIDE.checks)byId('check-'+c.id).dataset.state=state.checks[c.id].result;
 const ready=done===required.length&&issues===0&&state.scope_ack;
 byId('copy-signature').disabled=!ready;
 byId('readiness').textContent=issues?'已记录问题，请导出后交回修复。':done!==required.length?'尚有必要体验项未通过或暂不可测。':!state.scope_ack?'请先确认本阶段范围与未完成项。':'体验记录已齐，可复制拟签署文本；正式签署尚未提交。';
}
function save(){
 try{localStorage.setItem(KEY,JSON.stringify(state));storageOK=true;byId('storage-status').textContent='已在当前浏览器本地保存；建议导出一份记录。';}
 catch(_){storageOK=false;byId('storage-status').textContent='浏览器不允许本地保存，当前输入仍在本页；关闭前请导出记录。';}
 update();
}
function fill(){
 for(const c of GUIDE.checks){document.querySelector('[data-result="'+c.id+'"]').value=state.checks[c.id].result;document.querySelector('[data-note="'+c.id+'"]').value=state.checks[c.id].note;}
 for(const k of ['reviewer','samples','overall'])byId(k).value=state[k];byId('scope-ack').checked=state.scope_ack;update();
}
try{const raw=localStorage.getItem(KEY);if(raw){state=validate(JSON.parse(raw));byId('storage-status').textContent='已恢复当前候选的本地体验记录。';}else byId('storage-status').textContent='尚无本地记录；填写后会自动保存在当前浏览器。';}
catch(_){storageOK=false;byId('storage-status').textContent='本地存储不可用或已有记录损坏；未将旧记录计为通过。请导出本次记录备份。';}
fill();
for(const c of GUIDE.checks){document.querySelector('[data-result="'+c.id+'"]').addEventListener('change',event=>{state.checks[c.id].result=event.target.value;save();});document.querySelector('[data-note="'+c.id+'"]').addEventListener('input',event=>{state.checks[c.id].note=event.target.value;save();});}
for(const k of ['reviewer','samples','overall'])byId(k).addEventListener('input',event=>{state[k]=event.target.value;save();});
byId('scope-ack').addEventListener('change',event=>{state.scope_ack=event.target.checked;save();});
function record(){return {...state,exported_at:new Date().toISOString(),record_kind:'HUMAN_EXPERIENCE_NOTES_ONLY',human_signoff_submitted:false,stage_pass_claim:false,machine_evidence:{run_id:GUIDE.machine_run,source:'reports/v0-s2/full-v0-auto-08/receipt.json'},proposed_signature:byId('copy-signature').disabled?null:GUIDE.signature};}
function download(name,contents,type){const url=URL.createObjectURL(new Blob([contents],{type}));const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);message('已发起下载；请确认浏览器已保存文件。正式人工签署尚未提交。');}
byId('export').addEventListener('click',()=>{try{download('LVW-S2-人工体验记录.json',JSON.stringify(record(),null,2)+'\n','application/json;charset=utf-8');}catch(_){message('无法发起下载，请保留页面并手动复制记录。',true);showFallback(JSON.stringify(record(),null,2));}});
byId('export-text').addEventListener('click',()=>{const lines=['LVW S2 人工体验记录（非正式签署）','候选：'+GUIDE.candidate,'体验人：'+state.reviewer,'样本：'+state.samples,'整体意见：'+state.overall,''];for(const c of GUIDE.checks)lines.push(c.title+'：'+state.checks[c.id].result,state.checks[c.id].note,'');try{download('LVW-S2-问题记录.txt',lines.join('\n'),'text/plain;charset=utf-8');}catch(_){showFallback(lines.join('\n'));message('无法发起下载，请手动复制文字。',true);}});
function showFallback(text){byId('copy-fallback').hidden=false;byId('fallback-text').value=text;byId('fallback-text').focus();byId('fallback-text').select();}
async function copy(text){try{await navigator.clipboard.writeText(text);byId('copy-fallback').hidden=true;message('已复制。复制拟签署文本不会自动提交签署。');}catch(_){showFallback(text);message('浏览器未允许复制；文字已选中，请手动复制。',true);}}
for(const button of document.querySelectorAll('[data-copy]'))button.addEventListener('click',()=>copy(byId(button.dataset.copy).textContent));
byId('copy-signature').addEventListener('click',()=>{if(!byId('copy-signature').disabled)copy(GUIDE.signature);});
byId('port').addEventListener('change',event=>{const port=Number(event.target.value);if(Number.isInteger(port)&&port>=18765&&port<=18775)byId('image-link').href='http://127.0.0.1:'+port;});
byId('import-file').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>256*1024)throw new Error('记录文件超过256 KiB。');const clean=validate(JSON.parse(await file.text()));if(!window.confirm('导入将替换本页记录；未导出的内容请先保存。'))return;state=clean;fill();save();message('已导入匹配本候选的体验笔记，正式签署仍未提交。');}catch(error){message('未导入：'+error.message,true);}finally{event.target.value='';}});
byId('reset').addEventListener('click',()=>{if(!window.confirm('只清空本页体验记录，不修改产品、机器证据或项目签署。继续吗？'))return;state=blank();fill();save();message('已清空本页记录。');});
</script></body></html>'''
PAGE=PAGE.replace('__PORTS__',''.join(f'<option value="{p}">{p}</option>' for p in range(18765,18776))).replace('__PS__',e(ps)).replace('__CHECKS__',check_html).replace('__OUTLINE__',outline).replace('__SIGNATURE__',e(data['signature'])).replace('__CANDIDATE__',candidate).replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c'))
assert '__PS__' not in PAGE
OUT.write_text(PAGE,encoding='utf-8')
report=Path(__file__).resolve().parent
(report/'video-start-command.txt').write_text(ps+'\n',encoding='utf-8')
(report/'guide-source-binding.json').write_text(json.dumps({'kind':'MANUAL_GUIDE_SOURCE_BINDING_NOT_ACCEPTANCE','product_candidate':candidate,'machine_receipt_sha256':hashlib.sha256((REPORT/'receipt.json').read_bytes()).hexdigest(),'independent_review_sha256':hashlib.sha256((REPORT/'independent-review.json').read_bytes()).hexdigest(),'guide_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'product_services_started':0,'model_calls':0,'human_signoff_submitted':False},indent=2)+'\n')
print(OUT)
