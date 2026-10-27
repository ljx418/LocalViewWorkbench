from pathlib import Path
from playwright.sync_api import sync_playwright
import json, time, threading, shutil
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from jsonschema import Draft202012Validator
R=Path(__file__).resolve().parents[1];out=R/'reports/previews';results=[];errors=[];remote=[]
server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(R)))
threading.Thread(target=server.serve_forever,daemon=True).start()
BASE='http://127.0.0.1:'+str(server.server_port)
def ck(n,v,d=''):results.append({'check':n,'passed':bool(v),'detail':d})
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=shutil.which('chromium') or shutil.which('google-chrome'),headless=True,args=['--no-sandbox'])
 context=browser.new_context(accept_downloads=True)
 page=context.new_page();page.set_default_timeout(4000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda req:remote.append(req.url) if req.url.startswith(('http://','https://')) and not req.url.startswith(BASE) else None)
 for width in [360,768,1440,1920]:
  page.set_viewport_size({'width':width,'height':1000});page.goto('about:blank');page.set_content((R/'START_HERE.html').read_text(),wait_until='load');page.wait_for_timeout(150)
  ck(f'overview width {width}',page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),str(page.evaluate('document.documentElement.scrollWidth')))
  ck(f'overview h1 {width}',page.locator('h1').first.is_visible())
  if width in [360,1440]:page.screenshot(path=str(out/f'overview-{width}.png'),full_page=True)
 page.set_viewport_size({'width':1440,'height':1000});page.goto('about:blank');page.set_content((R/'START_HERE.html').read_text(),wait_until='load');page.screenshot(path=str(out/'overview-desktop-top.png'))
 for v in ['V0','V1','V2','V3']:
  page.locator(f'[data-arch="{v}"]').click();ck('architecture '+v,page.locator(f'[data-arch="{v}"]').get_attribute('class')=='active' and len(page.locator('#archflow .node').all())==3)
 # all document buttons load correct heading
 for i in range(22):
  page.locator(f'[data-doc="{i}"]').click();ck('reader doc '+str(i),bool(page.locator('#docbody h1').text_content()))
 page.goto('about:blank');page.set_content((R/'prototype/index.html').read_text(),wait_until='load');page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path=str(out/'prototype-v0-desktop.png'),full_page=True)
 ck('v0 save intentionally disabled',page.locator('#save').is_disabled())
 draft='独立人工稿：模型失败也不能覆盖这段文字。';page.locator('#draft').fill(draft)
 page.locator('#analyze').click();page.wait_for_timeout(550);ck('analysis preserves draft',page.locator('#draft').input_value()==draft)
 page.locator('#unavailable').click();ck('no-model editor enabled',page.locator('#draft').is_editable() and page.locator('#draft').input_value()==draft)
 page.locator('#analyze').click();page.locator('#cancel').click();page.wait_for_timeout(550);ck('cancel preserves draft',page.locator('#draft').input_value()==draft and '取消' in page.locator('#state').text_content())
 page.locator('#compile').click();ck('compile no auto overwrite',page.locator('#draft').input_value()==draft)
 page.locator('[data-version="V1"]').click();page.locator('#save').click();ck('v1 session revision',page.locator('#history .mini-card').count()==1)
 for mode in ['documentary','realistic','scifi','science','cinematic','stylized']:
  page.select_option('#mode',mode);page.locator('#compile').click();ck('mode '+mode,'CPU 格式整理示意' in page.locator('#suggestion').text_content())
 for target in ['natural','image','edit','motion']:
  page.select_option('#target',target);page.locator('#compile').click();ck('target '+target,page.locator('#draft').input_value()==draft)
 with page.expect_download() as dl:page.locator('#exportjson').click()
 download=dl.value;download.save_as(str(R/'reports/prototype-export.json'))
 export=json.loads((R/'reports/prototype-export.json').read_text());core=json.loads((R/'contracts/lvw.schema.json').read_text());val=Draft202012Validator({'$ref':'#/$defs/V0Result','$defs':core['$defs']});ck('prototype export valid schema',not list(val.iter_errors(export)));ck('prototype export labelled demo','DEMO_NOT_MODEL_RESULT' in export['warnings'])
 page.screenshot(path=str(out/'prototype-v1-desktop.png'),full_page=True)
 page.locator('[data-version="V2"]').click();page.locator('[data-page="library"]').click();page.locator('#search').fill('科幻');ck('asset filter',page.locator('#assets .card').count()==1);page.screenshot(path=str(out/'prototype-v2-library.png'))
 page.locator('[data-version="V3"]').click();page.locator('[data-page="integrations"]').click();page.locator('#unknown').click();ck('unknown submit state', 'SUBMISSION_UNKNOWN' in page.locator('#receipt').text_content());page.screenshot(path=str(out/'prototype-v3-integrations.png'))
 page.locator('#peerfail').click();ck('peer offline', 'PEER_UNAVAILABLE' in page.locator('#receipt').text_content())
 for width in [360,768,1440,1920]:
  page.set_viewport_size({'width':width,'height':1000});page.locator('[data-page="workbench"]').click();ck(f'prototype width {width}',page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),str(page.evaluate('document.documentElement.scrollWidth')))
  if width==360:page.screenshot(path=str(out/'prototype-mobile.png'),full_page=True)
 # CSS zoom is a separate smoke check, not a claim of native browser 200% compliance.
 page.set_viewport_size({'width':1280,'height':900});page.evaluate("document.body.style.zoom='2'");ck('prototype 200% CSS zoom export reachable',page.locator('#exportjson').is_enabled());page.locator('#exportjson').scroll_into_view_if_needed();page.evaluate("document.body.style.zoom='1'")
 context.close();browser.close()
ck('no browser page errors',not errors,str(errors));ck('no network asset requests',not remote,str(remote))
report={'kind':'DESIGN_HTML_BROWSER_TEST_NOT_PRODUCT_E2E','passed':sum(c['passed'] for c in results),'failed':sum(not c['passed'] for c in results),'checks':results,'browser':'headless Chromium via Playwright','scope':'Chromium DOM rendering via set_content using exact local HTML; browser environment blocked file:// and loopback navigation, so page navigation was not validated','limitations':['No real ComfyUI/React product','No model or target GPU','CSS zoom smoke is not native zoom acceptance','No real file:// or HTTP navigation because environment policy blocks both']}
(R/'reports/HTML_SMOKE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False,indent=2))
for c in results:
 if not c['passed']:print('FAIL',c)
