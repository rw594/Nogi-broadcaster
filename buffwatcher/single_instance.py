from __future__ import annotations

import os
from pathlib import Path


class SingleInstance:
    def __init__(self, lock_path: str | Path) -> None:
        self.lock_path = Path(lock_path)
        self._file = None

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.lock_path.open("a+b")

        if os.name != "nt":
            return True

        import msvcrt

        try:
            self._file.seek(0)
            msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self._file.close()
            self._file = None
            return False
        return True

    def release(self) -> None:
        if self._file is None:
            return

        if os.name == "nt":
            import msvcrt

            try:
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass

        self._file.close()
        self._file = None
