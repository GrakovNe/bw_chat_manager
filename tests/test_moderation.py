"""Тесты чистой функции decide()."""

from __future__ import annotations

import pytest

from bwbot.moderation import Action, decide

WORDS = frozenset({"корпус 1", "двор", "bw"})


def decide_one(text, *, words=WORDS, min_length=10, is_reply=False):
    return decide(text, allowed_words=words, min_length=min_length, is_reply=is_reply)


def test_reply_is_ignored_even_if_it_breaks_the_rule():
    assert decide_one("мусор", is_reply=True).action is Action.IGNORE_REPLY


def test_reply_check_comes_before_length():
    assert decide_one("ок", is_reply=True).action is Action.IGNORE_REPLY


@pytest.mark.parametrize("text", [None, "", "   ", "\n\t"])
def test_empty_text_is_ignored_not_deleted(text):
    assert decide_one(text).action is Action.IGNORE_EMPTY


def test_short_message_is_ignored_not_deleted():
    assert decide_one("ок").action is Action.IGNORE_SHORT


def test_message_without_allowed_word_is_deleted():
    assert decide_one("продам гараж срочно").action is Action.DELETE


def test_allowed_word_is_case_insensitive():
    decision = decide_one("ПРОДАМ кв-ру в Корпус 1 срочно")
    assert decision.action is Action.ALLOW
    assert decision.matched_word == "корпус 1"


def test_substring_match_is_enough():
    assert decide_one("у нас во дворе потоп").action is Action.ALLOW


def test_empty_word_list_deletes_everything():
    assert decide_one("любой текст", words=frozenset()).action is Action.DELETE


def test_blank_word_in_list_does_not_match_everything():
    assert decide_one("любой текст", words=frozenset({"", "  "})).action is Action.DELETE


def test_min_length_one_still_checks_words():
    assert decide_one("мусор", min_length=1).action is Action.DELETE


def test_deletes_property():
    assert decide_one("продам гараж срочно").deletes is True
    assert decide_one("ок").deletes is False
