"""Per-generation compiler/control directory, independent of shared app data."""
from pathlib import Path
import os
import stat
import tempfile


def windows_acl_preamble(path: str) -> str:
    quoted = "'" + path.replace("'", "''") + "'"
    return (
        "$privateRoot=" + quoted + ";if([IO.Directory]::Exists($privateRoot)){throw 'PRIVATE_ROOT_EXISTS'};"
        "$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User;"
        "$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18');"
        "$acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetOwner($sid);$acl.SetAccessRuleProtection($true,$false);"
        "foreach($who in @($sid,$system)){$rule=[Security.AccessControl.FileSystemAccessRule]::new($who,'FullControl','ContainerInherit,ObjectInherit','None','Allow');$acl.AddAccessRule($rule)};"
        "[void][IO.Directory]::CreateDirectory($privateRoot,$acl);"
        "if(([IO.File]::GetAttributes($privateRoot) -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'PRIVATE_ROOT_ALIAS'};"
        "$check=[IO.Directory]::GetAccessControl($privateRoot);"
        "if(!$check.AreAccessRulesProtected -or $check.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $sid.Value){throw 'PRIVATE_ROOT_OWNER'};"
        "foreach($rule in $check.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){"
        "if($rule.AccessControlType -ne 'Allow' -or $rule.IdentityReference.Value -notin @($sid.Value,$system.Value)){throw 'PRIVATE_ROOT_ACL'}};"
    )


def create_root(token: str, windows):
    parent = Path(tempfile.gettempdir())
    mapped_parent = windows(parent)
    if os.name != 'nt' and mapped_parent.lower().startswith('\\\\wsl.'):
        # mkdtemp creates 0700 atomically; do not chmod a shared application tree.
        root = Path(tempfile.mkdtemp(prefix='lvw-native-' + token + '-', dir=parent))
        value = root.lstat()
        if (root.resolve() != root or not stat.S_ISDIR(value.st_mode)
                or value.st_uid != os.geteuid() or value.st_mode & 0o077):
            raise ValueError('PRIVATE_ROOT_UNPROVEN')
        return root, ''
    # NTFS permissions cannot be inferred from a POSIX chmod. The native wrapper
    # creates the new random leaf with a protected owner/SYSTEM DACL before any
    # control, log or compiler file is written. Existing leaves are refused.
    root = parent / ('lvw-native-' + token)
    return root, windows_acl_preamble(windows(root))
