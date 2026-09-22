"""Точка входа: `python -m bwbot` или `bwbot`."""

from __future__ import annotations

import collections.abc
import logging
import sys

from dotenv import load_dotenv
from telegram import Update

from bwbot.app import build_application
from bwbot.config import ConfigError, Settings
from bwbot.deps import Deps

logger = logging.getLogger("bwbot")


NOISY_LOGGERS = ("httpx", "httpcore")


def configure_logging(level: str) -> None:
    verbosity = getattr(logging, level, logging.INFO)
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        level=verbosity,
        stream=sys.stdout,
    )
    # basicConfig молчит, если хендлеры уже навешаны (например, тестовым
    # плагинем), поэтому уровень задаём явно: LOG_LEVEL обязан применяться.
    logging.getLogger().setLevel(verbosity)
    # httpx пишет каждое обращение полным URL, а в нём токен бота. В журнале
    # systemd токен появления быть не должен.
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def main(environ: collections.abc.Mapping[str, str] | None = None) -> None:
    load_dotenv()
    settings = Settings.from_env(environ)
    configure_logging(settings.log_level)

    deps = Deps.build(settings)
    words_count = len(deps.words.all())
    if words_count == 0:
        logger.warning(
            "Список слов пуст: будет удаляться любое сообщение длиннее %s символов",
            settings.min_length,
        )
    logger.info(
        "Старт: data_dir=%s, слов=%s, администраторов=%s",
        settings.data_dir,
        words_count,
        len(settings.admin_ids),
    )

    build_application(settings, deps).run_polling(allowed_updates=Update.ALL_TYPES)


def cli() -> None:
    try:
        main()
    except ConfigError as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    cli()
