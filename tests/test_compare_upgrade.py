import pytest

from voicetest.compare import Result, compare_amount, compare_digits, compare_time


def test_result_style_defaults_to_digits():
    assert Result(True, "match", "1", "1").style == "digits"


# digits ------------------------------------------------------------
def test_digits_as_words_match_and_are_flagged():
    r = compare_digits("400076", "मेरा पिन कोड चार शून्य शून्य शून्य सात छह है।")
    assert r.ok and r.style == "words" and r.heard == "400076"


def test_digits_as_words_wrong_digit_is_substitution():
    r = compare_digits("400076", "चार शून्य शून्य शून्य सात नौ")
    assert not r.ok and r.kind == "substitution" and r.style == "words"


def test_double_word():
    assert compare_digits("887", "डबल आठ सात").ok


def test_digit_path_untouched_when_it_matches():
    r = compare_digits("9876543210", "मेरा नंबर 9876543210 है।")
    assert r.ok and r.style == "digits"


# amounts -----------------------------------------------------------
@pytest.mark.parametrize("heard, style", [
    ("₹5,00,000 भेजना है।", "digits"),
    ("5,00,000 रुपये भेजना है।", "digits"),
    ("50 लाख रुपये भेजना है।", "mixed"),
    ("पचास लाख रुपये भेजना है।", "words"),
    ("सवा लाख रुपये भेजना है।", "words"),
])
def test_amount_styles(heard, style):
    expected = 125000 if "सवा" in heard else 5000000 if "50" in heard or "पचास" in heard else 500000
    r = compare_amount(expected, heard)
    assert r.ok and r.style == style


def test_amount_mixed_is_not_read_as_50():
    # the v3.0 case: "50 लाख" used to be read as 50
    r = compare_amount(5000000, "50 लाख रुपये भेजना है।")
    assert r.ok and r.heard == "5000000"


def test_amount_wrong_value_in_words_reports_parsed_value():
    r = compare_amount(30000, "बीस हज़ार रुपये जमा करो")
    assert not r.ok and r.kind == "wrong_value" and r.heard == "20000" and r.style == "words"


def test_amount_prefers_number_next_to_rupee():
    r = compare_amount(12500, "दो बार बारह हज़ार पाँच सौ रुपये जमा करो")
    assert r.ok


def test_bare_small_word_is_not_an_amount():
    r = compare_amount(500000, "पैसे भेज दो")
    assert not r.ok and r.kind == "not_found"


# times -------------------------------------------------------------
@pytest.mark.parametrize("expected, heard, style", [
    ((9, 30), "सुबह साढ़े नौ बजे मिलते हैं।", "words"),
    ((9, 15), "सुबह सवा नौ बजे मिलते हैं।", "words"),
    ((9, 45), "सुबह पौने दस बजे मिलते हैं।", "words"),
    ((13, 30), "दोपहर डेढ़ बजे मिलते हैं।", "words"),
    ((14, 30), "दोपहर ढाई बजे मिलते हैं।", "words"),
    ((17, 0), "शाम पाँच बजे मिलते हैं।", "words"),
    ((17, 15), "शाम पाँच बजकर पंद्रह मिनट पर कॉल करना", "words"),
    ((17, 15), "शाम 5 बजकर 15 मिनट पर कॉल करना", "mixed"),
    ((17, 15), "शाम 05:15 पर कॉल करना।", "digits"),
    ((17, 15), "शाम 5:15 पर कॉल करना।", "digits"),
    ((19, 40), "शाम सात बजकर चालीस मिनट पर कॉल करना", "words"),
    ((0, 45), "रात पौने एक बजे", "words"),
])
def test_time_forms_match(expected, heard, style):
    r = compare_time(expected, heard)
    assert r.ok, r
    assert r.style == style


def test_pm_on_a_morning_time_is_wrong_period():
    r = compare_time((7, 45), "सुबह 7:45 pm पर कॉल करना")
    assert not r.ok and r.kind == "wrong_period"


def test_evening_word_on_a_morning_time_is_wrong_period():
    r = compare_time((7, 45), "शाम 7:45 पर कॉल करना")
    assert not r.ok and r.kind == "wrong_period"


def test_pm_suffix_on_evening_time_is_fine():
    assert compare_time((17, 15), "शाम 5:15 pm पर").ok
    assert compare_time((17, 15), "5:15 p.m. पर").ok


def test_no_period_word_is_missing_period_not_a_pass():
    r = compare_time((19, 40), "7:40 पर कॉल करना")
    assert not r.ok and r.kind == "missing_period" and r.heard == "07:40"


def test_require_period_false_softens_missing_period():
    assert compare_time((19, 40), "7:40 पर कॉल करना", require_period=False).ok


def test_wrong_value_takes_precedence_over_period():
    r = compare_time((9, 30), "सुबह साढ़े दस बजे")
    assert not r.ok and r.kind == "wrong_value" and r.heard == "10:30"


def test_night_word():
    assert compare_time((21, 0), "रात नौ बजे").ok
    assert not compare_time((9, 0), "रात नौ बजे").ok