"""Fresh Linux-local Chromium scratch lease; never adopt an existing profile."""
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile


def create(config, evidence_directory):
    base=Path('/tmp')
    if base.resolve(strict=True)!=base or not base.is_dir():raise ValueError('browser Linux temp base invalid')
    root=Path(tempfile.mkdtemp(prefix='lvw-s2-browser-',dir=base))
    info=root.lstat()
    lease={'root':str(root),'device':str(info.st_dev),'inode':str(info.st_ino),'uid':info.st_uid,
        **{key:config[key] for key in ('run_id','candidate_sha','authorization_sha256')},
        'stage_pass_claim':False}
    try:
        with (Path(evidence_directory)/'linux-temp-lease.json').open('x') as output:
            output.write(json.dumps(lease,sort_keys=True)+'\n');output.flush();os.fsync(output.fileno())
    except BaseException:
        # No caller/process has received this path; only an empty fresh root.
        root.rmdir()
        raise
    return root,lease


def remove(root, lease, *, independent_cleanup, node_terminal, callbacks_pending):
    root=Path(root)
    if (independent_cleanup.get('decision')!='BROWSER_CLEANUP_PROVEN'
            or node_terminal is not True or callbacks_pending!=0):raise ValueError('browser temp cleanup requires independent closure')
    if root.parent!=Path('/tmp') or not root.name.startswith('lvw-s2-browser-') or str(root)!=lease['root']:
        raise ValueError('browser temp lease path mismatch')
    info=root.lstat()
    if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or root.resolve(strict=True)!=root
            or (str(info.st_dev),str(info.st_ino),info.st_uid)!=(lease['device'],lease['inode'],lease['uid'])
            or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700
            or not shutil.rmtree.avoids_symlink_attacks):raise ValueError('browser temp identity/cleanup safety changed')
    # Linux fd-based rmtree unlinks child symlinks; it never traverses them.
    shutil.rmtree(root)
    return {'proven':not root.exists(),'device':lease['device'],'inode':lease['inode'],'stage_pass_claim':False}
