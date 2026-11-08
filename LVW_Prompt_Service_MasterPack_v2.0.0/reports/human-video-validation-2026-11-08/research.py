from pathlib import Path
import concurrent.futures,json,re,requests,time
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
queries=[('nature','自然海浪','ocean waves'),('timelapse','延时云层','clouds timelapse'),('macro','微距昆虫','butterfly close up'),('wildlife','动物纪实','duck swimming'),('city','都市夜景','city night traffic'),('sport','运动跟拍','skateboarding'),('underwater','水下生态','underwater fish'),('space','太空实拍','ISS earth'),('animation','三维动画','blender animation short'),('science','科学可视化','fluid simulation'),('archive','黑白历史影像','black white street 1900'),('fire','慢动作火焰','flame slow motion')]
def one(q):
 id,style,query=q;params={'action':'query','generator':'search','gsrsearch':'filetype:video '+query,'gsrnamespace':6,'gsrlimit':5,'prop':'imageinfo','iiprop':'url|size|extmetadata','format':'json'}
 r=requests.get('https://commons.wikimedia.org/w/api.php',params=params,headers={'User-Agent':'LVWValidationAssets/1.0 (local public-video evaluation)'},timeout=30)
 (OUT/(id+'-search.response')).write_text(r.text)
 rows=[]
 if r.status_code==200:
  for p in r.json().get('query',{}).get('pages',{}).values():
   i=p.get('imageinfo',[{}])[0];m=i.get('extmetadata',{});license=m.get('LicenseShortName',{}).get('value','')
   rows.append({'id':id,'style':style,'title':p['title'],'info':i,'license':license,'eligible':bool(re.search(r'CC0|Public domain|CC BY(?:-SA)? [1-4]',license,re.I)) and 0<i.get('size',0)<50000000 and 4<=i.get('duration',0)<=180})
 return rows
all=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for rows in pool.map(one,queries):
  all+=rows
  print([(r['id'],r['title'],r['info'].get('duration'),r['info'].get('size'),r['license'],r['eligible']) for r in rows],flush=True)
(OUT/'candidates.json').write_text(json.dumps(all,ensure_ascii=False,indent=2)+'\n')
