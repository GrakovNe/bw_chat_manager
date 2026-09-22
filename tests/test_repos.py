"""Тесты репозиториев и атомарной записи."""

from __future__ import annotations

import json
import os

import pytest

from bwbot.dedupe import normalize
from bwbot.storage.chat_settings import ChatSettingsRepository
from bwbot.storage.json_store import CorruptStoreError, JsonStore
from bwbot.storage.recent_posts import RecentPostsRepository
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

    def test_flat_true_from_old_version_keeps_silent_mode(self, chat_settings_repo):
        chat_settings_repo.path.write_text('{"-100": true}', encoding="utf-8")
        assert chat_settings_repo.is_silent(-100) is True

    def test_flat_false_from_old_version(self, chat_settings_repo):
        chat_settings_repo.path.write_text('{"-100": false}', encoding="utf-8")
        assert chat_settings_repo.is_silent(-100) is False

    def test_set_silent_keeps_other_flat_entries(self, chat_settings_repo):
        chat_settings_repo.path.write_text('{"-100": true, "-200": false}', encoding="utf-8")
        chat_settings_repo.set_silent(-200, True)
        assert chat_settings_repo.is_silent(-100) is True
        assert chat_settings_repo.is_silent(-200) is True
        assert chat_settings_repo.is_silent(-300) is False

    def test_migrate_rewrites_old_format(self, chat_settings_repo):
        chat_settings_repo.path.write_text('{"-100": true, "-200": false}', encoding="utf-8")
        assert chat_settings_repo.migrate() == 2
        assert json.loads(chat_settings_repo.path.read_text(encoding="utf-8")) == {
            "-100": {"silent": True},
            "-200": {"silent": False},
        }

    def test_migrate_is_noop_on_new_format(self, chat_settings_repo):
        chat_settings_repo.set_silent(-100, True)
        assert chat_settings_repo.migrate() == 0

    def test_non_dict_root_is_tolerated(self, chat_settings_repo):
        chat_settings_repo.path.write_text("[]", encoding="utf-8")
        assert chat_settings_repo.is_silent(-100) is False
        chat_settings_repo.set_silent(-100, True)
        assert chat_settings_repo.is_silent(-100) is True

    def test_migrate_on_non_dict_root_changes_nothing(self, chat_settings_repo):
        chat_settings_repo.path.write_text("[1, 2, 3]", encoding="utf-8")
        assert chat_settings_repo.migrate() == 0


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

    def test_mutate_can_replace_whole_document(self, tmp_path):
        store = JsonStore(tmp_path / "state.json")
        store.save(["старый формат, а не словарь"])
        store.mutate({}, lambda data: {"fixed": True})
        assert store.load({}) == {"fixed": True}


CHAT = -1001
AUTHOR = 777
NOW = 1_700_000_000.0
DAY = 86400


@pytest.fixture
def posts_repo(tmp_path) -> RecentPostsRepository:
    return RecentPostsRepository(tmp_path / "recent_posts.json", window_days=7)


class TestRecentPostsRepository:
    def test_record_and_read_back(self, posts_repo: RecentPostsRepository):
        posts_repo.record(CHAT, AUTHOR, 5, "Продам Гараж!!!", at=NOW)

        stored = posts_repo.posts(CHAT, AUTHOR)
        assert [(post.message_id, post.text) for post in stored] == [
            (5, normalize("Продам Гараж!!!"))
        ]
        assert stored[0].posted_at == NOW

    def test_unknown_author_or_chat_is_empty(self, posts_repo: RecentPostsRepository):
        posts_repo.record(CHAT, AUTHOR, 5, "продам гараж", at=NOW)

        assert posts_repo.posts(CHAT, 555) == []
        assert posts_repo.posts(-2002, AUTHOR) == []

    def test_authors_are_isolated(self, posts_repo: RecentPostsRepository):
        posts_repo.record(CHAT, AUTHOR, 5, "продам гараж", at=NOW)
        posts_repo.record(CHAT, 555, 6, "продам гараж", at=NOW)

        assert [post.message_id for post in posts_repo.posts(CHAT, AUTHOR)] == [5]
        assert [post.message_id for post in posts_repo.posts(CHAT, 555)] == [6]

    def test_noise_only_text_is_not_stored(self, posts_repo: RecentPostsRepository):
        posts_repo.record(CHAT, AUTHOR, 5, "!!! 🔥", at=NOW)

        assert posts_repo.posts(CHAT, AUTHOR) == []
        assert posts_repo.path.exists() is False

    def test_only_newest_entries_are_kept(self, posts_repo: RecentPostsRepository):
        tiny = RecentPostsRepository(posts_repo.path, window_days=7, max_entries=3)
        for index in range(6):
            tiny.record(CHAT, AUTHOR, index, f"продам гараж {index}", at=NOW + index)

        assert [post.message_id for post in tiny.posts(CHAT, AUTHOR)] == [3, 4, 5]

    def test_write_drops_entries_outside_the_window(self, posts_repo: RecentPostsRepository):
        posts_repo.record(CHAT, AUTHOR, 1, "старый гараж", at=NOW - 30 * DAY)
        posts_repo.record(CHAT, AUTHOR, 2, "новый гараж", at=NOW)

        assert [post.message_id for post in posts_repo.posts(CHAT, AUTHOR)] == [2]

    def test_prune_removes_and_counts(self, tmp_path):
        path = tmp_path / "recent_posts.json"
        path.write_text(
            json.dumps(
                {
                    str(CHAT): {
                        str(AUTHOR): [
                            {"id": 1, "at": NOW - 30 * DAY, "text": "старый гараж"},
                            {"id": 2, "at": NOW, "text": "свежий гараж"},
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        repo = RecentPostsRepository(path, window_days=7)

        assert repo.prune(now=NOW) == 1
        assert [post.message_id for post in repo.posts(CHAT, AUTHOR)] == [2]

    def test_prune_drops_empty_chats(self, posts_repo: RecentPostsRepository):
        posts_repo.record(CHAT, AUTHOR, 1, "старый гараж", at=NOW - 30 * DAY)

        assert posts_repo.prune(now=NOW) == 1
        assert json.loads(posts_repo.path.read_text(encoding="utf-8")) == {}

    def test_document_shape_is_stable(self, posts_repo: RecentPostsRepository):
        posts_repo.record(CHAT, AUTHOR, 5, "продам гараж", at=NOW)

        assert json.loads(posts_repo.path.read_text(encoding="utf-8")) == {
            str(CHAT): {str(AUTHOR): [{"id": 5, "at": NOW, "text": "продам гараж"}]}
        }

    @pytest.mark.parametrize(
        "entry",
        [
            None,
            "текст",
            {},
            {"id": 1, "at": NOW},
            {"id": 1, "text": "гараж"},
            {"id": "1", "at": NOW, "text": "гараж"},
            {"id": True, "at": NOW, "text": "гараж"},
            {"id": 1, "at": "вчера", "text": "гараж"},
            {"id": 1, "at": NOW, "text": "   "},
        ],
    )
    def test_broken_entry_is_skipped(self, tmp_path, entry):
        path = tmp_path / "recent_posts.json"
        path.write_text(
            json.dumps({str(CHAT): {str(AUTHOR): [entry, {"id": 9, "at": NOW, "text": "гараж"}]}}),
            encoding="utf-8",
        )
        repo = RecentPostsRepository(path, window_days=7)

        assert [post.message_id for post in repo.posts(CHAT, AUTHOR)] == [9]

    @pytest.mark.parametrize(
        "document",
        ["не словарь", [1, 2], {str(CHAT): "не словарь"}, {str(CHAT): {str(AUTHOR): "не список"}}],
    )
    def test_broken_document_is_empty(self, tmp_path, document):
        path = tmp_path / "recent_posts.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        repo = RecentPostsRepository(path, window_days=7)

        assert repo.posts(CHAT, AUTHOR) == []

    def test_corrupt_file_does_not_break_reads(self, tmp_path):
        path = tmp_path / "recent_posts.json"
        path.write_text("{ оборвано", encoding="utf-8")
        repo = RecentPostsRepository(path, window_days=7)

        assert repo.posts(CHAT, AUTHOR) == []

    def test_corrupt_file_is_overwritten_by_next_record(self, tmp_path):
        path = tmp_path / "recent_posts.json"
        path.write_text("{ оборвано", encoding="utf-8")
        repo = RecentPostsRepository(path, window_days=7)

        repo.record(CHAT, AUTHOR, 5, "продам гараж", at=NOW)

        assert [post.message_id for post in repo.posts(CHAT, AUTHOR)] == [5]


class TestAtomicWriteFailure:
    def test_failed_write_leaves_no_temp_files(self, tmp_path, monkeypatch):
        store = JsonStore(tmp_path / "state.json")

        def boom(src, dst):
            raise OSError("диск закончился")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError):
            store.save({"a": 1})

        assert not list(tmp_path.glob("*.tmp"))
        assert not (tmp_path / "state.json").exists()
