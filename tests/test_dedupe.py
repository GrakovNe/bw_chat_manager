"""Метрика похожести и окно повторов."""

from __future__ import annotations

import pytest

from bwbot.dedupe import StoredPost, find_repeat, normalize, similarity

NOW = 1_700_000_000.0
DAY = 86400


def stored(text: str, *, message_id: int = 1, at: float = NOW - DAY) -> StoredPost:
    return StoredPost(message_id=message_id, posted_at=at, text=normalize(text))


class TestNormalize:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Продам Гараж", "продам гараж"),
            ("  продам    гараж\n", "продам гараж"),
            ("продам гараж!!!", "продам гараж"),
            ("продам гараж 🔥🔥", "продам гараж"),
            ("Продам\tгараж", "продам гараж"),
        ],
    )
    def test_noise_is_stripped(self, raw: str, expected: str) -> None:
        assert normalize(raw) == expected

    def test_digits_are_kept(self) -> None:
        assert normalize("корпус 3") != normalize("корпус 5")

    @pytest.mark.parametrize("raw", ["", "   ", "!!!", "🔥"])
    def test_nothing_but_noise(self, raw: str) -> None:
        assert normalize(raw) == ""


class TestSimilarity:
    def test_identical(self) -> None:
        assert similarity("продам гараж", "продам гараж") == 1.0

    @pytest.mark.parametrize("other", ["", "что угодно"])
    def test_empty_side_is_zero(self, other: str) -> None:
        assert similarity("", other) == 0.0

    def test_unrelated_is_low(self) -> None:
        assert similarity("продам гараж", "куплю покрышки зимой") < 0.5

    def test_small_edit_is_high(self) -> None:
        assert similarity("продам гараж в корпусе 3", "продам гараж в корпусе 5") > 0.9

    def test_long_texts_are_not_penalised_by_autojunk(self) -> None:
        # SequenceMatcher объявляет частые символы «мусором» на длинных строках,
        # если autojunk не выключен: оценка бы провалилась.
        base = " ".join(f"слово{index}" for index in range(120))
        assert similarity(base, f"{base} ещё слово") > 0.95


class TestFindRepeat:
    def test_no_posts(self) -> None:
        assert find_repeat([], "продам гараж", now=NOW) is None

    def test_exact_copy_matches(self) -> None:
        posts = [stored("продам гараж в корпусе 3", message_id=7)]
        repeat = find_repeat(posts, "Продам Гараж в корпусе 3!!!", now=NOW)
        assert repeat is not None
        assert repeat.message_id == 7
        assert repeat.score == 1.0

    def test_below_threshold_is_quiet(self) -> None:
        posts = [stored("продам гараж в корпусе 3")]
        assert find_repeat(posts, "срочно вывезу мебель завтра утром", now=NOW) is None

    def test_threshold_boundary_counts_as_repeat(self) -> None:
        posts = [stored("продам гараж")]
        needle = "продам гараж срочно"
        score = similarity(normalize(needle), posts[0].text)
        assert 0 < score < 1
        assert find_repeat(posts, needle, now=NOW, threshold=score) is not None
        assert find_repeat(posts, needle, now=NOW, threshold=score + 0.01) is None

    def test_most_similar_post_wins(self) -> None:
        posts = [
            stored("продам гараж", message_id=1),
            stored("продам гараж в корпусе 3", message_id=2),
        ]
        repeat = find_repeat(posts, "продам гараж в корпусе 3", now=NOW)
        assert repeat is not None
        assert repeat.message_id == 2

    def test_old_posts_are_out_of_the_window(self) -> None:
        posts = [stored("продам гараж", at=NOW - 8 * DAY)]
        assert find_repeat(posts, "продам гараж", now=NOW, window_days=7) is None

    def test_last_day_of_the_window_still_matches(self) -> None:
        posts = [stored("продам гараж", at=NOW - 7 * DAY)]
        assert find_repeat(posts, "продам гараж", now=NOW, window_days=7) is not None

    def test_post_from_the_future_is_ignored(self) -> None:
        posts = [stored("продам гараж", at=NOW + DAY)]
        assert find_repeat(posts, "продам гараж", now=NOW) is None

    @pytest.mark.parametrize("text", ["", "   ", "!!!"])
    def test_needle_without_letters(self, text: str) -> None:
        posts = [stored("продам гараж")]
        assert find_repeat(posts, text, now=NOW) is None

    def test_broken_stored_text_is_ignored(self) -> None:
        posts = [StoredPost(message_id=1, posted_at=NOW - DAY, text="")]
        assert find_repeat(posts, "продам гараж", now=NOW) is None
