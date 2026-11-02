"""Advisory single-writer lock on `project.lock` (ADR-021), on POSIX and Windows."""

import os
import sys
from pathlib import Path
from typing import IO

from comic_smith.errors import ProjectLockedError

# Windows locks a byte range, and a locked range cannot be read by other processes. Locking one
# byte far past the pid text keeps the pid readable for the error detail on every platform.
WINDOWS_LOCK_OFFSET = 1 << 20

if sys.platform == "win32":  # pragma: no cover - exercised on the Windows CI runners
    import msvcrt

    def _lock(fh: IO[str]) -> None:
        fh.seek(WINDOWS_LOCK_OFFSET)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(fh: IO[str]) -> None:
        fh.seek(WINDOWS_LOCK_OFFSET)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(fh: IO[str]) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(fh: IO[str]) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


class ProjectLock:
    """An exclusive, non-blocking OS lock held for the life of an open project.

    The OS releases `flock` and `msvcrt` locks when the process dies, so a crashed process never
    leaves a stale lock behind (unlike a pid file that must be probed for liveness).
    """

    def __init__(self, path: Path) -> None:
        """Remember the lock file location; nothing is locked until `acquire`."""
        self.path = path
        self._fh: IO[str] | None = None

    def acquire(self) -> None:
        """Take the lock or raise `ProjectLockedError` if another live process holds it."""
        fh = self.path.open("a+", encoding="utf-8")
        try:
            _lock(fh)
        except OSError as exc:
            holder = self._holder_pid(fh)
            fh.close()
            raise ProjectLockedError(
                "This project is open in another comic-smith process.",
                hint="Close the other window or command, or use the running Studio.",
                detail=f"lock file {self.path} held by pid {holder}",
            ) from exc
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        self._fh = fh

    @staticmethod
    def _holder_pid(fh: IO[str]) -> str:
        """Best-effort pid of the holder, for the error detail only."""
        try:
            fh.seek(0)
            return fh.read().strip() or "unknown"
        except OSError:  # pragma: no cover - defensive; the pid range is never locked
            return "unknown"

    def release(self) -> None:
        """Release the lock; safe to call twice."""
        if self._fh is not None:
            _unlock(self._fh)
            self._fh.close()
            self._fh = None
