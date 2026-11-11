from linger.core.text import norm, similar, split_sentences


def test_split_keeps_unfinished_tail():
    assert split_sentences("Hello there. How are") == ["Hello there.", "How are"]


def test_split_handles_question_and_exclamation():
    assert split_sentences("Ready? Go! Now.") == ["Ready?", "Go!", "Now."]


def test_split_collapses_whitespace_and_newlines():
    assert split_sentences("One.\n  Two  three.") == ["One.", "Two three."]


def test_split_urdu_full_stop():
    assert split_sentences("پہلا جملہ۔ دوسرا") == ["پہلا جملہ۔", "دوسرا"]


def test_norm_strips_punctuation_and_case():
    assert norm("Hello,   World!") == "hello world"


def test_similar_tolerates_small_asr_revisions():
    assert similar("My name is Allie.", "My name is Ali.")
    assert not similar("Good morning.", "Thank you for listening.")
