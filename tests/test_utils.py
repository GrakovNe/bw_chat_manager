"""Тесты утилит."""

from __future__ import annotations

import pytest

from bwbot.utils import append_note, chunk_text, human_age, normalize_word


def test_normalize_word():
    assert normalize_word("  Корпус 1\n") == "корпус 1"


def test_chunk_text_short_text_is_single_chunk():
    assert chunk_text("раз\nдва", limit=100) == ["раз\nдва"]


def test_chunk_text_empty_text():
    assert chunk_text("", limit=100) == []


def test_chunk_text_fits_exactly():
    assert chunk_text("abcde", limit=5) == ["abcde"]


def test_chunk_text_never_breaks_a_line():
    lines = ["словo" * 4]
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
    assert append_note("отчёт", "забанен") == "отчёт\n\nзабанен"


def test_append_note_without_note_keeps_text():
    assert append_note("отчёт", "") == "отчёт"


def test_append_note_truncates_report_but_keeps_note():
    result = append_note("x" * 100, "забанен", limit=40)
    assert result.endswith("забанен")
    assert len(result) == 40


def test_append_note_drops_report_when_note_eats_the_limit():
    assert append_note("отчёт", "n" * 50, limit=20) == "n" * 20


def test_append_note_leaves_no_dangling_spaces():
    assert append_note("a" * 8 + "   ", "note", limit=15) == "aaaaaaaa\n\nnote"


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (0, "сегодня"),
        (0.5, "сегодня"),
        (1, "вчера"),
        (2, "2 дня назад"),
        (5, "5 дней назад"),
        (11, "11 дней назад"),
        (21, "21 день назад"),
        (24, "24 дня назад"),
        (111, "111 дней назад"),
    ],
)
def test_human_age(days, expected):
    day = 86400
    assert human_age(1_000_000 - days * day, 1_000_000) == expected


def test_human_age_clock_skew_is_today():
    assert human_age(1_000_100, 1_000_000) == "сегодня"
