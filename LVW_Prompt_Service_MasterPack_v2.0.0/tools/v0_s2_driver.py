"""S2 lifecycle adapter; constructing it does not authorize or start services.

Reuse the recorded S1 process ownership/terminal checks without changing its
historical Harness. S2 replaces HTTP, localized PowerShell output handling,
submission accounting, and the transient decoder configuration.
"""
import importlib.util
from pathlib import Path
import subprocess

from tools.v0_s2_http import LoopbackClient

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / 'reports/v0-s1/wp-s1-03-phase-a/live_probe.py'
spec = importlib.util.spec_from_file_location('lvw_s2_lifecycle_base', LEGACY)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def comfy_wrapper(python, main, directory, pid_file, ffmpeg, ffprobe):
    # Process environment only, never user/machine environment or PATH writes.
    return (f"$env:LVW_FFMPEG_EXE={base.ps_quote(ffmpeg)}\n"
            f"$env:LVW_FFPROBE_EXE={base.ps_quote(ffprobe)}\n"
            + base.comfy_wrapper_text(python, main, directory, pid_file))


class S2SystemDriver(base.SystemDriver):
    def __init__(self, args, evidence):
        super().__init__(args,evidence)
        if type(args.max_public_submissions) is not int or not 1 <= args.max_public_submissions <= 64:
            raise base.StopProbe('PUBLIC_SUBMISSION_BUDGET_INVALID')
        self.max_public_submissions = args.max_public_submissions
        self.clients = {url:LoopbackClient(url) for url in (base.COMFY_URL,base.OLLAMA_URL)}

    def _json_request(self, url, *, payload=None, timeout=20):
        for endpoint,client in self.clients.items():
            if url.startswith(endpoint+'/'):
                return client.request('POST' if payload is not None else 'GET',url[len(endpoint):],
                                      payload=payload,timeout=timeout)
        raise base.StopProbe('NON_LOOPBACK_URL_FORBIDDEN')

    def _powershell(self, script):
        prefix = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference='Stop';"
        result = subprocess.run([self.args.powershell,'-NoProfile','-NonInteractive','-Command',prefix+script],
                                capture_output=True,timeout=60)
        if result.returncode:
            raise base.StopProbe('WINDOWS_PREFLIGHT_COMMAND_FAILED')
        return result.stdout.decode('utf-8-sig','strict').strip()

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
            self._windows_path(self.args.ffmpeg_exe),self._windows_path(self.args.ffprobe_exe)),encoding='utf-8')
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
