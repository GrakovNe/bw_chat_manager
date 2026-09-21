"""Тесты репозиториев и атомарной записи."""

from __future__ import annotations

import pytest

from bwbot.storage.chat_settings import ChatSettingsRepository
from bwbot.storage.json_store import CorruptStoreError, JsonStore
from bwbot.storage.words import WordRepository


class TestWordRepository:
    def test_add_and_read_back(self, words_repo: WordRepository):
        assert words_repo.add("Корпус 1") is True
        assert words_repo.all() == frozenset({"корпус 1"})

    def test_add_is_idempotent(self, words_repo: WordRepository):
        assert words_repo.add("двор") is True
        assert words_repo.add("ДВОР") is False
        assert words_repo.all() == frozenset({"двор"})

    @pytest.mark.parametrize("word", ["", "   ", "\t"])
    def test_blank_word_is_rejected(self, words_repo: WordRepository, word: str):
        assert words_repo.add(word) is False
        assert words_repo.all() == frozenset()

    def test_remove_existing(self, words_repo: WordRepository):
        words_repo.add("двор")
        assert words_repo.remove("Двор") is True
        assert words_repo.all() == frozenset()

    def test_remove_missing(self, words_repo: WordRepository):
        assert words_repo.remove("нет такого") is False

    def test_blank_lines_are_skipped_on_read(self, tmp_path):
        path = tmp_path / "words.txt"
        path.write_text("\n  Корпус2  \n\n\n", encoding="utf-8")
        assert WordRepository(path).all() == frozenset({"корпус2"})

    def test_missing_file_reads_as_empty(self, tmp_path):
        assert WordRepository(tmp_path / "absent.txt").all() == frozenset()

    def test_state_survives_new_instance_and_is_sorted(self, words_repo: WordRepository):
        words_repo.add("б")
        words_repo.add("а")
        lines = words_repo.path.read_text(encoding="utf-8").splitlines()
        assert lines == ["а", "б"]
        assert WordRepository(words_repo.path).all() == frozenset({"а", "б"})


class TestChatSettingsRepository:
    def test_default_is_not_silent(self, chat_settings_repo: ChatSettingsRepository):
        assert chat_settings_repo.is_silent(-100) is False

    def test_set_and_get(self, chat_settings_repo: ChatSettingsRepository):
        chat_settings_repo.set_silent(-100, True)
        assert chat_settings_repo.is_silent(-100) is True
        chat_settings_repo.set_silent(-100, False)
        assert chat_settings_repo.is_silent(-100) is False

    def test_chats_are_isolated(self, chat_settings_repo: ChatSettingsRepository):
        chat_settings_repo.set_silent(-100, True)
        assert chat_settings_repo.is_silent(-200) is False

    def test_persists_across_instances(self, chat_settings_repo: ChatSettingsRepository):
        chat_settings_repo.set_silent(-100, True)
        assert ChatSettingsRepository(chat_settings_repo.path).is_silent(-100) is True

    def test_corrupted_entry_degrades_to_defaults(self, chat_settings_repo: ChatSettingsRepository):
        chat_settings_repo.path.write_text('{"-100": "не словарь"}', encoding="utf-8")
        assert chat_settings_repo.is_silent(-100) is False


class TestJsonStore:
    def test_missing_file_returns_default(self, tmp_path):
        assert JsonStore(tmp_path / "absent.json").load({"a": 1}) == {"a": 1}

    def test_empty_file_returns_default(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("   ", encoding="utf-8")
        assert JsonStore(path).load([]) == []

    def test_broken_json_raises(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(CorruptStoreError):
            JsonStore(path).load({})

    def test_no_temp_files_left_after_write(self, tmp_path):
        store = JsonStore(tmp_path / "state.json")
        store.save({"x": 1})
        store.save({"x": 2})
        assert [p.name for p in tmp_path.iterdir()] == ["state.json"]

    def test_mutate_writes_under_one_lock(self, tmp_path):
        store = JsonStore(tmp_path / "state.json")

        def updater(data):
            data["count"] = data.get("count", 0) + 1

        store.mutate({}, updater)
        store.mutate({}, updater)
        assert store.load({}) == {"count": 2}
