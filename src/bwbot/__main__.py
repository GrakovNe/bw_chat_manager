"""Entry point: `python -m bwbot` or `bwbot`."""

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
    # basicConfig stays silent if handlers are already attached (e.g. by a test
    # plugin), so we set the level explicitly: LOG_LEVEL must be applied.
    logging.getLogger().setLevel(verbosity)
    # httpx logs every request with the full URL, which contains the bot token.
    # The token must never appear in the systemd journal.
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
            "The word list is empty: any message longer than %s characters will be deleted",
            settings.min_length,
        )
    logger.info(
        "Startup: data_dir=%s, words=%s, administrators=%s",
        settings.data_dir,
        words_count,
        len(settings.admin_ids),
    )

    build_application(settings, deps).run_polling(allowed_updates=Update.ALL_TYPES)


def cli() -> None:
    try:
        main()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    cli()
