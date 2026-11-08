import pytest
from voicetest.compare import compare_amount, compare_digits, compare_time, normalize


def test_normalize_strips_danda_and_converts_devanagari_digits():
    assert normalize("मेरा नंबर ९८७६५४३२१० है।") == "मेरा नंबर 9876543210 है।"


@pytest.mark.parametrize("heard", [
    "मेरा नंबर 9876543210 है।",
    "मेरा नंबर 98765 43210 है।",
    "मेरा नंबर 98765-43210 है।",
    "मेरा नंबर +91 98765 43210 है।",
    "मेरा नंबर ९८७६५४३२१० है।",
])
def test_phone_formats_that_should_match(heard):
    assert compare_digits("9876543210", heard).ok


def test_phone_dropped_digit_is_length_mismatch():
    r = compare_digits("9876543210", "मेरा नंबर 987654321 है।")
    assert not r.ok and r.kind == "length_mismatch"


def test_phone_wrong_digit_is_substitution():
    r = compare_digits("9876543210", "मेरा नंबर 9876543219 है।")
    assert not r.ok and r.kind == "substitution"


def test_phone_spoken_as_words_partial_is_length_mismatch():
    # was "not_found" before words were understood; now the 4 digits heard are compared
    r = compare_digits("9876543210", "मेरा नंबर नौ आठ सात छह है।")
    assert not r.ok and r.kind == "length_mismatch" and r.style == "words"


@pytest.mark.parametrize("heard", [
    "₹5,00,000 भेजना है।",
    "5,00,000 रुपये भेजना है।",
    "500000 रुपये भेजना है।",
    "Rs. 5,00,000 भेजना है।",
    "₹ 5,00,000.00 भेजना है।",
])
def test_amount_formats_that_should_match(heard):
    assert compare_amount(500000, heard).ok


def test_amount_wrong_value():
    r = compare_amount(500000, "₹5,00,00 भेजना है।")
    assert not r.ok and r.kind == "wrong_value"


def test_amount_words_now_match():
    # was "not_found" before the phrase parser; now words are understood and flagged as words
    r = compare_amount(500000, "पाँच लाख रुपये भेजना है।")
    assert r.ok and r.style == "words"


def test_amount_not_found():
    r = compare_amount(500000, "भेजना है।")
    assert not r.ok and r.kind == "not_found"


@pytest.mark.parametrize("heard", [
    "सुबह 09:30 बजे मिलते हैं।",
    "सुबह 9:30 बजे मिलते हैं।",
    "सुबह 9.30 बजे मिलते हैं।",
])
def test_time_formats_that_should_match(heard):
    assert compare_time((9, 30), heard).ok


def test_time_wrong_minute():
    r = compare_time((9, 30), "सुबह 09:45 बजे मिलते हैं।")
    assert not r.ok and r.kind == "wrong_value"


def test_time_half_in_words_now_matches():
    # was "not_found" before साढ़े was understood
    r = compare_time((9, 30), "सुबह साढ़े नौ बजे मिलते हैं।")
    assert r.ok and r.style == "words"


def test_time_not_found():
    r = compare_time((9, 30), "सुबह मिलते हैं।")
    assert not r.ok and r.kind == "not_found"