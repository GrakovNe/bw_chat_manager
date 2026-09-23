"""Outcome of an administrator action: a ban or a delete via a button."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionResult:
    """ok — whether it worked; message — what to show the administrator who clicked."""

    ok: bool
    message: str
