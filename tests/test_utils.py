"""Тесты утилит."""

from __future__ import annotations

import pytest

from bwbot.utils import chunk_text, normalize_word


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
