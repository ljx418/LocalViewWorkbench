from pathlib import Path
import datetime,hashlib,json,subprocess,zipfile,csv
ROOT=Path(__file__).resolve().parents[2];ASSETS=ROOT/'人工验收视频集';OUT=Path(__file__).resolve().parent
# Observational annotations written after contact-sheet inspection; no LVW result exists for these clips.
labels=[
('实拍教程 / 手机交互',['户外人物使用手机，画面在手机特写、人物和天空之间切换','手机界面和英文引导文字可见，整体自然日光、浅景深'],'人物在户外操作手机；以近景和人物镜头交替呈现云层观察教程。',['不能只依据来源标题声称整段只有云层','不编造手机品牌、人物身份或未听取的对话']),
('森林航拍 / 三维地形',['森林、山谷与河道的高处视角','先出现机翼，再转为森林地形/三维数据视图'],'从飞机机翼附近俯瞰森林山谷，再过渡到森林地形的三维视图。',['不要把机翼误当建筑屋顶','不要凭素材标题确定拍摄国家或灾害原因']),
('复古地图 / 路径图解',['灰白航海地图、虚线与红色路径','画面有推移或缩放，地图上能看到Gulf Stream等标注'],'复古灰白地图上显示虚线和红色航迹，镜头沿地图移动以说明路径。',['不能声称看到真实海底动物或潜艇实拍','不要求精确读出所有小字或经纬度']),
('野生动物 / 长焦特写',['树枝间的大型鸟巢和巢内的鸟','蓝天背景、长焦固定近景；动作较轻微'],'蓝天下，树枝之间的大鸟巢中可见一只鸟，镜头稳定，鸟有轻微头部变化。',['不能编造捕食、展翅飞走或大量幼鸟','物种若不能确认可称鸟类；不强求白头海雕名称']),
('写实地表CGI / 机械载具',['橙褐色地表上的六轮探测车','高处斜俯视，载具和地面阴影清晰，缓慢变化'],'写实三维动画中，六轮探测车位于橙褐色地表，镜头从高处斜俯视。',['不是实景道路汽车广告','未见无人机起飞时不能依据完整片名编造直升机动作']),
('快速混剪 / 航天主题',['发射台与橙白火箭、月面车、带太阳翼的空间设施先后出现','存在明显场景切换，不能把多个地点合并为一个连续实景'],'快速切换的航天画面展示发射台火箭、月面车辆与轨道中的太阳翼设施。',['不能只描述最后一帧','不可补写爆炸、战争或当前片段之外的飞船喷焰']),
('夜景延时 / 展陈建筑',['深蓝夜空下的数座竖直火箭展品，前景有树木暗影','镜头基本固定，夜空中可见稀疏亮点/微小变化'],'固定机位拍摄夜色中的火箭展陈，深蓝天空与树影形成安静的夜景。',['不能说火箭正在发射或爆炸','四帧不足时不强求判定星轨速度；不编造城市名']),
('室内纪实 / 工作人群',['明亮大窗的控制室，成排显示器与戴耳机的工作人员','先是室内较广视角，随后切到工作人员近景'],'纪实镜头展示控制室的显示器阵列和戴耳机的工作人员，随后转向人物近景。',['不根据人物外貌推断身份或情绪','不编造屏幕具体读数和故障事件']),
('科学光影 / 高对比绿色',['黑色背景中有绿色圆形观察区域','区域内部的纹理和流动样结构随时间变化，顶部有装置轮廓'],'高对比科学影像中，绿色圆形观察窗内的流动纹理不断改变，周围为黑色背景。',['不声称能从画面确定液体化学成分','不要把光影直接定性为火灾、肿瘤或真实夜视战斗']),
('太空CGI / 航天器近景',['白色航天器及深色太阳翼、蓝白地球和黑色太空','相对视角变化使太阳翼和舱体在画面中移动'],'三维太空动画近距离展示白色航天器和太阳翼，地球在背景中弯曲延展。',['不能把CGI断言为真实航天员拍摄','不编造舱内人物、发射日期或精确型号']),
('地球信息图 / 多层可视化',['黑色背景上的小地球逐渐变大，出现卫星/轨道和文字标注','末段出现空间站结构与地球，存在视图转换'],'黑色背景上的地球逐渐放大，并叠加卫星轨道和标注，随后转向空间设施视角。',['不能只描述为一张静态地球照片','不把图解轨道当作真实可见光轨，不强求小字逐字识别'])]
a=json.loads((ASSETS/'assets.json').read_text());items=[]
for asset,(style,must,example,avoid) in zip(a['items'],labels,strict=True):
 asset['style']=style;asset['expected_observation_status']='FROZEN_BEFORE_ANY_LVW_INFERENCE';p=ROOT/asset['video_path']
 result=subprocess.run(['ffmpeg','-nostdin','-v','error','-threads','2','-i',str(p),'-map','0:v:0','-f','null','-'],capture_output=True,timeout=30);assert result.returncode==0
 asset['full_decode_exit_code']=0
 (ASSETS/(asset['id']+'.source.json')).write_text(json.dumps(asset,ensure_ascii=False,indent=2)+'\n')
 items.append({'id':asset['id'],'video_sha256':asset['video_sha256'],'style':style,'must_observe':must,'example_prompt':example,'must_not_invent':avoid,'basis':'Independent visual inspection of six temporal thumbnails; no LVW response or model self-rating used.','lvw_status':'NOT_RUN'})
a['items']=a['items'];(ASSETS/'assets.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
payload={'kind':'FROZEN_HUMAN_OBSERVATION_EXPECTATIONS_NOT_PRODUCT_RESULTS','version':1,'candidate_sha':'719c74559393a6489b2f630a1e0d3bc3303eb655','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'lvw_model_calls':0,'formal_stage_denominator_changed':False,'rule':'Subject, visual style, visible changes and uncertainty; wording need not match example. No identity/geography/chemistry inference from metadata.','items':items}
p=ASSETS/'expected-results.frozen.json'
with p.open('x') as f:f.write(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest={'kind':'PRE_INFERENCE_HOLDOUT_FREEZE','expected_sha256':sha(p),'assets_manifest_sha256':sha(ASSETS/'assets.json'),'videos':[{k:x[k] for k in ['id','video_sha256','video_path','bytes','duration_seconds','width','height']} for x in a['items']],'lvw_status':'ALL_NOT_RUN','independent_sample_selection':False,'selection_limit':'Assistant acquired and annotated these samples; this is not a cryptographic double-blind or independent S3 quality set. The target LVW model has not been invoked on them.'}
(ASSETS/'FREEZE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with (ASSETS/'licenses.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['id','title','creator','license','license_url','source_url','download_url','modifications'])
 for x in a['items']:w.writerow([x['id'],x['title'],x['creator'],x['license'],x['license_url'],x['source_url'],x['download_url'],json.dumps(x['transformation'])])
(ASSETS/'SHA256SUMS.txt').write_text('\n'.join(x['video_sha256']+'  videos/'+x['id']+'.mp4' for x in a['items'])+'\n')
with zipfile.ZipFile(ASSETS/'人工验证视频_11段.zip','x',compression=zipfile.ZIP_STORED) as z:
 for x in a['items']:z.write(ROOT/x['video_path'],'videos/'+x['id']+'.mp4')
 for name in ['licenses.csv','SHA256SUMS.txt']:z.write(ASSETS/name,name)
print('frozen',len(items),'clips; expected hash',manifest['expected_sha256'],'video bytes',sum(x['bytes'] for x in a['items']))
