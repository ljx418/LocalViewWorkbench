from pathlib import Path
import requests,json,concurrent.futures
out=Path(__file__).resolve().parent
queries=['clouds','forest','ocean','wildlife','helicopter','rocket','night','simulation','fluid','microscope','moon','earth']
def one(q):
 r=requests.get('https://images-api.nasa.gov/search',params={'q':q,'media_type':'video','page_size':3},timeout=25);r.raise_for_status();j=r.json();(out/('nasa-'+q+'.json')).write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n');return q,j['collection']['items']
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for q,items in pool.map(one,queries):
  print(q,[(x['data'][0]['nasa_id'],x['data'][0]['title']) for x in items],flush=True)
  rows.extend({'query':q,'item':x} for x in items)
(out/'nasa-candidates.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
