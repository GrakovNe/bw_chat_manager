"""Configuration loading tests."""

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
    settings = from_values(ON_DELETE_REPLY="custom message", LOG_LEVEL="debug")
    assert settings.on_delete_reply == "custom message"
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
    settings = from_values(ON_DELETE_REPLY="one\\n\\ntwo")
    assert settings.on_delete_reply == "one\n\ntwo"


def test_real_newline_survives():
    assert from_values(ON_DELETE_REPLY="one\ntwo").on_delete_reply == "one\ntwo"


def test_crlf_and_tab_are_unescaped():
    assert from_values(SILENT_ON_REPLY="a\\r\\nb\\tc").silent_on_reply == "a\nb\tc"


def test_unescaping_keeps_text():
    settings = from_values(NOT_ADMIN_REPLY="Admins only\\n@maxgrakov")
    assert settings.not_admin_reply == "Admins only\n@maxgrakov"


def test_every_text_setting_is_unescaped():
    settings = from_values(BAN_DONE_REPLY="done\\n!", BAN_FAILED_REPLY="failed:\\nreason")
    assert settings.ban_done_reply == "done\n!"
    assert settings.ban_failed_reply == "failed:\nreason"


def test_dup_defaults():
    settings = from_values()
    assert settings.dup_window_days == 7
    assert 0 < settings.dup_threshold <= 1
    assert settings.dup_delete_label == "Delete"
    assert settings.dup_report.format(
        chat_id=-1, user_label="vasya", text="garage", matched_age="yesterday", score=100
    )


def test_dup_overrides():
    settings = from_values(DUP_WINDOW_DAYS="30", DUP_THRESHOLD="0.75")
    assert settings.dup_window_days == 30
    assert settings.dup_threshold == 0.75


@pytest.mark.parametrize("value", ["0", "-1", "abc", "   x"])
def test_bad_dup_window(value):
    with pytest.raises(ConfigError, match="DUP_WINDOW_DAYS"):
        from_values(DUP_WINDOW_DAYS=value)


@pytest.mark.parametrize("value", ["0", "-0.5", "1.5", "abc"])
def test_bad_dup_threshold(value):
    with pytest.raises(ConfigError, match="DUP_THRESHOLD"):
        from_values(DUP_THRESHOLD=value)


@pytest.mark.parametrize("template", ["{unknown}", "{}", "{1}", "{chat_id!x}"])
def test_bad_dup_report_template_is_rejected_on_startup(template):
    with pytest.raises(ConfigError, match="DUP_REPORT"):
        from_values(DUP_REPORT=template)


def test_bad_delete_note_template_is_rejected():
    with pytest.raises(ConfigError, match="DUP_DELETE_DONE_NOTE"):
        from_values(DUP_DELETE_DONE_NOTE="{who}")


def test_dup_report_keeps_line_breaks():
    settings = from_values(DUP_REPORT="dup\\n{score}%")
    assert settings.dup_report == "dup\n{score}%"


def test_recent_posts_file_lives_in_data_dir(tmp_path):
    settings = Settings.from_env({"TELEGRAM_TOKEN": "1:a", "DATA_DIR": str(tmp_path)})
    assert settings.recent_posts_file == tmp_path / "recent_posts.json"
    assert settings.recent_posts_file != settings.chat_settings_file


@pytest.mark.parametrize("value", ["verbose", "debu", "TRACE"])
def test_unknown_log_level_is_rejected(value):
    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        from_values(LOG_LEVEL=value)


def test_log_level_is_case_insensitive():
    assert from_values(LOG_LEVEL="warning").log_level == "WARNING"
