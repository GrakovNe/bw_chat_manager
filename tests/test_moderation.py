"""Tests for the pure decide() function."""

from __future__ import annotations

import pytest

from bwbot.moderation import Action, decide

WORDS = frozenset({"building 1", "yard", "bw"})


def decide_one(text, *, words=WORDS, min_length=10, is_reply=False):
    return decide(text, allowed_words=words, min_length=min_length, is_reply=is_reply)


def test_reply_is_ignored_even_if_it_breaks_the_rule():
    assert decide_one("trash", is_reply=True).action is Action.IGNORE_REPLY


def test_reply_check_comes_before_length():
    assert decide_one("ok", is_reply=True).action is Action.IGNORE_REPLY


@pytest.mark.parametrize("text", [None, "", "   ", "\n\t"])
def test_empty_text_is_ignored_not_deleted(text):
    assert decide_one(text).action is Action.IGNORE_EMPTY


def test_short_message_is_ignored_not_deleted():
    assert decide_one("ok").action is Action.IGNORE_SHORT


def test_message_without_allowed_word_is_deleted():
    assert decide_one("selling a garage urgently").action is Action.DELETE


def test_allowed_word_is_case_insensitive():
    decision = decide_one("SELLING an apt in Building 1 urgently")
    assert decision.action is Action.ALLOW
    assert decision.matched_word == "building 1"


def test_substring_match_is_enough():
    assert decide_one("we have a flood in the yard").action is Action.ALLOW


def test_empty_word_list_deletes_everything():
    assert decide_one("some random text", words=frozenset()).action is Action.DELETE


def test_blank_word_in_list_does_not_match_everything():
    assert decide_one("some random text", words=frozenset({"", "  "})).action is Action.DELETE


def test_min_length_one_still_checks_words():
    assert decide_one("trash", min_length=1).action is Action.DELETE


def test_deletes_property():
    assert decide_one("selling a garage urgently").deletes is True
    assert decide_one("ok").deletes is False
