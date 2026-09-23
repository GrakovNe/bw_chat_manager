"""Исход админского действия: бан или удаление по кнопке."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionResult:
    """ok — удалось ли; message — что показать нажавшему администратору."""

    ok: bool
    message: str
