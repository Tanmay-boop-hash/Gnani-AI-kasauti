from voicetest.compare import compare_amount, compare_digits, compare_time
from voicetest.generate import generate,  indian_commas

def test_same_seed_is_identical():
    assert generate(0) == generate(0)

def test_different_seed_differs():
    assert generate(0) != generate(1)

def test_size_kinds_and_unique_names():
    cases = generate(0)
    assert len(cases) == 46
    assert {c[1] for c in cases} == {"digits", "amount", "time"}
    assert len({c[0] for c in cases}) == 46

def test_phone_and_pin_shapes():
    for name, kind, expected, _ in generate(3):
        if name.startswith("phone"):
            assert len(expected) == 10 and expected[0] in "6789"
        if name.startswith("pin"):
            assert len(expected) == 6 and expected[0] != "0"

def test_indian_commas():
    assert indian_commas(500000) == "5,00,000"
    assert indian_commas(12500) == "12,500"
    assert indian_commas(1500000) == "15,00,000"

def test_time_expected_values_are_comparable():
    for name, _, expected, _ in generate(5):
        if name.startswith("time"):
            h24, m = expected
            period = "शाम" if h24 >= 12 else "सुबह"
            heard = f"{period} {h24 % 12 or 12}:{m:02d} बजे"
            assert compare_time(expected, heard).ok

def test_first_40_unchanged_by_hinglish_variant():
    cases = generate(0)
    assert [c[0] for c in cases[:40]][0] == "phone-digits-s0-01"
    assert cases[39][0] == "time-s0-06"
    assert cases[40][0] == "acct-hinglish-s0-01"

def test_comparer_accepts_the_written_form_of_its_own_answers():
    # sanity: if the model heard the sentence perfectly, the comparer must pass it
    for name, _, expected, sentence in generate(5):
        if name.startswith(("phone-digits", "pin-digits", "acct-hinglish")):
            assert compare_digits(expected, sentence).ok
        if name.startswith("amount-symbol"):
            assert compare_amount(expected, sentence).ok
