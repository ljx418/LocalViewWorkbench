"""Author review from manual visual observations; no media/model/source access."""
import json,pathlib,hashlib,shutil
O=pathlib.Path(__file__).resolve().parent;D=O.parent;P=O.parents[4]
read=lambda p:json.loads(p.read_text())
write=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
for name in ['review.md','independent-review.json','prelabels.json','selection-proposal.json']:
 dest=O/('superseded-draft-'+name)
 if not dest.exists():shutil.copyfile(D/name,dest)
old=read(O/'superseded-draft-prelabels.json');M=read(O/'preview-map.json');checks=read(O/'continuation-verification.json')
# Actual visual observations by the continuation reviewer using view_image.
# category | visible count | objects / scene | pose cues | composition/light/style | text
notes=[
('双人正式服装近景','2个可见人物','灰色浅背景；首饰；画面中横向半透明薄纱状区域','两人面孔接近；右侧人物的一只手环在左侧人物颈部附近，手上有戒指','竖幅紧特写；柔光；半透明区域可能是薄纱，不能认定为后期光带','Live in your eyes'),
('单人面部近景','1个可见人物','浅色背景与右侧粉色亮点；深发刘海','面对镜头，嘴角上扬露齿','方形预览中上下黑边；脸占大部','左上黄色残缺文字，com可见，其余不完整'),
('双格正式服装人像','每格2个可见人物，不能相加为4人','浅色礼服、深色领结西装；木箱；右侧蓝色窗面','上格手靠近木箱；下格手持浅色卡片在箱口处','上下两格黑色分隔；暖室内与冷窗光','未见需转写的清楚文字'),
('双格舞台人像','上格2人；下格多人，裁切及低分辨率无法精确计数','白礼服、深色套装；花艺；舞台灯与装饰','上格两人有抬手姿态；下格多人部分举臂','上下拼图，明亮舞台照明','小字UNKNOWN'),
('礼服及局部人物细节','至少2个局部人物；面孔不清楚','大面积白裙与头纱；右上深色西装局部；白花装饰','人物相邻；可见手臂局部，具体动作UNKNOWN','紧裁切裙摆占大部；白色亮点','无可靠可读文字'),
('多格近景拼贴','7格，每格1个主要人物；不据此认定7人','深发；树叶、灯光与夜色','不同格嘴形与头部朝向不同，一格手靠近头发','上4下3拼贴；夜间灯光','小字UNKNOWN'),
('戴眼镜人物近景','1个主要可见人物；远景人数UNKNOWN','大深色眼镜；树木、路灯、招牌及街道','面孔靠近镜头，嘴角轻微上扬','横幅近摄透视明显；夜景；不能确定镜头种类或焦距','远处招牌不可可靠转写'),
('白边框内人物肖像','1个可见人物','棕色肩长发、刘海；黑衣；十字状吊坠；暖色背景','头部稍偏，目光偏向画面一侧','竖图嵌在白色边框；暖光','标题含-7.png，其余字形不能可靠辨读'),
('八格人物拼贴','每格1个主要人物；身份一致性UNKNOWN','浅衣、浅墙；深色肩长发','不同格可见V形手势、手靠近嘴边、头部倾斜','上4下4拼贴；亮室内','小标签含.mp4与t=；不把标签当实测PTS'),
('带标签的竖幅人像','1个可见人物','深色眼镜；蓝色衣服；右下绿色平面；室内背景','手在脸旁形成V形','竖图在白边中；近景；绿色区域不是已证实绿幕','标题含-1.mp4与t=2.972s；其余字形UNKNOWN'),
('眼镜人物极近景','1个可见人物','大眼镜；深色头发；暗背景','面孔贴近画面，嘴角上扬','极近裁切；眼镜和脸占满','UB_SeedVR2_full t=5.00s；只是画面文字'),
('双人近景带标签画面','2个可见人物','左侧深发人物；右侧人物侧脸被边缘裁切；浅色背景','两张面孔相向；左侧嘴角上扬','横幅极近景；右侧局部失去细节','标题含-5.mp4与t=160.041s；不据此断言本图是完整视频'),
('带播放器的界面截图','内嵌画面1个主要人物','深色界面、按钮、橙色强调；内嵌夜景人物戴眼镜','内嵌人物嘴唇前突；页面本身无动作可判','界面截图；文字和媒体窗口并存','H3 身份参考矩阵；推荐母版；P01_GIV t=0.15s；页面声称不是外部事实'),
('红色装饰背景正式服装人物','1个主要可见人物','浅金色绣花衣饰、头饰；红色囍字剪纸和红色背景','两只手抬在身侧，靠近剪纸；不支持一手叉腰','竖向人物构图；明亮暖光','囍'),
('城市夜间人物与环境','右侧1个主要人物；后方另1个局部人物；远景多人数量UNKNOWN','条纹上衣；多层亮灯建筑、街灯、招牌、人群与两轮车轮廓','主要人物侧向站立望向画面左侧','竖幅近景人物与较广街景；夜间混合照明','远景招牌小字UNKNOWN'),
('标签竖幅人物近景','1个可见人物','深色肩长发遮部分脸；浅衣浅墙；左侧模糊手部','头偏向一侧；左侧手入画，动作UNKNOWN','白边包围竖图；柔亮室内','标题含-3.mp4与t=12.354s；其余UNKNOWN'),
('夜景人物近景','1个主要可见人物','深发刘海；树、路灯与背景散景','嘴角上扬，眼睛略眯','横幅脸部近景；右上强灯光','P05_GIV t=2.00s'),
('镜面构图正式礼服人物','前景背影与镜中正面，构图支持1人及其倒影，非直接2人','珠饰浅色礼服；镜边球灯；右侧冷蓝窗面','手靠近耳饰','过肩镜面构图；暖灯与冷窗光对照','无可靠可读文字'),
('夜景眼镜人物近景','1个主要可见人物','细框眼镜；深发；夜景树木和灯光','头侧向，脸朝镜头，嘴角上扬','横幅近景；夜间混合照明','P04_GI t=5.00s'),
('镜面构图花饰礼服人物','前景背影与镜中正面，可能为1人及其倒影','胸前成簇白花；镜边球灯与右侧冷蓝窗面','手靠近耳饰','与C18构图高度近似；花饰及表情有差异；暖冷光对照','无可靠可读文字'),
('夜景单人四帧','每个采样格1个主要人物，背景人数UNKNOWN','深发深衣；树叶、路灯与夜色','f01嘴唇前突；f02嘴角上扬；f03手在头发旁；f04嘴角上扬','四格景别有差异；夜间近景','小字UNKNOWN'),
('花艺玻璃建筑背景单人四帧','每格1个主要人物','白色礼服与头纱；玻璃格窗、白花、绿植','f01侧面；f02更朝镜头；f03/f04正面更多且嘴角上扬；手持纱边','柔和亮光；背景虚化；实际运镜UNKNOWN','小字UNKNOWN'),
('夜景外部到窗边室内的四帧','f01主要1人；f02–f04主要2人；背景人数UNKNOWN','深蓝外套、米色高领、眼镜；驼色外套、深红围巾；湿亮路面和候车亭状结构；f04桌、杯、窗','f01嘴略张；f02两人相向站立；f03两人嘴角上扬且手搭上臂；f04两人坐在桌边，手在杯边','f01单人近景；f02双人较广；f03较近；f04暖调窗边室内；场景差异可见，切点UNKNOWN','眼镜绿色反光属光照，不是文字；其它小字UNKNOWN'),
('竖幅室内单人四帧','每格1个主要人物','浅色衣服与墙；深色肩长发','f01嘴角上扬；f02头略倾斜；f03头偏转且头发遮部分脸；f04露齿且左侧V形手势入画','竖幅亮室内近景；真实动作连续性UNKNOWN','无可靠可读文字'),
('湿亮夜景单人四帧','每格1个主要人物；f01/f02远处另有人影，数量UNKNOWN','眼镜、深色外套、浅色高领；手持矩形设备；玻璃亭状结构、灯光、湿路面','f01/f02低头看向手中物；f03/f04抬头且嘴微张','夜景；f04脸部更大；与C23 f01视觉近似','亭上小字UNKNOWN'),
('车道及汽车人物四帧','1个主要站立人物；车内人影不能可靠计数','深西装领结；浅色矩形纸片；黑色汽车、树、檐篷、湿亮地面','人物站立；汽车相对画面和站立人物向左改变位置','白天较广构图；不能排除镜头运动，也不能断定车速','小字UNKNOWN'),
('汽车旁多人四帧','3个主要人物；车内另有局部人影，是否额外人物UNKNOWN','前景浅色西装背影；浅色礼服；后方深色西装；汽车与树木','f01礼服人物朝前；f02–f04头偏向后方；后方人物嘴角变化','白天，前中后景人物分层；连续转头过程未观测','小字UNKNOWN'),
('夜间玻璃亭旁单人四帧','每格1个主要人物','驼色外套、暗红围巾、弯柄收拢伞；湿路面、玻璃亭、灯光','f01头朝前；f02朝向略偏；f03双手靠伞；f04嘴角上扬更明显','夜景半身近景；与C23服装/环境近似','亭上文字不可可靠转写'),
('汽车旁西装人物四帧','每格1个主要人物','黑色西装、领结、胸花状装饰；浅色纸片；汽车、树木、建筑门口','f01嘴微张；f02手靠胸口；f03双手靠胸前持浅纸；f04头转向右侧，未完全背对镜头','白天半身近景；与C31 f04近似','纸片字UNKNOWN'),
('沙发室内单人四帧','每格1个主要人物','洋红套装、白领、深色领带状物；米色拉扣沙发、靠垫、茶具与茶几','f01/f02斜靠沙发，手在腿部；f03/f04一腿屈起，手靠膝腿；没有足够证据指认手机','暖室内，较高视角；同一房间四格；动作连续性UNKNOWN','右上小水印存在，本次拼图尺度不能可靠转写'),
('车道/车内外不同构图四帧','f01主要1人；f02/f03主要2人；f04主要1人；身份连续性UNKNOWN','黑色汽车、檐篷、树木；深色西装与浅色礼服；f03另有浅西装人物；浅色纸片','f01站车旁持纸；f02礼服人物在车内、深西装人物在外；f03礼服人物站在车外靠浅西装人物；f04手靠胸前持纸','四格明显不同景别/空间状态；不能据4帧精确计数镜头或切换次数','纸片小字UNKNOWN'),
('低视角走廊单人四帧','每格1个主要人物','短棕发、深色牛仔外套；红橙纹样门、绿色门牌灯、开关、穿孔金属板、红色告示','f01回望方向；f02脸偏向画面左侧；f03下巴抬起；f04视线较低','暖色走廊；明显低视角；机位差异和动作连续性UNKNOWN','门上901及ROOM可见；绿色牌数字似901；告示和水印小字不转写')
]
assert len(notes)==32
out=[]
for m,n,prev in zip(M,notes,old['prelabels']):
 assert prev['file_id']==m['file_id']
 refs=[]
 for ref in prev['preview_refs']:
  ref=dict(ref);ref['prior_agent_reported_viewed']=ref.pop('viewed',False);ref.pop('view_note',None)
  ref['viewed']=ref['kind']==('thumbnail' if m['media_kind']=='image' else 'contact_sheet')
  ref['view_note']='本接续会话用view_image实际查看' if ref['viewed'] else '本接续会话未单独打开；视频帧仅通过登记contact sheet四格观察'
  refs.append(ref)
 row={k:prev[k] for k in ['asset_id','file_id','source_sha256','source_relative_path','media_kind','probe_facts_from_container']}
 row.update(preview_refs=refs,observation_basis='接续独立审查者亲自查看20个thumbnail与12个四格contact sheet；看过前代理草稿后复核，故不是第二次从零盲标；未读任何LVW结果/人工稿/expected答案。',observable_facts=dict(zip(['subject_category','visible_person_count','scene_and_objects','pose_and_action_cues','composition_lighting_style','visible_text'],n)),unknown_or_ambiguous=['身份、年龄、关系、地点、拍摄来源与制作方式UNKNOWN；不由文件名推断。','小字/细节限于预览分辨率；未显示的内容UNKNOWN。'],prohibited_assertions=['不得推断身份、年龄、国籍、人物关系、对话、声音、心理或剧情。','不得把画面内文字或文件名当成外部事实或项目模型质量证明。'],applicable_obligation_dimensions={'人物':'可见主体及局部/反射/人数边界','场景':'场景与可见道具，未知保持未知','动作':'仅姿态及采样间变化线索','证据一致性':'逐项登记预览文件与hash，事实绑定本图或f01–f04','未知/局限':'不能判定必须UNKNOWN；不因缺细节扣除分母'},acceptance_notes='独立Agent视觉观察，非人签、非LVW评分、非模型达标；资格不等于语义质量。')
 if m['media_kind']=='video':
  row['temporal_obligations']={k:'UNKNOWN' for k in ['actual_pts','exact_shot_count','cut_times','continuous_motion','camera_motion','occlusion_between_samples','audio']}
  row['unknown_or_ambiguous'].append('仅看登记四格采样拼图，未看完整视频；请求偏移非实际PTS，帧间连续运动/切换方式/遮挡UNKNOWN。')
  row['prohibited_assertions'].append('不得断言实际切换次数或时间、推轨/变焦、完整动作链；容器时长是收据事实而非观看时长。')
 out.append(row)
prov={'previous_dispatch':'ctx_f9a99284a861','current_dispatch':'ctx_464e91f112d9','interruption':'Coordinator reported prior Claude worker HTTP429 Token Plan exhaustion, stopped with ptyKilled=true; draft was unfinished.','handoff_authorization':'msg_5f9c2313c976 and msg_3e7b46aef821; preserve drafts, accept existing once-run 45 tests, no remerge required.','prior_draft_status':'SUPERSEDED_NOT_FINAL; copies under raw/superseded-draft-* retain history, not current findings.','current_role':'Independent Codex continuation, separate from implementation; conclusions rechecked, not inherited.','prior_reported_viewed':80,'continuation_actual_viewed_files':32,'continuation_viewed_assets':32,'continuation_viewed_image_thumbnails':20,'continuation_viewed_video_contact_sheets':12,'continuation_video_frames_observed_via_sheets':48,'blindness_limit':'Read prior independent labels before visual recheck. No LVW raw, human draft or expected answer read. Not a second blind replication.'}
payload={k:old[k] for k in ['kind','schema_version','authority','is_human_signature','candidate_eligibility_is_not_semantic_quality','model_calls','gpu_actions','network_calls','obligation_dimension_glossary']}
payload.update(produced_by='Independent Claude draft continued and visually rechecked by independent Codex; neither is implementer',continuation_provenance=prov,observation_provenance={'status':'BLIND_TO_PROJECT_RESULTS_PRELABEL_VISUALLY_RECHECKED','method':'view_image: 20 thumbnails and 12 existing video contact sheets; all 32 assets actually observed','preview_root_relative_to_package':'.agent-governance/runtime/receipts/s3-preview-c01/run-01','runtime_workspace':'<implement-workspace>','no_original_media_access':True,'external_media_api_calls':0,'no_full_video_viewing':True},counts={'prelabels':32,'images':20,'videos':12,'preview_files_listed':100,'preview_files_viewed':32,'video_frames_observed_via_contact_sheets':48,'prior_agent_claimed_viewed_files':80},prelabels=out)
write(D/'prelabels.json',payload)
# One proposal, linked mechanically to corrected per-asset identities.
img=['C01','C03','C04','C07','C10','C12','C13','C14','C15','C18'];vid=['C23','C31','C22','C24','C30','C32']
why={'C01':'双主体紧特写、薄纱状遮挡及清楚英文','C03':'双格拼图与道具状态差异，不捏造动作过程','C04':'多人舞台与人数不确定边界','C07':'夜景眼镜近摄与背景小字局限','C10':'V形手势、绿色前景平面及标签；不能误称绿幕','C12':'双人相向近景与边缘裁切','C13':'界面文字与内嵌图像；页面声明不可当事实','C14':'红囍剪纸、浅金绣饰和双手抬起姿态','C15':'城市街景远近人物及低分辨率招牌','C18':'镜像人物去重和暖冷光','C23':'外部湿夜景与室内桌边的明显场景差异；两主体；切点未知','C31':'车内/外空间状态与多种构图；严格不猜完整故事或切点','C22':'短片容器时长、柔光花艺及头部朝向变化','C24':'竖幅室内近景和V形手势；连续动作未知','C30':'室内家具场景、腿与手姿态变化；避免把不明物猜成手机','C32':'低视角、门牌文字、姿态变化；小字未知'}
by={x['asset_id']:x for x in out}
def selection(ids):
 return [{**{k:by[i][k] for k in ['asset_id','file_id','source_sha256','media_kind']},'preview_refs':by[i]['preview_refs'],'unique_contribution':why[i]} for i in ids]
proposal={'kind':'S3_PREP_C_INDEPENDENT_SELECTION_PROPOSAL','authority':'PROPOSAL_ONLY_NOT_A_FREEZE','is_human_signature':False,'continuation_provenance':prov,'denominator':{'images':10,'videos':6,'images_proposed':10,'videos_proposed':6,'denominator_reduced':False},'selection_basis':['类别、构图、光照与可观察义务覆盖','四帧可见的状态差异复杂度，非已知运动/剪切真值','视觉近重复排除；未用模型结果或成功率；不按可获高分筛样'],'proposed_images':selection(img),'proposed_videos':selection(vid),'visual_near_duplicate_groups':[{'assets':['C18','C20'],'basis':'镜面、球灯、窗面、礼服姿态高度相似；保留C18','provenance_claim':'仅视觉相似，非证明同源'},{'assets':['C07','C11','C19'],'basis':'眼镜夜景面部近景相似；保留C07；不认定同一人'},{'assets':['C09','C16','C24'],'basis':'浅衣深发室内姿态与构图近似；保留视频C24；不能仅凭标签证明同源'},{'assets':['C23','C25','C28'],'basis':'夜景玻璃亭、服装与人物外观近似；仅保留C23'},{'assets':['C26','C27','C29','C31'],'basis':'车、衣饰、环境重叠；C26近C31 f01、C29近C31 f04；仅保留C31，C27也排除以减少未采样中段重叠风险'}],'other_exclusions':{'C02':'室内极近面孔和残缺字；固定10槽优先保留已列构图覆盖，不声称它是夜景近重复','C05':'局部/低信息可用于未知义务，但此次10槽优先保留其他构图；不推断其达不到分数','C06':'拼贴义务已有C03/C04，夜景已有C07；非严格同源证明','C08':'静态肖像与边框义务已有其它选项','C17':'夜景单人近景义务已有C07；不作同人认定','C21':'夜景人物覆盖已有C07/C23；视频6槽优先增加C30室内姿态；不声称动作等价'},'coverage_gaps_declared':['仅32个固定候选内建议，无替换源；不能代表全语料类别广度。','视频均以人物为主；无可靠运动体育/动物/人群广度；C26存在汽车相对位移但被近重复排除，不能称原候选没有车辆运动线索。','四帧无法冻结完整动作、真实运镜、快切/遮挡时序或实际PTS真值；6片不能独自证明原A12全部质量义务，相关真值UNKNOWN，需root裁决补齐规格而非减分母。','C24确为竖幅，C30提供不同室内构图；静态/含糊及快切等完整类别是否满足仍UNKNOWN。','视觉相似只能提示重复风险，不能证明制作簇数量、同演员或来源；不声称全批只有4个制作簇。','水印或内容风格不触发新审批；来源/权利未知按冻结catalog事实保留，不擅设C30清理水印前置。','10图与6片及>=8/10、>=5/6、关键幻觉0不变；此为S3准备建议，不能替代V1的不同质量分母。'],'final_freeze_owner':'root','quality_pass_claim':False,'changes_from_unfinished_draft':['修正C10/C14的file_id/source_sha256错配','视频C27改为C30，减少C31同环境近重复并增加室内姿态类别','纠正无竖版、手机、水印审批、固定制作簇及按可得分排除C05等无依据描述']}
write(D/'selection-proposal.json',proposal)
write(O/'continuation-provenance.json',prov)
print('written 32 visually rechecked prelabels; one 10+6 proposal')
