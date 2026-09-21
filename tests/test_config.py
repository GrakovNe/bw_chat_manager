"""Тесты загрузки конфигурации."""

from __future__ import annotations

import pytest

from bwbot.config import (
    DEFAULT_MIN_LENGTH,
    ConfigError,
    Settings,
)

BASE = {"TELEGRAM_TOKEN": "123:abc"}


def from_values(**overrides):
    return Settings.from_env({**BASE, **overrides})


def test_token_is_required():
    with pytest.raises(ConfigError, match="TELEGRAM_TOKEN"):
        Settings.from_env({})


@pytest.mark.parametrize("token", ["", "   "])
def test_blank_token_is_rejected(token):
    with pytest.raises(ConfigError):
        Settings.from_env({"TELEGRAM_TOKEN": token})


def test_defaults():
    settings = from_values()
    assert settings.min_length == DEFAULT_MIN_LENGTH
    assert settings.admin_ids == frozenset()
    assert settings.on_delete_reply
    assert settings.silent_usage_reply
    assert settings.log_level == "INFO"


def test_text_overrides():
    settings = from_values(ON_DELETE_REPLY="своё сообщение", LOG_LEVEL="debug")
    assert settings.on_delete_reply == "своё сообщение"
    assert settings.log_level == "DEBUG"


def test_empty_string_falls_back_to_default():
    assert from_values(ON_DELETE_REPLY="").on_delete_reply


def test_min_length_parsing():
    assert from_values(MIN_LENGTH="1").min_length == 1


@pytest.mark.parametrize("value", ["abc", "1.5", "-3", "0"])
def test_bad_min_length(value):
    with pytest.raises(ConfigError):
        from_values(MIN_LENGTH=value)


def test_admin_ids_parsing():
    assert from_values(ADMIN_IDS="1, 2,,3 ").admin_ids == frozenset({1, 2, 3})


def test_admin_ids_invalid():
    with pytest.raises(ConfigError, match="ADMIN_IDS"):
        from_values(ADMIN_IDS="1,abc")


def test_data_dir_and_paths(tmp_path):
    settings = from_values(DATA_DIR=str(tmp_path))
    assert settings.words_file == tmp_path / "bw_buildings.txt"
    assert settings.chat_settings_file == tmp_path / "chat_settings.json"


def test_data_dir_is_coerced_to_path(tmp_path):
    settings = Settings(token="1:1", data_dir=str(tmp_path))
    assert settings.data_dir == tmp_path
    assert settings.words_file == tmp_path / "bw_buildings.txt"


def test_is_admin():
    settings = from_values(ADMIN_IDS="7")
    assert settings.is_admin(7) is True
    assert settings.is_admin(8) is False
    assert settings.is_admin(None) is False
