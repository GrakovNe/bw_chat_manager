"""Загрузка настроек из переменных окружения."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MIN_LENGTH = 10
DEFAULT_DATA_DIR = Path("data")

DEFAULT_ON_DELETE_REPLY = (
    "Сообщение удалено, поскольку в нем нет указания дома или двора BW\n\n"
    "Если вы считаете, что ваше сообщение удалили зря - напишите @maxgrakov"
)
DEFAULT_SILENT_ON_REPLY = "Тихий режим включён. Бот не будет отправлять сообщения об удалении."
DEFAULT_SILENT_OFF_REPLY = "Тихий режим выключен. Бот будет отправлять сообщения об удалении."
DEFAULT_SILENT_USAGE_REPLY = "Использование: /silent on | /silent off"
DEFAULT_NOT_ADMIN_REPLY = "Эта команда доступна только администраторам."
DEFAULT_BAN_BUTTON_LABEL = "BAN"
DEFAULT_BAN_DONE_REPLY = "Забанен и удалён из чата."
DEFAULT_BAN_FAILED_REPLY = "Не удалось забанить:"
DEFAULT_BAN_ADMIN_REPLY = "Администратора не банят."
DEFAULT_BAN_BROKEN_REPLY = "Не понимаю эту кнопку — она устарела."
DEFAULT_DUP_WINDOW_DAYS = 7
DEFAULT_DUP_THRESHOLD = 0.9
DEFAULT_DUP_REPORT = (
    "Подозрение на повтор в чате {chat_id} от {user_label}: {text}\n"
    "Похоже на его же сообщение {matched_age} — совпадение {score}%."
)
DEFAULT_DUP_DELETE_LABEL = "Удалить"
DEFAULT_DUP_DELETED_REPLY = "Сообщение удалено."
DEFAULT_DUP_DELETE_FAILED_REPLY = "Не удалось удалить:"
DEFAULT_DUP_DELETE_DONE_NOTE = "🗑 Удалено администратором {by}"
DEFAULT_DUP_BROKEN_REPLY = "Не понимаю эту кнопку — она устарела."

WORDS_FILENAME = "bw_buildings.txt"
CHAT_SETTINGS_FILENAME = "chat_settings.json"
RECENT_POSTS_FILENAME = "recent_posts.json"


class ConfigError(RuntimeError):
    """Конфигурация некорректна или не может быть загружена."""


# Подстановки, доступные в шаблоне отчёта о повторе.
DUP_REPORT_FIELDS = frozenset({"chat_id", "user_label", "text", "matched_age", "score"})
# Подстановки в пометке, которая дописывается под отчёт после действия админа.
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
            raise ConfigError("TELEGRAM_TOKEN не задан. Скопируйте .env.example в .env.")

        try:
            min_length = int(env.get("MIN_LENGTH", "") or DEFAULT_MIN_LENGTH)
        except ValueError as exc:
            raise ConfigError(f"MIN_LENGTH должен быть числом: {env['MIN_LENGTH']!r}") from exc
        if min_length < 1:
            raise ConfigError(f"MIN_LENGTH должен быть >= 1, получено {min_length}")

        try:
            admin_ids = frozenset(_parse_int_list(env.get("ADMIN_IDS", "")))
        except ValueError as exc:
            raise ConfigError(f"ADMIN_IDS должен быть списком id через запятую: {exc}") from exc

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
            log_level=(env.get("LOG_LEVEL") or "INFO").upper(),
        )


def _positive_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key) or ""
    try:
        value = int(raw) if raw.strip() else default
    except ValueError as exc:
        raise ConfigError(f"{key} должен быть числом: {raw!r}") from exc
    if value < 1:
        raise ConfigError(f"{key} должен быть >= 1, получено {value}")
    return value


def _ratio(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key) or ""
    try:
        value = float(raw) if raw.strip() else default
    except ValueError as exc:
        raise ConfigError(f"{key} должен быть числом от 0 до 1: {raw!r}") from exc
    if not 0 < value <= 1:
        raise ConfigError(f"{key} должен быть в интервале (0, 1], получено {value}")
    return value


def _template(env: Mapping[str, str], key: str, default: str, fields: frozenset[str]) -> str:
    """Текст с подстановками: проверяем сразу, чтобы не падать при первом отчёте."""
    raw = _text(env, key, default)
    try:
        raw.format(**dict.fromkeys(fields))
    except (IndexError, KeyError, ValueError) as exc:
        names = ", ".join(sorted(fields))
        raise ConfigError(f"{key} не собирается из подстановок: {names}: {exc}") from exc
    return raw


def _text(env: Mapping[str, str], key: str, default: str) -> str:
    r"""Текст настройки: переносы строк в окружении приходят литеральными.

    `.env` и `EnvironmentFile` systemd не умеют многострочные значения, поэтому
    администраторы пишут `\n` руками — разворачиваем их обратно в настоящие
    переносы.
    """
    raw = env.get(key) or default
    return raw.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")


def _parse_int_list(raw: str) -> list[int]:
    values = [part.strip() for part in raw.split(",")]
    return [int(part) for part in values if part]
