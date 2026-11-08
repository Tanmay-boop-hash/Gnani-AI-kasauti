import pytest
from fractions import Fraction

from voicetest.hindi_numbers import (NUMBER_WORDS, canon, digit_word_runs, find_numbers, parse_numbers)


def values(text):
    return [p.value for p in parse_numbers(text)[1]]


def test_table_covers_0_to_99_and_roundtrips():
    assert set(NUMBER_WORDS.values()) == set(range(100))
    for word, v in NUMBER_WORDS.items():
        assert values(word) == [v], word


@pytest.mark.parametrize("text, expected", [
    ("पाँच लाख", 500000),
    ("पांच लाख", 500000),                       # spelling variant
    ("बारह हज़ार पाँच सौ", 12500),
    ("बारह हजार पाँच सौ", 12500),               # no nukta
    ("पचास लाख", 5000000),
    ("एक करोड़ बीस लाख", 12000000),
    ("दो सौ पच्चीस", 225),
    ("एक सौ पच्चीस हज़ार", 125000),
    ("सवा लाख", 125000),
    ("पौने सौ", 75),
    ("सवा सौ", 125),
    ("साढ़े तीन सौ", 350),
    ("डेढ़ सौ", 150),
    ("ढाई हज़ार", 2500),
    ("ढाई लाख", 250000),
    ("साढ़े नौ", Fraction(19, 2)),
    ("सवा नौ", Fraction(37, 4)),
    ("पौने दस", Fraction(39, 4)),
    ("डेढ़", Fraction(3, 2)),
    ("5,00,000", 500000),
    ("₹5,00,000.00", 500000),
    ("50 लाख", 5000000),
    ("९८७६", 9876),                              # Devanagari digits
])
def test_values(text, expected):
    assert values(text) == [Fraction(expected)]


def test_adjacent_plain_numbers_are_separate():
    assert values("पाँच छह") == [5, 6]
    assert values("1234 5678") == [1234, 5678]
    assert values("भेज दो") == [2]                 # the verb is a number to the parser; callers must ignore it


def test_styles():
    def style(t):
        return parse_numbers(t)[1][0].style
    assert style("5,00,000") == "digits"
    assert style("50 लाख") == "mixed"
    assert style("पचास लाख") == "words"


def test_token_ranges_let_callers_find_neighbours():
    toks, ph = parse_numbers("शाम पाँच बजकर पंद्रह मिनट")
    assert [(p.start, p.end) for p in ph] == [(1, 2), (3, 4)]
    assert toks[2].word == canon("बजकर")


def test_canon_folds_variants():
    assert canon("हज़ार") == canon("हजार")
    assert canon("पाँच") == canon("पांच")
    assert canon("साढ़े") == canon("साढे")


@pytest.mark.parametrize("text, runs", [
    ("नौ आठ सात छह पाँच चार तीन दो एक शून्य", ["9876543210"]),
    ("मेरा नंबर नौ आठ सात छह है", ["9876"]),
    ("डबल आठ सात", ["887"]),
    ("ट्रिपल आठ", ["888"]),
    ("98765 चार तीन", ["9876543"]),
    ("9876543210", []),                          # digits only: not a "word run"
    ("मेरा नंबर है", []),
    ("चार शून्य शून्य शून्य सात छह है, फिर तीन दो", ["400076", "32"]),
])
def test_digit_word_runs(text, runs):
    assert digit_word_runs(text) == runs