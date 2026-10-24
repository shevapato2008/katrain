"""Private, content-addressed public OGS source files with cross-worker single flight."""

import fcntl
import hashlib
import os
from pathlib import Path
import re
import tempfile


def cached_source_zip(db, book, course):
    from katrain.web.tutorials.ogs_course import LICENSE_NOTICE, export_zip

    digest = course.content_sha256
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid OGS source digest")
    # Version the archive when notices/export format change, even if course content does not.
    revision = hashlib.sha256(("ogs-source-v1:" + LICENSE_NOTICE).encode()).hexdigest()[:16]
    root = Path(tempfile.gettempdir()) / f"katrain-ogs-source-{os.getuid()}"
    root.mkdir(mode=0o700, exist_ok=True)
    info = root.lstat()
    if root.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Unsafe OGS source cache directory")
    target = root / f"{digest}-{revision}.zip"
    # flock applies across threads (separate descriptors) and server worker processes.
    # One lock for every version also bounds cold-cache builds during course updates.
    with (root / "build.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if not target.is_file():
            fd, temporary = tempfile.mkstemp(prefix="building-", dir=root)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(export_zip(db, book, course))
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
    return target
