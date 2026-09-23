"""Wiring: building the Application, Deps.build and the entry point."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest
from telegram.ext import Application, CallbackQueryHandler

import bwbot.__main__ as entrypoint
from bwbot.app import build_application, on_error
from bwbot.config import ConfigError, Settings
from bwbot.deps import Deps
from conftest import ADMIN_ID

TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


@pytest.fixture
def app_settings(tmp_path) -> Settings:
    settings = Settings(
        token=TOKEN, min_length=10, admin_ids=frozenset({ADMIN_ID}), data_dir=tmp_path
    )
    settings.words_file.write_text("building\n", encoding="utf-8")
    return settings


def _handlers(app: Application) -> list[object]:
    return [handler for group in app.handlers.values() for handler in group]


def test_application_registers_every_kind_of_handler(app_settings):
    app = build_application(app_settings)
    kinds = {type(handler).__name__ for handler in _handlers(app)}
    assert {"CommandHandler", "MessageHandler", "CallbackQueryHandler"} <= kinds


def test_callback_handlers_are_filtered_by_prefix(app_settings):
    """Without prefixes both buttons would be handled by both handlers."""
    app = build_application(app_settings)
    patterns = sorted(
        handler.pattern.pattern
        for handler in _handlers(app)
        if isinstance(handler, CallbackQueryHandler)
    )
    assert patterns == ["^ban:", "^del:"]


def test_application_has_error_handler(app_settings):
    app = build_application(app_settings)
    assert app.error_handlers


async def test_error_handler_logs_the_failure(caplog):
    context = SimpleNamespace(error=RuntimeError("boom"))

    with caplog.at_level(logging.ERROR, logger="bwbot.app"):
        await on_error(object(), context)

    assert "Unhandled error" in caplog.text
    assert "boom" in caplog.text


def test_build_migrates_the_old_chat_settings_format(app_settings):
    app_settings.chat_settings_file.write_text('{"-1001": true}', encoding="utf-8")

    Deps.build(app_settings)

    document = json.loads(app_settings.chat_settings_file.read_text(encoding="utf-8"))
    assert document == {"-1001": {"silent": True}}


def test_build_survives_corrupt_chat_settings(app_settings):
    """A corrupt chat settings file must not bring the service down at startup."""
    app_settings.chat_settings_file.write_text("{ not json", encoding="utf-8")

    deps = Deps.build(app_settings)

    assert deps.chat_settings.is_silent(-1001) is False


def test_build_requires_the_words_file(tmp_path):
    settings = Settings(token=TOKEN, admin_ids=frozenset(), data_dir=tmp_path)
    with pytest.raises(ConfigError, match="No words file"):
        Deps.build(settings)


def test_build_forgets_posts_outside_the_window(app_settings):
    stale = {
        "-1001": {"200": [{"id": 1, "at": 1000.0, "text": "selling a garage in building 3"}]},
    }
    app_settings.recent_posts_file.write_text(json.dumps(stale), encoding="utf-8")

    Deps.build(app_settings)

    assert json.loads(app_settings.recent_posts_file.read_text(encoding="utf-8")) == {}


def test_configure_logging_keeps_the_token_out_of_http_logs():
    root = logging.getLogger()
    saved = {name: logging.getLogger(name).level for name in ("", *entrypoint.NOISY_LOGGERS)}
    try:
        entrypoint.configure_logging("DEBUG")
        assert root.level == logging.DEBUG
        assert all(
            logging.getLogger(name).level == logging.WARNING for name in entrypoint.NOISY_LOGGERS
        )
    finally:
        root.setLevel(saved[""])
        for name, level in saved.items():
            if name:
                logging.getLogger(name).setLevel(level)


def test_cli_exits_with_code_two_on_config_error(monkeypatch, capsys):
    def boom(environ=None):
        raise ConfigError("no token")

    monkeypatch.setattr(entrypoint, "main", boom)

    with pytest.raises(SystemExit) as exit_info:
        entrypoint.cli()

    assert exit_info.value.code == 2
    assert "no token" in capsys.readouterr().err


def _run_main(monkeypatch, tmp_path, *, words: str) -> dict:
    monkeypatch.setattr(entrypoint, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("TELEGRAM_TOKEN", TOKEN)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ADMIN_IDS", str(ADMIN_ID))
    (tmp_path / "bw_buildings.txt").write_text(words, encoding="utf-8")

    started: dict = {}
    monkeypatch.setattr(Application, "run_polling", lambda self, **kwargs: started.update(kwargs))
    entrypoint.main()
    return started


def test_main_starts_polling_with_every_update(monkeypatch, tmp_path):
    started = _run_main(monkeypatch, tmp_path, words="building\n")
    assert started.get("allowed_updates")


def test_main_warns_when_the_word_list_is_empty(monkeypatch, tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="bwbot"):
        _run_main(monkeypatch, tmp_path, words="")

    assert any("word list is empty" in record.message for record in caplog.records)
