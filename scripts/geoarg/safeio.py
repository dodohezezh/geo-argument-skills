"""Small filesystem helpers shared by the audit and grounding writers.

Two guarantees matter for the audit trail. First, a record must never be left
half-written: `atomic_write_text` writes a temporary sibling and renames it
into place, so a crash keeps the old file or the new one. Second, two processes
must not interleave a commit on the same case: `case_lock` is an advisory
inter-process lock held for the whole write.

Readers do not take the lock. Atomic renames make a concurrent read safe
enough for the registry, report, and ledger.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class LockError(Exception):
    """Raised when a case directory is already locked by another process."""


def atomic_write_text(path: str | Path, text: str, encoding: str = "utf-8") -> Path:
    """Write `text` next to `path` and rename it into place."""
    target = Path(path)
    if target.exists() and target.is_dir():
        raise OSError(f"cannot write file: target is a directory: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        with temp.open("w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        try:
            temp.unlink()
        except OSError:
            pass
    return target


def _lock(handle) -> None:  # type: ignore[no-untyped-def]
    if os.name == "nt":  # pragma: no cover - exercised on Windows
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:  # pragma: no cover - exercised on POSIX
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle) -> None:  # type: ignore[no-untyped-def]
    try:
        if os.name == "nt":  # pragma: no cover - exercised on Windows
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:  # pragma: no cover - exercised on POSIX
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def case_lock(root: str | Path, timeout: float = 15.0) -> Iterator[None]:
    """Hold an advisory lock for one case directory.

    The lock file lives under `.geoarg/`; it is created on first use and never
    deleted (the OS lock, not the file, is the mutex). Raises `LockError` when
    another process holds it past `timeout` seconds.
    """
    lock_path = Path(root) / ".geoarg" / ".lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    acquired = False
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                _lock(handle)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise LockError(
                        f"case is busy: another geoarg process holds {lock_path}"
                    ) from None
                time.sleep(0.05)
        yield
    finally:
        if acquired:
            _unlock(handle)
        handle.close()
