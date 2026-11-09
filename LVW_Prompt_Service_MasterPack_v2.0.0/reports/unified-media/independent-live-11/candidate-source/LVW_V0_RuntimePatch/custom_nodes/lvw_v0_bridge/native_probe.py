"""Trusted native metadata adapter and existing-binary discovery; no download."""
import importlib.util
from pathlib import Path

from .video_process import run_bounded


class NativeAvProbe:
    backend_name='pyav-probe'

    def __init__(self,python,*,runner=run_bounded):
        self.python=str(python)
        self.script=str(Path(__file__).with_name('_native_av_probe.py'))
        self.runner=runner

    def __call__(self,path,*,cancel=None):
        return self.runner([self.python,'-I','-B',self.script,str(path)],
                           timeout_seconds=15,output_limit=256*1024,cancel=cancel)


def module_available(name):
    try:return importlib.util.find_spec(name) is not None
    except (ImportError,ValueError):return False


def bundled_ffmpeg():
    try:spec=importlib.util.find_spec('imageio_ffmpeg')
    except (ImportError,ValueError):return None
    if spec is None or not spec.origin:return None
    directory=Path(spec.origin).parent/'binaries'
    files=sorted(path for path in directory.glob('ffmpeg*.exe') if path.is_file() and not path.is_symlink())
    return str(files[0]) if len(files)==1 else None
