import subprocess,socket,os,json
from pathlib import Path
checks=[]
for name,action in [('Popen',lambda:subprocess.Popen(['/bin/true'])),('system',lambda:os.system('true')),('fork',os.fork),('exec',lambda:os.execv('/bin/true',['true'])),('socket',lambda:socket.socket())]:
 try:action()
 except RuntimeError as e:
  assert str(e).startswith('REVIEW_PREIMPORT_DENIED:');checks.append({'operation':name,'refused':str(e)})
 else:raise AssertionError('BOUNDARY_FAILED:'+name)
Path(__file__).with_name('guard-selftest-results.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks,indent=2))
