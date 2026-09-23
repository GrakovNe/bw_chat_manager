"""Atomic read and write of state files."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any


class CorruptStoreError(RuntimeError):
    """A state file is corrupted — there is nothing to parse."""


def write_text_atomic(path: Path, text: str) -> None:
    """Writes the file whole: a temporary file in the same directory + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


class JsonStore:
    """One JSON file on disk with a per-process write lock."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def load(self, default: Any) -> Any:
        with self._lock:
            return self._read(default)

    def save(self, data: Any) -> None:
        with self._lock:
            self._write(data)

    def mutate(self, default: Any, updater: Callable[[Any], Any]) -> Any:
        """Reads, changes and writes under a single lock.

        `updater` mutates the data in place or returns a whole new object.
        Returns the result of `updater`.
        """
        with self._lock:
            data = self._read(default)
            result = updater(data)
            self._write(data if result is None else result)
            return result

    def _read(self, default: Any) -> Any:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return default
        if not raw.strip():
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CorruptStoreError(f"Cannot parse {self._path}: {exc}") from exc

    def _write(self, data: Any) -> None:
        write_text_atomic(self._path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
