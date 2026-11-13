"""The bounded, safe input and output helpers of the S3 production controller.

This module is a *private* helper of the controller and of the quality
worker.  It is not a general file platform: it offers exactly the four
operations that the production composition needs and nothing else.

1. A bounded read of one *explicit entry* file.  The file is opened with
   ``O_NOFOLLOW`` and ``O_NONBLOCK``, the type of the opened object is
   decided by its ``fstat`` and not by a pre-check of the path, and the
   bytes are read through that very handle.  The read is bounded *before*
   the bytes are taken: at most ``limit + 1`` bytes are ever requested
   from the kernel, so an oversized file is refused without being read
   into the memory of the process.
2. A bounded read of one *root relative* reference.  Every component of
   the reference is opened from the descriptor of its own parent with
   ``O_NOFOLLOW``, so an ancestor that is a link is refused as well and
   not only a link on the artifact itself.  The final component is opened
   with ``O_NONBLOCK`` as well, so a special file can never block the
   opening.
3. The creation of one directory chain inside a bound root.  Every
   component is opened or created relative to the descriptor of its own
   parent, so a link in the chain is never followed and the created
   directories are always inside the root.
4. The exclusive write of one leaf file.  The leaf is created with
   ``O_CREAT | O_EXCL``, so an existing file is never replaced, and the
   write is relative to the descriptor of the directory that was
   verified.

Every refusal of this module has a stable, machine readable code.  A
platform without the safe primitives fails closed: the caller refuses the
run instead of silently reading the file the unsafe way.
"""
import errno
import hashlib
import os
import stat

# The bound of one read.  The phase and the controller never read a file
# that is larger than this, and the bound is applied to the bytes that
# are really taken from the kernel.
MAX_BOUNDED_BYTES = 8 * 1024 * 1024

# The size of one read request.  The bound is applied to the sum of the
# requests, not to the size of the file.
READ_CHUNK_BYTES = 64 * 1024

# The modes of the artefacts of the controller.  They are private to the
# run root.
DIRECTORY_MODE = 0o700
FILE_MODE = 0o600

# The stable refusal codes of this module.
FILE_UNREADABLE = 'FILE_UNREADABLE'
FILE_NOT_A_REGULAR_FILE = 'FILE_NOT_A_REGULAR_FILE'
FILE_TOO_LARGE = 'FILE_TOO_LARGE'
FILE_CHANGED_DURING_READ = 'FILE_CHANGED_DURING_READ'
REFERENCE_INVALID = 'REFERENCE_INVALID'
ROOT_UNAVAILABLE = 'ROOT_UNAVAILABLE'
ROOT_NOT_A_DIRECTORY = 'ROOT_NOT_A_DIRECTORY'
DIRECTORY_UNUSABLE = 'DIRECTORY_UNUSABLE'
DIRECTORY_UNCREATABLE = 'DIRECTORY_UNCREATABLE'
ANCESTOR_NOT_A_DIRECTORY = 'ANCESTOR_NOT_A_DIRECTORY'
OUTPUT_ALREADY_EXISTS = 'OUTPUT_ALREADY_EXISTS'
OUTPUT_UNWRITABLE = 'OUTPUT_UNWRITABLE'
SAFE_OPEN_UNSUPPORTED = 'SAFE_OPEN_UNSUPPORTED'
ROOT_REDIRECTED = 'ROOT_REDIRECTED'
ANCHOR_REDIRECTED = 'ANCHOR_REDIRECTED'
DIRECTORY_IDENTITY_CHANGED = 'DIRECTORY_IDENTITY_CHANGED'


class ControllerIOError(RuntimeError):
    """A refused bounded input or output with a stable code."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def errno_name(error):
    """The stable name of one operating system error."""
    return errno.errorcode.get(getattr(error, 'errno', None), 'OSERROR')


def safe_open_supported():
    """Whether this platform has every primitive the safe read needs.

    The check is a real capability check and not a promise: the flags
    themselves are handed to the kernel by the opening of the root, and a
    kernel that refuses them turns into a refusal of the run.
    """
    if not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        return False
    if not hasattr(os, 'O_NONBLOCK') or not isinstance(os.O_NONBLOCK, int):
        return False
    return os.open in getattr(os, 'supports_dir_fd', ())


def directory_open_flags():
    """The flags of one safe opening of a directory component."""
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK


def final_open_flags():
    """The flags of one safe opening of the final component.

    The final component is not opened with ``O_DIRECTORY``: it may be a
    regular file, and the type of whatever it is has to be decided by the
    ``fstat`` of the opened handle.  ``O_NONBLOCK`` keeps a special file
    from blocking this opening.
    """
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def reference_parts(relative):
    """The components of one root relative reference."""
    if not isinstance(relative, str) or not relative:
        raise ControllerIOError(REFERENCE_INVALID)
    pure = os.path.normpath(relative)
    if os.path.isabs(pure) or pure == '..' or pure.startswith('..' + os.sep):
        raise ControllerIOError(REFERENCE_INVALID)
    parts = [part for part in pure.split(os.sep) if part not in ('', '.')]
    if not parts:
        raise ControllerIOError(REFERENCE_INVALID)
    return parts


def _read_bounded_handle(descriptor, limit):
    """Read at most ``limit + 1`` bytes from one verified handle.

    The size of the object is only a *hint* here: the bound is applied to
    the bytes that are really requested from the kernel, so an object
    that lies about its size can not make the process read more than the
    bound either.  The handle is verified again after the read, so a
    file that changed while it was read is refused.
    """
    try:
        before = os.fstat(descriptor)
    except OSError as error:
        raise ControllerIOError(FILE_UNREADABLE, errno_name(error)) from error
    if not stat.S_ISREG(before.st_mode):
        # A fifo, a device, a socket or a directory is never read as a
        # file, and the type is decided by the opened handle.
        raise ControllerIOError(FILE_NOT_A_REGULAR_FILE)
    if before.st_size > limit:
        raise ControllerIOError(FILE_TOO_LARGE)
    chunks = []
    total = 0
    while True:
        wanted = min(READ_CHUNK_BYTES, limit + 1 - total)
        if wanted <= 0:
            raise ControllerIOError(FILE_TOO_LARGE)
        try:
            block = os.read(descriptor, wanted)
        except OSError as error:
            raise ControllerIOError(FILE_UNREADABLE, errno_name(error)) from error
        if not block:
            break
        total += len(block)
        chunks.append(block)
        if total > limit:
            raise ControllerIOError(FILE_TOO_LARGE)
    try:
        after = os.fstat(descriptor)
    except OSError as error:
        raise ControllerIOError(FILE_UNREADABLE, errno_name(error)) from error
    if (int(after.st_dev), int(after.st_ino)) != (int(before.st_dev), int(before.st_ino)) \
            or int(after.st_size) != int(before.st_size) \
            or int(after.st_ctime_ns) != int(before.st_ctime_ns) \
            or int(after.st_mtime_ns) != int(before.st_mtime_ns) \
            or total != int(before.st_size):
        raise ControllerIOError(FILE_CHANGED_DURING_READ)
    return b''.join(chunks)


def read_bounded_regular(path, limit=MAX_BOUNDED_BYTES):
    """Read one explicit entry file with a real bound.

    The path is an explicit entry point of a trusted local caller.  The
    final component is still opened without following a link, the type of
    the opened object is decided by its ``fstat`` and the bytes are read
    through that very handle.
    """
    if not safe_open_supported():
        raise ControllerIOError(SAFE_OPEN_UNSUPPORTED)
    try:
        descriptor = os.open(str(path), final_open_flags())
    except OSError as error:
        raise ControllerIOError(FILE_UNREADABLE, errno_name(error)) from error
    try:
        return _read_bounded_handle(descriptor, limit)
    finally:
        os.close(descriptor)


def open_root_directory(path):
    """Open the bound root and verify that it is a directory.

    The root is opened without following a link, so a root that became a
    link is refused here and not walked.
    """
    if not safe_open_supported():
        raise ControllerIOError(SAFE_OPEN_UNSUPPORTED)
    try:
        descriptor = os.open(str(path), directory_open_flags())
    except OSError as error:
        raise ControllerIOError(ROOT_UNAVAILABLE, errno_name(error)) from error
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISDIR(info.st_mode):
            raise ControllerIOError(ROOT_NOT_A_DIRECTORY)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def open_root_directory_chain(path):
    """Open the bound root from the file system root, level by level.

    Every level is opened from the descriptor of its own parent with
    ``O_NOFOLLOW``, so an ancestor of the root that is a link is refused
    here and is never walked.  The chain of the observed identities is
    returned together with the descriptor, so a later replacement of the
    root or of one of its ancestors is detected by
    :func:`verify_directory_chain` and never adopted.

    The descriptor of the root is owned by the caller.
    """
    if not safe_open_supported():
        raise ControllerIOError(SAFE_OPEN_UNSUPPORTED)
    literal = os.path.normpath(str(path))
    if not os.path.isabs(literal):
        raise ControllerIOError(ROOT_UNAVAILABLE, 'NOT_ABSOLUTE')
    parts = [part for part in literal.split(os.sep) if part not in ('', '.')]
    directory = os.open(os.sep, directory_open_flags())
    chain = []
    try:
        info = os.fstat(directory)
        chain.append({'path': os.sep,
                      'device': int(info.st_dev),
                      'inode': int(info.st_ino)})
        walked = os.sep
        for part in parts:
            try:
                child = os.open(part, directory_open_flags(), dir_fd=directory)
            except OSError as error:
                if error.errno == errno.ELOOP:
                    raise ControllerIOError(ROOT_REDIRECTED, part) from error
                raise ControllerIOError(ROOT_UNAVAILABLE, errno_name(error)) from error
            try:
                info = os.fstat(child)
                if not stat.S_ISDIR(info.st_mode):
                    raise ControllerIOError(ROOT_NOT_A_DIRECTORY)
            except BaseException:
                os.close(child)
                raise
            os.close(directory)
            directory = child
            walked = os.path.join(walked, part)
            chain.append({'path': walked,
                          'device': int(info.st_dev),
                          'inode': int(info.st_ino)})
        return directory, tuple(chain)
    except BaseException:
        os.close(directory)
        raise


def verify_directory_chain(chain):
    """Verify that every level of a chain still names the same object.

    The verification is a no-follow ``lstat`` of every level of the chain.
    A level that was replaced by a link, by another directory or by another
    file is refused: the descriptor that was opened earlier is never
    adopted as the new object and the replaced level is never written to.
    """
    for entry in chain:
        try:
            info = os.lstat(entry['path'])
        except OSError as error:
            raise ControllerIOError(DIRECTORY_IDENTITY_CHANGED,
                                    errno_name(error)) from error
        if not stat.S_ISDIR(info.st_mode):
            raise ControllerIOError(DIRECTORY_IDENTITY_CHANGED, 'NOT_A_DIRECTORY')
        if int(info.st_dev) != entry['device'] or int(info.st_ino) != entry['inode']:
            raise ControllerIOError(DIRECTORY_IDENTITY_CHANGED, 'IDENTITY')
    return True


def verify_directory_identity(path, identity):
    """Verify that one directory still names the object that was observed.

    The verification is a no-follow ``lstat``: a directory that was
    replaced by a link or by another object is refused.
    """
    try:
        info = os.lstat(str(path))
    except OSError as error:
        raise ControllerIOError(DIRECTORY_IDENTITY_CHANGED,
                                errno_name(error)) from error
    if not stat.S_ISDIR(info.st_mode):
        raise ControllerIOError(DIRECTORY_IDENTITY_CHANGED, 'NOT_A_DIRECTORY')
    if (int(info.st_dev), int(info.st_ino)) != (int(identity[0]), int(identity[1])):
        raise ControllerIOError(DIRECTORY_IDENTITY_CHANGED, 'IDENTITY')
    return True


def open_read_only_directory(path):
    """Open one declared read-only anchor directory.

    The anchor itself is never a link and the observed identity is
    returned with the descriptor, so a later replacement of the anchor is
    detected by :func:`verify_directory_identity`.  The descriptor is
    owned by the caller.
    """
    if not safe_open_supported():
        raise ControllerIOError(SAFE_OPEN_UNSUPPORTED)
    try:
        descriptor = os.open(str(path), directory_open_flags())
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ControllerIOError(ANCHOR_REDIRECTED, errno_name(error)) from error
        raise ControllerIOError(DIRECTORY_UNUSABLE, errno_name(error)) from error
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISDIR(info.st_mode):
            raise ControllerIOError(DIRECTORY_UNUSABLE, 'NOT_A_DIRECTORY')
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, (int(info.st_dev), int(info.st_ino))


def open_child_directory(parent_descriptor, name):
    """Open one directory level relative to the descriptor of its parent.

    The level is opened without following a link, so a level that became a
    link is refused instead of being walked.  The descriptor is owned by
    the caller.
    """
    try:
        child = os.open(name, directory_open_flags(), dir_fd=parent_descriptor)
    except OSError as error:
        raise ControllerIOError(DIRECTORY_UNUSABLE, errno_name(error)) from error
    try:
        info = os.fstat(child)
        if not stat.S_ISDIR(info.st_mode):
            raise ControllerIOError(ANCESTOR_NOT_A_DIRECTORY)
    except BaseException:
        os.close(child)
        raise
    return child


def read_bounded_at(directory_descriptor, name, limit=MAX_BOUNDED_BYTES):
    """Read one leaf of a verified directory, relative to its descriptor.

    The leaf is opened without following a link and without blocking, the
    type of the opened object is decided by its ``fstat`` and the bytes are
    read through that very handle with a real bound.
    """
    try:
        descriptor = os.open(name, final_open_flags(), dir_fd=directory_descriptor)
    except OSError as error:
        raise ControllerIOError(FILE_UNREADABLE, errno_name(error)) from error
    try:
        return _read_bounded_handle(descriptor, limit)
    finally:
        os.close(descriptor)


def open_directory_chain(root_descriptor, parts):
    """Walk the components of a directory chain from the bound root.

    Every component is opened from the descriptor of its own parent with
    ``O_NOFOLLOW``.  A component that is a link is therefore refused:
    the chain is never walked through a link.  The returned descriptor is
    owned by the caller.
    """
    directory = os.dup(root_descriptor)
    try:
        for part in parts:
            try:
                child = os.open(part, directory_open_flags(), dir_fd=directory)
            except OSError as error:
                raise ControllerIOError(DIRECTORY_UNUSABLE,
                                        errno_name(error)) from error
            try:
                info = os.fstat(child)
            except OSError as error:
                os.close(child)
                raise ControllerIOError(DIRECTORY_UNUSABLE,
                                        errno_name(error)) from error
            if not stat.S_ISDIR(info.st_mode):
                os.close(child)
                raise ControllerIOError(ANCESTOR_NOT_A_DIRECTORY)
            os.close(directory)
            directory = child
        return directory
    except BaseException:
        os.close(directory)
        raise


def ensure_directory_chain(root_descriptor, parts):
    """Walk the components of a directory chain and create the missing ones.

    The creation is relative to the descriptor of the own parent, so a
    link in the chain is never followed and the created directories are
    always inside the bound root.  The returned descriptor is owned by
    the caller.
    """
    directory = os.dup(root_descriptor)
    try:
        for part in parts:
            try:
                child = os.open(part, directory_open_flags(), dir_fd=directory)
            except FileNotFoundError:
                try:
                    os.mkdir(part, DIRECTORY_MODE, dir_fd=directory)
                except FileExistsError:
                    pass
                except OSError as error:
                    raise ControllerIOError(DIRECTORY_UNCREATABLE,
                                            errno_name(error)) from error
                try:
                    child = os.open(part, directory_open_flags(), dir_fd=directory)
                except OSError as error:
                    raise ControllerIOError(DIRECTORY_UNUSABLE,
                                            errno_name(error)) from error
            except OSError as error:
                raise ControllerIOError(DIRECTORY_UNUSABLE,
                                        errno_name(error)) from error
            try:
                info = os.fstat(child)
            except OSError as error:
                os.close(child)
                raise ControllerIOError(DIRECTORY_UNUSABLE,
                                        errno_name(error)) from error
            if not stat.S_ISDIR(info.st_mode):
                os.close(child)
                raise ControllerIOError(ANCESTOR_NOT_A_DIRECTORY)
            os.close(directory)
            directory = child
        return directory
    except BaseException:
        os.close(directory)
        raise


def read_bounded_in_root(root, relative, limit=MAX_BOUNDED_BYTES):
    """Read one root relative reference through the bound root.

    Every ancestor of the reference is opened from the descriptor of its
    own parent with ``O_NOFOLLOW`` and the final component is opened
    with ``O_NOFOLLOW`` and ``O_NONBLOCK``.  A reference that leaves the
    root, an ancestor that is a link and a special file are all refused.
    """
    parts = reference_parts(relative)
    root_descriptor = open_root_directory(root)
    try:
        directory = open_directory_chain(root_descriptor, parts[:-1])
    finally:
        os.close(root_descriptor)
    try:
        try:
            descriptor = os.open(parts[-1], final_open_flags(), dir_fd=directory)
        except OSError as error:
            raise ControllerIOError(FILE_UNREADABLE, errno_name(error)) from error
    finally:
        os.close(directory)
    try:
        return _read_bounded_handle(descriptor, limit)
    finally:
        os.close(descriptor)


def read_bounded_in_root_at(root_descriptor, relative, limit=MAX_BOUNDED_BYTES):
    """Read one root relative reference through the bound root descriptor.

    The reference is walked from the descriptor of the bound root, so
    every ancestor of it is opened without following a link and the bytes
    are read through the handle of the leaf that was verified.  The root
    is the object that the caller bound: it is never opened again by its
    path here.
    """
    parts = reference_parts(relative)
    directory = open_directory_chain(root_descriptor, parts[:-1])
    try:
        try:
            descriptor = os.open(parts[-1], final_open_flags(), dir_fd=directory)
        except OSError as error:
            raise ControllerIOError(FILE_UNREADABLE, errno_name(error)) from error
    finally:
        os.close(directory)
    try:
        return _read_bounded_handle(descriptor, limit)
    finally:
        os.close(descriptor)


def write_exclusive_at(directory_descriptor, name, raw):
    """Write one leaf file exactly once inside a verified directory.

    The leaf is created with ``O_CREAT | O_EXCL``, so an existing file is
    never replaced, and the write is relative to the descriptor of the
    directory that was verified.  A partial write is not removed: the
    evidence of a failed write stays where it is.
    """
    try:
        descriptor = os.open(name,
                              os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                              FILE_MODE,
                              dir_fd=directory_descriptor)
    except FileExistsError as error:
        raise ControllerIOError(OUTPUT_ALREADY_EXISTS) from error
    except OSError as error:
        raise ControllerIOError(OUTPUT_UNWRITABLE, errno_name(error)) from error
    try:
        written = 0
        while written < len(raw):
            written += os.write(descriptor, raw[written:])
        os.fsync(descriptor)
    except OSError as error:
        raise ControllerIOError(OUTPUT_UNWRITABLE, errno_name(error)) from error
    finally:
        os.close(descriptor)


def write_exclusive_path(path, raw):
    """Write one explicit output file exactly once.

    This is the output of an explicit entry point of a trusted local
    caller.  The file is never replaced.
    """
    try:
        descriptor = os.open(str(path),
                              os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                              FILE_MODE)
    except FileExistsError as error:
        raise ControllerIOError(OUTPUT_ALREADY_EXISTS) from error
    except OSError as error:
        raise ControllerIOError(OUTPUT_UNWRITABLE, errno_name(error)) from error
    try:
        written = 0
        while written < len(raw):
            written += os.write(descriptor, raw[written:])
        os.fsync(descriptor)
    except OSError as error:
        raise ControllerIOError(OUTPUT_UNWRITABLE, errno_name(error)) from error
    finally:
        os.close(descriptor)


def exists_at(directory_descriptor, name):
    """Whether one leaf exists in a verified directory.

    The check never follows a link and it never opens the leaf, so it can
    not block on a special file.
    """
    try:
        os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError:
        return False
    return True
