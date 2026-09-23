"""Loading settings from environment variables."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MIN_LENGTH = 10
DEFAULT_DATA_DIR = Path("data")

DEFAULT_ON_DELETE_REPLY = (
    "The message was deleted because it does not mention a BW building or courtyard\n\n"
    "If you believe your message was deleted by mistake - write to @maxgrakov"
)
DEFAULT_SILENT_ON_REPLY = "Silent mode is on. The bot will not send deletion messages."
DEFAULT_SILENT_OFF_REPLY = "Silent mode is off. The bot will send deletion messages."
DEFAULT_SILENT_USAGE_REPLY = "Usage: /silent on | /silent off"
DEFAULT_NOT_ADMIN_REPLY = "This command is available to administrators only."
DEFAULT_BAN_BUTTON_LABEL = "BAN"
DEFAULT_BAN_DONE_REPLY = "Banned and removed from the chat."
DEFAULT_BAN_FAILED_REPLY = "Could not ban:"
DEFAULT_BAN_ADMIN_REPLY = "Administrators are not banned."
DEFAULT_BAN_BROKEN_REPLY = "I don't understand this button — it is outdated."
DEFAULT_DUP_WINDOW_DAYS = 7
DEFAULT_DUP_THRESHOLD = 0.9
DEFAULT_DUP_REPORT = (
    "Suspected repeat in chat {chat_id} from {user_label}: {text}\n"
    "Looks like their own message {matched_age} — {score}% match."
)
DEFAULT_DUP_DELETE_LABEL = "Delete"
DEFAULT_DUP_DELETED_REPLY = "Message deleted."
DEFAULT_DUP_DELETE_FAILED_REPLY = "Could not delete:"
DEFAULT_DUP_DELETE_DONE_NOTE = "🗑 Deleted by administrator {by}"
DEFAULT_DUP_BROKEN_REPLY = "I don't understand this button — it is outdated."

WORDS_FILENAME = "bw_buildings.txt"
CHAT_SETTINGS_FILENAME = "chat_settings.json"
RECENT_POSTS_FILENAME = "recent_posts.json"


LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class ConfigError(RuntimeError):
    """The configuration is incorrect or cannot be loaded."""


# Substitutions available in the repeat report template.
DUP_REPORT_FIELDS = frozenset({"chat_id", "user_label", "text", "matched_age", "score"})
# Substitutions in the note appended under a report after an admin action.
NOTE_FIELDS = frozenset({"by"})


@dataclass(frozen=True)
class Settings:
    token: str
    min_length: int = DEFAULT_MIN_LENGTH
    admin_ids: frozenset[int] = field(default_factory=frozenset)
    data_dir: Path = DEFAULT_DATA_DIR
    on_delete_reply: str = DEFAULT_ON_DELETE_REPLY
    silent_on_reply: str = DEFAULT_SILENT_ON_REPLY
    silent_off_reply: str = DEFAULT_SILENT_OFF_REPLY
    silent_usage_reply: str = DEFAULT_SILENT_USAGE_REPLY
    not_admin_reply: str = DEFAULT_NOT_ADMIN_REPLY
    ban_button_label: str = DEFAULT_BAN_BUTTON_LABEL
    ban_done_reply: str = DEFAULT_BAN_DONE_REPLY
    ban_failed_reply: str = DEFAULT_BAN_FAILED_REPLY
    ban_admin_reply: str = DEFAULT_BAN_ADMIN_REPLY
    ban_broken_reply: str = DEFAULT_BAN_BROKEN_REPLY
    dup_window_days: int = DEFAULT_DUP_WINDOW_DAYS
    dup_threshold: float = DEFAULT_DUP_THRESHOLD
    dup_report: str = DEFAULT_DUP_REPORT
    dup_delete_label: str = DEFAULT_DUP_DELETE_LABEL
    dup_deleted_reply: str = DEFAULT_DUP_DELETED_REPLY
    dup_delete_failed_reply: str = DEFAULT_DUP_DELETE_FAILED_REPLY
    dup_delete_done_note: str = DEFAULT_DUP_DELETE_DONE_NOTE
    dup_broken_reply: str = DEFAULT_DUP_BROKEN_REPLY
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_dir", Path(self.data_dir))

    @property
    def words_file(self) -> Path:
        return self.data_dir / WORDS_FILENAME

    @property
    def chat_settings_file(self) -> Path:
        return self.data_dir / CHAT_SETTINGS_FILENAME

    @property
    def recent_posts_file(self) -> Path:
        return self.data_dir / RECENT_POSTS_FILENAME

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admin_ids

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if environ is None else environ

        token = env.get("TELEGRAM_TOKEN", "").strip()
        if not token:
            raise ConfigError("TELEGRAM_TOKEN is not set. Copy .env.example to .env.")

        min_length = _positive_int(env, "MIN_LENGTH", DEFAULT_MIN_LENGTH)

        try:
            admin_ids = frozenset(_parse_int_list(env.get("ADMIN_IDS", "")))
        except ValueError as exc:
            raise ConfigError(f"ADMIN_IDS must be a comma-separated list of ids: {exc}") from exc

        return cls(
            token=token,
            min_length=min_length,
            admin_ids=admin_ids,
            data_dir=Path(env.get("DATA_DIR") or DEFAULT_DATA_DIR),
            on_delete_reply=_text(env, "ON_DELETE_REPLY", DEFAULT_ON_DELETE_REPLY),
            silent_on_reply=_text(env, "SILENT_ON_REPLY", DEFAULT_SILENT_ON_REPLY),
            silent_off_reply=_text(env, "SILENT_OFF_REPLY", DEFAULT_SILENT_OFF_REPLY),
            silent_usage_reply=_text(env, "SILENT_USAGE_REPLY", DEFAULT_SILENT_USAGE_REPLY),
            not_admin_reply=_text(env, "NOT_ADMIN_REPLY", DEFAULT_NOT_ADMIN_REPLY),
            ban_button_label=_text(env, "BAN_BUTTON_LABEL", DEFAULT_BAN_BUTTON_LABEL),
            ban_done_reply=_text(env, "BAN_DONE_REPLY", DEFAULT_BAN_DONE_REPLY),
            ban_failed_reply=_text(env, "BAN_FAILED_REPLY", DEFAULT_BAN_FAILED_REPLY),
            ban_admin_reply=_text(env, "BAN_ADMIN_REPLY", DEFAULT_BAN_ADMIN_REPLY),
            ban_broken_reply=_text(env, "BAN_BROKEN_REPLY", DEFAULT_BAN_BROKEN_REPLY),
            dup_window_days=_positive_int(env, "DUP_WINDOW_DAYS", DEFAULT_DUP_WINDOW_DAYS),
            dup_threshold=_ratio(env, "DUP_THRESHOLD", DEFAULT_DUP_THRESHOLD),
            dup_report=_template(env, "DUP_REPORT", DEFAULT_DUP_REPORT, DUP_REPORT_FIELDS),
            dup_delete_label=_text(env, "DUP_DELETE_LABEL", DEFAULT_DUP_DELETE_LABEL),
            dup_deleted_reply=_text(env, "DUP_DELETED_REPLY", DEFAULT_DUP_DELETED_REPLY),
            dup_delete_failed_reply=_text(
                env, "DUP_DELETE_FAILED_REPLY", DEFAULT_DUP_DELETE_FAILED_REPLY
            ),
            dup_delete_done_note=_template(
                env, "DUP_DELETE_DONE_NOTE", DEFAULT_DUP_DELETE_DONE_NOTE, NOTE_FIELDS
            ),
            dup_broken_reply=_text(env, "DUP_BROKEN_REPLY", DEFAULT_DUP_BROKEN_REPLY),
            log_level=_log_level(env),
        )


def _log_level(env: Mapping[str, str]) -> str:
    raw = (env.get("LOG_LEVEL") or "INFO").upper()
    if raw not in LOG_LEVELS:
        names = ", ".join(sorted(LOG_LEVELS))
        raise ConfigError(f"LOG_LEVEL must be one of: {names}, got {raw!r}")
    return raw


def _parse_number(
    env: Mapping[str, str],
    key: str,
    default: int | float,
    *,
    cast: Callable[[str], int] | Callable[[str], float],
    hint: str,
) -> int | float:
    """A number from the environment: empty — default, junk — ConfigError with a hint."""
    raw = (env.get(key) or "").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be {hint}: {raw!r}") from exc


def _positive_int(env: Mapping[str, str], key: str, default: int) -> int:
    value = _parse_number(env, key, default, cast=int, hint="a number")
    if value < 1:
        raise ConfigError(f"{key} must be >= 1, got {value}")
    return int(value)


def _ratio(env: Mapping[str, str], key: str, default: float) -> float:
    value = _parse_number(env, key, default, cast=float, hint="a number from 0 to 1")
    if not 0 < value <= 1:
        raise ConfigError(f"{key} must be in the interval (0, 1], got {value}")
    return value


def _template(env: Mapping[str, str], key: str, default: str, fields: frozenset[str]) -> str:
    """Text with substitutions: validated right away so we don't crash on the first report."""
    raw = _text(env, key, default)
    try:
        raw.format(**dict.fromkeys(fields))
    except (IndexError, KeyError, ValueError) as exc:
        names = ", ".join(sorted(fields))
        raise ConfigError(f"{key} does not build from substitutions: {names}: {exc}") from exc
    return raw


def _text(env: Mapping[str, str], key: str, default: str) -> str:
    r"""A text setting: line breaks in the environment arrive as literals.

    `.env` and systemd `EnvironmentFile` cannot hold multiline values, so
    administrators write `\n` by hand — we expand them back into real line
    breaks.
    """
    raw = env.get(key) or default
    return raw.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")


def _parse_int_list(raw: str) -> list[int]:
    values = [part.strip() for part in raw.split(",")]
    return [int(part) for part in values if part]
