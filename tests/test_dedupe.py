"""Similarity metric and the repeat window."""

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
            ("Selling Garage", "selling garage"),
            ("  selling    garage\n", "selling garage"),
            ("selling garage!!!", "selling garage"),
            ("selling garage 🔥🔥", "selling garage"),
            ("Selling\tgarage", "selling garage"),
        ],
    )
    def test_noise_is_stripped(self, raw: str, expected: str) -> None:
        assert normalize(raw) == expected

    def test_digits_are_kept(self) -> None:
        assert normalize("building 3") != normalize("building 5")

    @pytest.mark.parametrize("raw", ["", "   ", "!!!", "🔥"])
    def test_nothing_but_noise(self, raw: str) -> None:
        assert normalize(raw) == ""


class TestSimilarity:
    def test_identical(self) -> None:
        assert similarity("selling garage", "selling garage") == 1.0

    @pytest.mark.parametrize("other", ["", "anything"])
    def test_empty_side_is_zero(self, other: str) -> None:
        assert similarity("", other) == 0.0

    def test_unrelated_is_low(self) -> None:
        assert similarity("selling garage", "buying tires in winter") < 0.5

    def test_small_edit_is_high(self) -> None:
        assert similarity("selling a garage in building 3", "selling a garage in building 5") > 0.9

    def test_long_texts_are_not_penalised_by_autojunk(self) -> None:
        # SequenceMatcher declares frequent characters "junk" on long strings when
        # autojunk is not off: the score would collapse.
        base = " ".join(f"word{index}" for index in range(120))
        assert similarity(base, f"{base} another word") > 0.95

    def test_equal_prefix_beyond_compare_limit_reads_as_identical(self) -> None:
        left = "selling a garage " + "x" * 700 + "first"
        right = "selling a garage " + "x" * 700 + "second"
        assert similarity(normalize(left), normalize(right)) == 1.0

    def test_threshold_never_hides_a_real_repeat(self) -> None:
        left = normalize("selling a garage in building 3 urgently")
        right = normalize("Selling A Garage In Building 3 urgently!!!")
        assert similarity(left, right, threshold=0.9) >= 0.9

    def test_threshold_cuts_obviously_different_long_texts(self) -> None:
        # quick_ratio is an upper bound: if even it is zero, no exact comparison is needed.
        assert similarity("a" * 4000, "b" * 4000, threshold=0.9) == 0.0


class TestFindRepeat:
    def test_no_posts(self) -> None:
        assert find_repeat([], "selling garage", now=NOW) is None

    def test_exact_copy_matches(self) -> None:
        posts = [stored("selling a garage in building 3", message_id=7)]
        repeat = find_repeat(posts, "Selling A Garage In Building 3!!!", now=NOW)
        assert repeat is not None
        assert repeat.message_id == 7
        assert repeat.score == 1.0

    def test_below_threshold_is_quiet(self) -> None:
        posts = [stored("selling a garage in building 3")]
        assert find_repeat(posts, "urgently haul away furniture tomorrow morning", now=NOW) is None

    def test_threshold_boundary_counts_as_repeat(self) -> None:
        posts = [stored("selling garage")]
        needle = "selling garage urgently"
        score = similarity(normalize(needle), posts[0].text)
        assert 0 < score < 1
        assert find_repeat(posts, needle, now=NOW, threshold=score) is not None
        assert find_repeat(posts, needle, now=NOW, threshold=score + 0.01) is None

    def test_most_similar_post_wins(self) -> None:
        posts = [
            stored("selling garage", message_id=1),
            stored("selling a garage in building 3", message_id=2),
        ]
        repeat = find_repeat(posts, "selling a garage in building 3", now=NOW)
        assert repeat is not None
        assert repeat.message_id == 2

    def test_old_posts_are_out_of_the_window(self) -> None:
        posts = [stored("selling garage", at=NOW - 8 * DAY)]
        assert find_repeat(posts, "selling garage", now=NOW, window_days=7) is None

    def test_last_day_of_the_window_still_matches(self) -> None:
        posts = [stored("selling garage", at=NOW - 7 * DAY)]
        assert find_repeat(posts, "selling garage", now=NOW, window_days=7) is not None

    def test_post_from_the_future_is_ignored(self) -> None:
        posts = [stored("selling garage", at=NOW + DAY)]
        assert find_repeat(posts, "selling garage", now=NOW) is None

    @pytest.mark.parametrize("text", ["", "   ", "!!!"])
    def test_needle_without_letters(self, text: str) -> None:
        posts = [stored("selling garage")]
        assert find_repeat(posts, text, now=NOW) is None

    def test_long_copy_is_still_found(self) -> None:
        long_text = "selling a garage in building 3 " + "listing details " * 300
        repeat = find_repeat(
            [stored(long_text)],
            long_text.upper(),
            now=NOW,
            window_days=7,
            threshold=0.9,
        )
        assert repeat is not None
        assert repeat.message_id == 1

    def test_broken_stored_text_is_ignored(self) -> None:
        posts = [StoredPost(message_id=1, posted_at=NOW - DAY, text="")]
        assert find_repeat(posts, "selling garage", now=NOW) is None
