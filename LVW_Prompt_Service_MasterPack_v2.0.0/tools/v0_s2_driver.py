"""S2 lifecycle adapter; constructing it does not authorize or start services.

Reuse the recorded S1 process ownership/terminal checks without changing its
historical Harness. S2 replaces HTTP, localized PowerShell output handling,
submission accounting, and the transient decoder configuration.
"""
import importlib.util
from pathlib import Path
import subprocess

from tools.v0_s2_http import LoopbackClient,ControlError
import time

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / 'reports/v0-s1/wp-s1-03-phase-a/live_probe.py'
spec = importlib.util.spec_from_file_location('lvw_s2_lifecycle_base', LEGACY)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def comfy_wrapper(python, main, directory, pid_file, ffmpeg, ffprobe, *, warm=False):
    # Process environment only, never user/machine environment or PATH writes.
    probe=(f"$env:LVW_FFPROBE_EXE={base.ps_quote(ffprobe)}\n$env:LVW_VIDEO_PROBE_BACKEND='cli'\n" if ffprobe else
           "Remove-Item Env:LVW_FFPROBE_EXE -ErrorAction SilentlyContinue\n$env:LVW_VIDEO_PROBE_BACKEND='pyav'\n")
    if type(warm) is not bool:raise ValueError('BENCHMARK_MODE_INVALID')
    benchmark=("$env:LVW_WARM_BENCHMARK='run-owned-v1'\n" if warm else
               "Remove-Item Env:LVW_WARM_BENCHMARK -ErrorAction SilentlyContinue\n")
    return (f"$env:LVW_FFMPEG_EXE={base.ps_quote(ffmpeg)}\n"+probe+benchmark
            + base.comfy_wrapper_text(python, main, directory, pid_file))


class S2SystemDriver(base.SystemDriver):
    def __init__(self, args, evidence):
        super().__init__(args,evidence)
        if type(args.max_public_submissions) is not int or not 1 <= args.max_public_submissions <= 64:
            raise base.StopProbe('PUBLIC_SUBMISSION_BUDGET_INVALID')
        self.max_public_submissions = args.max_public_submissions
        self.warm_benchmark=getattr(args,'warm_benchmark',False)
        if type(self.warm_benchmark) is not bool:raise base.StopProbe('BENCHMARK_MODE_INVALID')
        self.request_limit=getattr(args,'max_loopback_requests',1024)
        if type(self.request_limit) is not int or not 1<=self.request_limit<=8192:
            raise base.StopProbe('LOOPBACK_REQUEST_BUDGET_INVALID')
        self.request_ledger=[]
        self.clients = {url:LoopbackClient(url) for url in (base.COMFY_URL,base.OLLAMA_URL)}

    def _json_request(self, url, *, payload=None, timeout=20):
        for endpoint,client in self.clients.items():
            if url.startswith(endpoint+'/'):
                if len(self.request_ledger)>=self.request_limit:raise base.StopProbe('LOOPBACK_REQUEST_BUDGET_EXCEEDED')
                entry={'endpoint':endpoint,'path':url[len(endpoint):],'status':None}
                self.request_ledger.append(entry)
                try:
                    status,value=client.request('POST' if payload is not None else 'GET',url[len(endpoint):],
                                                payload=payload,timeout=timeout)
                    entry['status']=status
                    return status,value
                except Exception as exc:
                    entry['error_type']=type(exc).__name__
                    raise
        raise base.StopProbe('NON_LOOPBACK_URL_FORBIDDEN')

    def _powershell(self, script):
        prefix = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference='Stop';"
        result = subprocess.run([self.args.powershell,'-NoProfile','-NonInteractive','-Command',prefix+script],
                                capture_output=True,timeout=60)
        if result.returncode:
            raise base.StopProbe('WINDOWS_PREFLIGHT_COMMAND_FAILED')
        return result.stdout.decode('utf-8-sig','strict').strip()

    def wait_json(self,url,timeout=60):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            remaining=deadline-time.monotonic()
            if remaining<=0:break
            try:return self._json_request(url,timeout=min(5,remaining))
            except (OSError,ControlError):time.sleep(min(.25,max(0,deadline-time.monotonic())))
        raise base.StopProbe('SERVICE_START_TIMEOUT')

    def submit(self, graph):
        if self.submissions >= self.max_public_submissions:
            raise base.StopProbe('PUBLIC_API_SUBMISSION_BUDGET_EXCEEDED')
        self.submissions += 1  # Failed submissions consume budget too.
        status,value=self._json_request(base.COMFY_URL+'/prompt',payload={'prompt':graph,'client_id':self.args.run_id})
        if status != 200 or not isinstance(value.get('prompt_id'),str) or not value['prompt_id']:
            raise base.StopProbe('PUBLIC_PROMPT_SUBMISSION_FAILED')
        return value['prompt_id']

    def start_comfy(self, directory, log_path):
        # Caller must finish candidate/target hash checks and child authorization
        # before invoking any lifecycle operation on this low-level adapter.
        win_main=self._windows_path(self.args.comfy_main,expected=base.AUTHORIZED_COMFY_MAIN)
        win_python=self._windows_path(self.args.comfy_python,expected=base.AUTHORIZED_COMFY_PYTHON)
        win_directory=self._windows_path(str(directory))
        wrapper=directory/'comfy-wrapper.ps1';pid_file=directory/'comfy-wrapper.pid'
        wrapper.write_text(comfy_wrapper(win_python,win_main,win_directory,self._windows_path(str(pid_file)),
            self._windows_path(self.args.ffmpeg_exe),self._windows_path(self.args.ffprobe_exe) if self.args.ffprobe_exe else None,
            warm=self.warm_benchmark),encoding='utf-8-sig')
        stream=log_path.open('w',encoding='utf-8')
        try:
            process=subprocess.Popen([self.args.powershell,'-NoProfile','-NonInteractive','-File',
                self._windows_path(str(wrapper))],stdout=stream,stderr=subprocess.STDOUT,text=True)
        except BaseException:
            stream.close()
            raise
        self.owned.append(('comfy',process,stream))
        self.wait_json(base.COMFY_URL+'/object_info',timeout=120)
        self._prove_listener_owned(8191,pid_file,'python.exe')
