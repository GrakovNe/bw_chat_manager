"""Utility tests."""

from __future__ import annotations

import pytest

from bwbot.utils import append_note, chunk_text, clip, human_age, normalize_word


def test_normalize_word():
    assert normalize_word("  Building 1\n") == "building 1"


def test_chunk_text_short_text_is_single_chunk():
    assert chunk_text("one\ntwo", limit=100) == ["one\ntwo"]


def test_chunk_text_empty_text():
    assert chunk_text("", limit=100) == []


def test_chunk_text_fits_exactly():
    assert chunk_text("abcde", limit=5) == ["abcde"]


def test_chunk_text_never_breaks_a_line():
    lines = ["word" * 4]
    chunks = chunk_text("\n".join(lines * 5), limit=25)
    assert all(len(chunk) <= 25 for chunk in chunks)
    assert "\n".join(chunks).split("\n") == lines * 5


def test_chunk_text_oversized_single_line_is_not_lost():
    giant = "x" * 50
    assert chunk_text(giant, limit=10) == [giant]


def test_chunk_text_roundtrips_everything():
    body = "\n".join(f"line-{index}" for index in range(200))
    chunks = chunk_text(body, limit=120)
    assert "\n".join(chunks) == body


@pytest.mark.parametrize("limit", [10, 120, 4096])
def test_chunk_text_respects_limit(limit):
    body = "\n".join(f"line-{index}" for index in range(50))
    assert all(len(chunk) <= limit for chunk in chunk_text(body, limit=limit))


def test_append_note_puts_note_behind_blank_line():
    assert append_note("report", "banned") == "report\n\nbanned"


def test_append_note_without_note_keeps_text():
    assert append_note("report", "") == "report"


def test_append_note_truncates_report_but_keeps_note():
    result = append_note("x" * 100, "banned", limit=40)
    assert result.endswith("banned")
    assert len(result) == 40


def test_append_note_drops_report_when_note_eats_the_limit():
    assert append_note("report", "n" * 50, limit=20) == "n" * 20


def test_append_note_leaves_no_dangling_spaces():
    assert append_note("a" * 8 + "   ", "note", limit=15) == "aaaaaaaa\n\nnote"


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (0, "today"),
        (0.5, "today"),
        (1, "yesterday"),
        (2, "2 days ago"),
        (5, "5 days ago"),
        (11, "11 days ago"),
        (21, "21 days ago"),
        (24, "24 days ago"),
        (111, "111 days ago"),
    ],
)
def test_human_age(days, expected):
    day = 86400
    assert human_age(1_000_000 - days * day, 1_000_000) == expected


def test_human_age_clock_skew_is_today():
    assert human_age(1_000_100, 1_000_000) == "today"


class TestClip:
    def test_short_text_is_untouched(self):
        assert clip("garage", limit=100) == "garage"

    def test_text_exactly_at_limit_is_untouched(self):
        assert clip("abcde", limit=5) == "abcde"

    def test_long_text_is_clipped_with_ellipsis(self):
        result = clip("a" * 100, limit=10)
        assert len(result) == 10
        assert result.endswith("…")
        assert result.startswith("a")

    def test_trailing_space_is_trimmed_before_ellipsis(self):
        assert clip("word " * 10, limit=8) == "word wo…"

    @pytest.mark.parametrize("limit", [0, -5])
    def test_non_positive_limit_yields_empty_string(self, limit):
        assert clip("text", limit=limit) == ""

    def test_limit_of_one_is_just_ellipsis(self):
        assert clip("text", limit=1) == "…"
