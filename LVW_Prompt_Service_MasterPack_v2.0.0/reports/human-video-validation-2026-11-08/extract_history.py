from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;STATE=ROOT.parent.parent/'.lvw-runtime/lvw-prompt-service/V0-S2/full-v0-auto-08'
DEST=OUT/'historical';DEST.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
public=STATE/'default-raw/temp/public-phase';frozen=json.loads((ROOT/'reports/v0-s2/frozen-structural-inputs-02.json').read_text());items=[];copies=[]
def copy(p,name):
 dest=DEST/name;shutil.copyfile(p,dest);assert sha(p)==sha(dest);copies.append({'file':name,'archive_relative':str(p.relative_to(STATE)) if p.is_relative_to(STATE) else str(p.relative_to(ROOT)),'sha256':sha(dest)});return dest
for category,meta in frozen['categories'].items():
 source=ROOT/meta['path'];assert sha(source)==meta['sha256'];clip=copy(source,category+source.suffix)
 history=copy(public/('category-'+category+'.history.json'),category+'.history.json');oracle=copy(public/('category-'+category+'.oracle.json'),category+'.oracle.json');graph=copy(public/('category-'+category+'.graph.json'),category+'.graph.json')
 record=next(iter(json.loads(history.read_text()).values()));raw,suggestion,technical=record['outputs']['1']['text'];suggestion=json.loads(suggestion);technical=json.loads(technical);oracle=json.loads(oracle.read_text());
 (DEST/(category+'.raw-response.txt')).write_text(raw);(DEST/(category+'.suggestion.json')).write_text(json.dumps(suggestion,ensure_ascii=False,indent=2)+'\n')
 poster=DEST/(category+'.jpg');p=subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(clip),'-vf','fps=0.5,scale=320:-2,tile=2x2','-frames:v','1',str(poster)],capture_output=True,timeout=30);assert p.returncode==0
 items.append({'id':category,'video':str(clip.relative_to(ROOT)),'sha256':meta['sha256'],'poster':str(poster.relative_to(ROOT)),'suggestion':suggestion,'raw_response':raw,'technical':technical,'oracle':oracle,'process':['公开Comfy队列提交LVWVideoPromptOwner，空用户指令、gemma4:26b、realistic','FFmpeg/PyAV按真实PTS取四帧，逐帧调用本机Ollama','核对源哈希/PTS/帧哈希/Provider增量/释放，保留history原始输出'],'limits':['合成结构样本，不能证明真实风格识别质量','原始结果保留，不补写缺失中文或运动信息']})
phases={}
for phase in ['public','browser','cancel','fault']:
 p=STATE/'default-raw/temp'/(phase+'-phase')/'phase-receipt.json';copy(p,phase+'-receipt.json');phases[phase]=json.loads(p.read_text())
for kind in ['online','offline']:
 p=STATE/'default-raw/temp/cumulative-phase'/(kind+'-receipt.json');copy(p,'cumulative-'+kind+'.json');phases['cumulative-'+kind]=json.loads(p.read_text())
p=STATE/'warm-raw/temp/warm-phase/hot-records.json';copy(p,'warm-hot-records.json');phases['warm']=json.loads(p.read_text())
receipt=json.loads((ROOT/'reports/v0-s2/full-v0-auto-08/receipt.json').read_text())
(OUT/'history.json').write_text(json.dumps({'kind':'READ_ONLY_HISTORICAL_FULL08_REPORT_EXTRACTION_NOT_NEW_RUN','run_id':'full-v0-auto-08','candidate_sha':receipt['candidate_sha'],'receipt':receipt,'items':items,'phases':phases,'source_copies':copies,'new_model_calls':0,'stage_pass_claim':False},ensure_ascii=False,indent=2)+'\n')
print('Historical videos',len(items),'verified source copies',len(copies))
