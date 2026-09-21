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

WORDS_FILENAME = "bw_buildings.txt"
CHAT_SETTINGS_FILENAME = "chat_settings.json"


class ConfigError(RuntimeError):
    """Конфигурация некорректна или не может быть загружена."""


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
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_dir", Path(self.data_dir))

    @property
    def words_file(self) -> Path:
        return self.data_dir / WORDS_FILENAME

    @property
    def chat_settings_file(self) -> Path:
        return self.data_dir / CHAT_SETTINGS_FILENAME

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
            on_delete_reply=env.get("ON_DELETE_REPLY") or DEFAULT_ON_DELETE_REPLY,
            silent_on_reply=env.get("SILENT_ON_REPLY") or DEFAULT_SILENT_ON_REPLY,
            silent_off_reply=env.get("SILENT_OFF_REPLY") or DEFAULT_SILENT_OFF_REPLY,
            silent_usage_reply=env.get("SILENT_USAGE_REPLY") or DEFAULT_SILENT_USAGE_REPLY,
            not_admin_reply=env.get("NOT_ADMIN_REPLY") or DEFAULT_NOT_ADMIN_REPLY,
            log_level=(env.get("LOG_LEVEL") or "INFO").upper(),
        )


def _parse_int_list(raw: str) -> list[int]:
    values = [part.strip() for part in raw.split(",")]
    return [int(part) for part in values if part]
