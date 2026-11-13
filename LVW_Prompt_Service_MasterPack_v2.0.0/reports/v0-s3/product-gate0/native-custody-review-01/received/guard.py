"""The offline guard of the N1 native custody validation batch.

The guard is installed by ``runner.py`` **before** pytest, before any
plugin and before any import of a candidate module.  It is an audit hook,
so the refusal of an operating system event happens inside the event
itself and therefore *before* the action: a refusal of a process creation
is a proven position before the fork.

What the guard refuses is deliberately total.  Every event of the
``subprocess.`` family and of the ``socket.`` family is refused, not a
handful of named members of them.  The process and the socket families
are refused by their prefix, so a member that the interpreter adds later
is refused as well.  The named events of the process creation, of the
shell and of the database are refused by their exact name.  The original
budget ledger and the original shared counter may not be opened at all:
there is **no** exemption for them, no registry flag and no way to read
them from inside the guarded batch.

The self test of the guard uses ``sys.audit`` only.  It raises the events
that the guard refuses and it checks that the refusal happens.  It never
starts a process, it never opens a socket and it never touches a file, so
the self test proves the boundary of the hook and not the behaviour of
the operating system.
"""
import hashlib
import os
import sys
import time

GUARD_HANDSHAKE_EVENT = 'lvw.s3.native-custody.guard.handshake'

# The families that are refused as a whole.  A member that the interpreter
# adds later is refused by the same rule.
BLOCKED_EVENT_PREFIXES = ('subprocess.', 'socket.')

# The named events of the process creation, of the shell and of the
# database.
BLOCKED_EVENTS = (
    'os.system',
    'os.exec',
    'os.spawn',
    'os.posix_spawn',
    'os.fork',
    'os.forkpty',
    'sqlite3.connect',
)


class OfflineBoundaryViolation(RuntimeError):
    """Raised when the offline boundary would be crossed."""


class GuardInstallationError(RuntimeError):
    """The offline guard of this process is not proven active."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


class Guard:
    """The one, process wide owner of the offline guard.

    The guard has exactly one owner per process.  A second installation
    never installs a second hook: it proves again that the hook of this
    process is active and it returns the same owner.
    """

    def __init__(self):
        self.owner_id = None
        self.handshake_token = None
        self.forbidden_paths = ()
        self.hook_registered = False
        self.hook_installed = False
        self.hook_install_count = 0
        self.install_attempts = 0
        self.handshake_count = 0
        self.install_error = None
        self.refusals = []

    # -- the refusal of one event -----------------------------------------
    def refuse(self, event, arguments):
        """Refuse one event of the offline boundary."""
        detail = '%s %s' % (event, repr(arguments)[:200])
        self.refusals.append('OFFLINE_BOUNDARY:' + event)
        raise OfflineBoundaryViolation('offline boundary violation: ' + detail)

    def is_forbidden_path(self, path):
        """Whether a path is one of the paths that may not be opened."""
        try:
            value = os.fspath(path)
        except TypeError:
            return False
        if isinstance(value, bytes):
            value = value.decode('utf-8', 'replace')
        if not isinstance(value, str):
            return False
        for forbidden in self.forbidden_paths:
            if value == forbidden:
                return True
            try:
                if str(os.path.realpath(value)) == forbidden:
                    return True
            except (OSError, ValueError):
                continue
        return False

    def on_event(self, event, arguments):
        """The one audit hook of this process."""
        if event == GUARD_HANDSHAKE_EVENT:
            if (self.owner_id and len(arguments) == 2
                    and arguments[0] == self.owner_id
                    and arguments[1] == self.handshake_token):
                self.handshake_count += 1
            return
        if event == 'open':
            path = arguments[0] if arguments else None
            if self.is_forbidden_path(path):
                self.refuse('open:' + str(path), arguments)
            return
        if event.startswith(BLOCKED_EVENT_PREFIXES) or event in BLOCKED_EVENTS:
            self.refuse(event, arguments)


def _registry():
    """The registry of this process.  It is created once and then shared."""
    registry = sys.modules.get('lvw_s3_native_custody_guard_registry')
    if registry is None:
        registry = Guard()
        sys.modules['lvw_s3_native_custody_guard_registry'] = registry
    return registry


def install(forbidden_paths=()):
    """Install the offline guard of this process, exactly once.

    The installation is only promised after a handshake proved that the
    hook of this process is really active: ``sys.addaudithook`` can raise
    and the interpreter can also suppress a new hook silently when an
    existing policy hook raises on the ``sys.addaudithook`` event.
    """
    registry = _registry()
    registry.install_attempts += 1
    if registry.hook_registered:
        if not confirm_active():
            registry.hook_installed = False
            registry.install_error = 'GUARD_HANDSHAKE_FAILED'
            raise GuardInstallationError('GUARD_HANDSHAKE_FAILED')
        registry.hook_installed = True
        if registry.hook_install_count == 0:
            registry.hook_install_count = 1
        return registry.owner_id
    registry.forbidden_paths = tuple(str(item) for item in forbidden_paths)
    registry.owner_id = 'owner-' + hashlib.sha256(
        ('%s|%s|%s' % (os.getpid(), time.time(), registry.forbidden_paths))
        .encode('utf-8')).hexdigest()[:32]
    registry.handshake_token = hashlib.sha256(
        ('%s|%s' % (registry.owner_id, registry.handshake_token or '')).encode('utf-8')
    ).hexdigest()[:32]
    registry.hook_registered = True
    try:
        sys.addaudithook(registry.on_event)
    except Exception as error:  # noqa: BLE001 - the refusal is the guard
        registry.owner_id = None
        registry.hook_installed = False
        registry.install_error = 'GUARD_REGISTRATION_FAILED:' + type(error).__name__
        raise GuardInstallationError('GUARD_REGISTRATION_FAILED', str(error)) from error
    if not confirm_active():
        registry.hook_installed = False
        registry.install_error = 'GUARD_HANDSHAKE_FAILED'
        raise GuardInstallationError('GUARD_HANDSHAKE_FAILED')
    registry.hook_installed = True
    registry.hook_install_count += 1
    return registry.owner_id


def confirm_active():
    """Prove that the audit hook of this process is really active.

    The handshake is side effect free: it raises one audit event that only
    the hook of this registration answers, and it carries the owner and
    the token of the registration, so the answer of another owner is
    never counted.
    """
    registry = _registry()
    if registry.owner_id is None:
        return False
    before = registry.handshake_count
    try:
        sys.audit(GUARD_HANDSHAKE_EVENT, registry.owner_id, registry.handshake_token)
    except Exception:  # noqa: BLE001 - a failed handshake proves nothing
        return False
    return registry.handshake_count > before


def selftest():
    """Prove the boundary of the hook with ``sys.audit`` only.

    The self test raises the events that the guard refuses and it checks
    that every one of them is refused.  It never starts a process, it
    never opens a socket and it never touches a file.
    """
    registry = _registry()
    results = {}
    probes = [
        ('subprocess.Popen', ('/bin/true',)),
        ('socket.bind', ('127.0.0.1', 0)),
        ('socket.connect', ('127.0.0.1', 9)),
        ('os.system', ('true',)),
        ('os.exec', ('/bin/true',)),
        ('os.spawn', ('/bin/true',)),
        ('os.posix_spawn', ('/bin/true',)),
        ('os.fork', ()),
        ('sqlite3.connect', (':memory:',)),
    ]
    for path in registry.forbidden_paths:
        probes.append(('open', (path, 'rb', os.O_RDONLY)))
    for event, arguments in probes:
        try:
            sys.audit(event, *arguments)
        except OfflineBoundaryViolation:
            results[event] = 'REFUSED'
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            results[event] = 'OTHER:' + type(error).__name__
        else:
            results[event] = 'NOT_BLOCKED'
    return results


def state():
    """The recorded state of the guard of this process."""
    registry = _registry()
    return {
        'owner_id': registry.owner_id,
        'hook_registered': registry.hook_registered,
        'hook_installed': registry.hook_installed,
        'hook_install_count': registry.hook_install_count,
        'install_attempts': registry.install_attempts,
        'handshake_event': GUARD_HANDSHAKE_EVENT,
        'handshake_confirmed': registry.handshake_count > 0,
        'handshake_count': registry.handshake_count,
        'blocked_event_prefixes': list(BLOCKED_EVENT_PREFIXES),
        'blocked_events': list(BLOCKED_EVENTS),
        'forbidden_paths': list(registry.forbidden_paths),
        'refusals': list(registry.refusals),
        'install_error': registry.install_error,
    }
