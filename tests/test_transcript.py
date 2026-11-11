import itertools

import pytest

from linger.core.transcript import Transcript


@pytest.fixture
def tr():
    counter = itertools.count(1_700_000_000)
    return Transcript(clock=lambda: float(next(counter)))


def feed(t, frames):
    for f in frames:
        t.update(f)
    t.flush()
    return t.texts


def test_rolling_window_is_deduplicated(tr):
    frames = [
        "Hello every",
        "Hello everyone. Today we",
        "Hello everyone. Today we will talk about AI.",
        "Hello everyone. Today we will talk about AI. It is very",
        "everyone. Today we will talk about AI. It is very useful. Yes.",
        "talk about AI. It is very useful. Yes. Thanks for",
        "It is very useful. Yes. Thanks for coming.",
    ]
    assert feed(tr, frames) == [
        "Hello everyone.", "Today we will talk about AI.", "It is very useful.", "Yes.", "Thanks for coming.",
    ]


def test_newest_sentences_stay_pending_until_settled(tr):
    tr.update("First sentence. Second one. Third is still")
    assert tr.texts == ["First sentence."]
    assert tr.partial == "Second one. Third is still"


def test_decimals_are_not_sentence_breaks(tr):
    assert feed(tr, ["Version 1.0 is ready. It costs 3.5 dollars."]) == ["Version 1.0 is ready.", "It costs 3.5 dollars."]


def test_revision_of_last_finished_sentence_is_not_duplicated(tr):
    frames = [
        "Version one point oh is ready. It",
        "Version 1.0 is ready. It keeps every line.",
        "Version 1.0 is ready. It keeps every line. Thank you.",
        "Version 1.0 is ready. It keeps every line. Thank you. Bye",
    ]
    assert feed(tr, frames) == ["Version 1.0 is ready.", "It keeps every line.", "Thank you.", "Bye"]


def test_unpunctuated_text_that_scrolls_off_is_saved(tr):
    frames = [
        "one two three four five six",
        "one two three four five six seven eight",
        "three four five six seven eight nine ten",
        "five six seven eight nine ten eleven",
    ]
    assert " ".join(feed(tr, frames)).split() == "one two three four five six seven eight nine ten eleven".split()


def test_baseline_text_before_start_is_ignored(tr):
    tr.set_baseline("Old stuff here. More old text.")
    frames = [
        "Old stuff here. More old text. New one",
        "Old stuff here. More old text. New one is here. And",
        "More old text. New one is here. And done.",
    ]
    assert feed(tr, frames) == ["New one is here.", "And done."]


def test_baseline_survives_re_punctuation(tr):
    tr.set_baseline("Checking that captions appear in the recorder. Second sentence, here third one is the last")
    frames = [
        "Checking that captions appear in the recorder second sentence here third one is the last interview test. "
        "New words arrive",
        "Checking that captions appear in the recorder second sentence here third one is the last interview test. "
        "New words arrive now. Done.",
    ]
    assert feed(tr, frames) == ["Interview test.", "New words arrive now.", "Done."]


def test_legit_repeated_sentence_after_other_text(tr):
    frames = ["Yes. I agree. Yes", "Yes. I agree. Yes. Okay."]
    assert feed(tr, frames) == ["Yes.", "I agree.", "Yes.", "Okay."]


def test_clear_resets_and_bumps_version(tr):
    tr.update("A sentence here. Another. More")
    v = tr.version
    tr.clear()
    assert tr.texts == [] and tr.partial == "" and tr.version == v + 1


def test_word_count_includes_partial(tr):
    tr.update("Two words. Three more words. Four")
    assert tr.word_count == 6


@pytest.mark.parametrize("fmt", ["text", "timestamps", "markdown", "srt"])
def test_exports(tr, fmt):
    tr.update("First line here. Second line here. Third")
    out = tr.export(fmt)
    assert "First line here." in out and "Third" in out


def test_srt_structure(tr):
    tr.update("First line here. Second line here. x. y")
    blocks = tr.export("srt", include_partial=False).strip().split("\n\n")
    assert len(blocks) == 2
    assert blocks[0].splitlines()[0] == "1"
    assert " --> " in blocks[0].splitlines()[1]


def test_export_empty_and_unknown(tr):
    assert tr.export("text") == ""
    tr.update("Hi there. x. y")
    with pytest.raises(ValueError):
        tr.export("pdf")


def test_new_speech_repeating_old_text_is_recorded(tr):
    old = "Version one is ready. It keeps every line. Thank you for testing goodbye"
    tr.set_baseline(old)
    frames = [
        old,
        old + " version one",
        old + ". Version one is ready. It keeps",
        old + ". Version one is ready. It keeps every line. Thank you.",
        "every line. Thank you for testing goodbye. Version one is ready. It keeps every line. Thank you. Bye",
    ]
    assert feed(tr, frames) == ["Version one is ready.", "It keeps every line.", "Thank you.", "Bye"]


def test_identical_repeat_after_old_text_scrolls_off(tr):
    old = "It keeps every line. The price is five dollars. Thank you"
    tr.set_baseline(old)
    frames = [
        old + ". It keeps every line. The",
        old + ". It keeps every line. The price is five dollars. Thank you.",
        "The price is five dollars. Thank you. It keeps every line. The price is five dollars. Thank you. Goodbye",
        "It keeps every line. The price is five dollars. Thank you. Goodbye.",
    ]
    assert feed(tr, frames) == ["It keeps every line.", "The price is five dollars.", "Thank you.", "Goodbye."]


def test_baseline_survives_number_reformatting(tr):
    tr.set_baseline("Version one point zero is ready. The price is three point five dollars. Thank you")
    frames = [
        "Version 1.0 is ready. The price is 3.5 dollars. Thank you. Brand new",
        "Version 1.0 is ready. The price is 3.5 dollars. Thank you. Brand new words here. More. Even more",
    ]
    assert feed(tr, frames) == ["Brand new words here.", "More.", "Even more"]


def test_history_rewrite_does_not_duplicate_committed_lines(tr):
    frames = [
        "The price is three point five dollars. It is cheap. Buy",
        "The price is 3.5 dollars. It is cheap. Buy it now. Okay",
        "The price is 3.5 dollars. It is cheap. Buy it now. Okay then. Done",
    ]
    assert feed(tr, frames) == ["The price is three point five dollars.", "It is cheap.", "Buy it now.",
                                "Okay then.", "Done"]
