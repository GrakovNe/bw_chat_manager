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


def test_literal_newline_is_unescaped():
    settings = from_values(ON_DELETE_REPLY="раз\\n\\nдва")
    assert settings.on_delete_reply == "раз\n\nдва"


def test_real_newline_survives():
    assert from_values(ON_DELETE_REPLY="раз\nдва").on_delete_reply == "раз\nдва"


def test_crlf_and_tab_are_unescaped():
    assert from_values(SILENT_ON_REPLY="а\\r\\nб\\tc").silent_on_reply == "а\nб\tc"


def test_unescaping_keeps_cyrillic():
    settings = from_values(NOT_ADMIN_REPLY="Только админам\\n@maxgrakov")
    assert settings.not_admin_reply == "Только админам\n@maxgrakov"


def test_every_text_setting_is_unescaped():
    settings = from_values(BAN_DONE_REPLY="готово\\n!", BAN_FAILED_REPLY="не вышло:\\nпричина")
    assert settings.ban_done_reply == "готово\n!"
    assert settings.ban_failed_reply == "не вышло:\nпричина"
