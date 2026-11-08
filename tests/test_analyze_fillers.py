import pytest

from analyze_digits import carrier_table, fillers_vs_carrier, report

PHONE = "मेरा नंबर 9876543210 है"
PIN = "मेरा पिन कोड 400076 है"
HING = "मेरा account number 1234 5678 है"
WORDS = "मेरा पिन कोड चार शून्य शून्य शून्य सात छह है"


@pytest.mark.parametrize("transcript, carrier, expected", [
    ("मेरा नंबर 9876543210 है।", PHONE, []),
    ("मेरा नंबर था 876543210 है।", PHONE, [("था", "before")]),        # filler BEFORE the first digit
    ("मेरा नंबर 55401 था 114 है।", PHONE, [("था", "inside")]),
    ("मेरा नंबर 9876543210 हाँ है।", PHONE, [("हां", "after")]),
    ("मेरा पिन कोड हाँ 40007 है", PIN, [("हां", "before")]),
    ("मेरा पिनकोड 400076 है", PIN, []),                               # joined spelling is not a filler
    ("मेरा अकाउंट नंबर 1234 5678 है", HING, []),                      # transliterated carrier is not a filler
    ("मेरा account number 1234 5678 है", HING, []),
    ("मेरा पिन कोड चार शून्य शून्य शून्य सात छह है", WORDS, []),      # number words are digits, not fillers
    ("मेरा पिन कोड हाँ शून्य शून्य शून्य सात छह है", WORDS, [("हां", "before")]),
])
def test_fillers(transcript, carrier, expected):
    assert fillers_vs_carrier(transcript, carrier) == expected


def test_unlocatable_zone_is_none_not_a_guess():
    assert fillers_vs_carrier("नमस्ते 9876543210", PHONE) is None        # no opening carrier word
    assert fillers_vs_carrier("मेरा नंबर है", PHONE) is None             # no digits at all


def test_without_closing_word_zone_runs_to_the_end():
    assert fillers_vs_carrier("मेरा नंबर 98765 था", PHONE) == [("था", "after")]


def test_carrier_table_has_generated_and_hand_sentences():
    t = carrier_table([{"seed": 0}])
    assert t["phone-digits"] == "मेरा नंबर 9876543210 है"
    assert t["time-modifier-s0-01"].startswith("सुबह साढ़े")


def test_report_runs_and_counts_leading_filler(capsys):
    recs = [dict(seed=0, name="phone-digits-s0-01", entity="phone-digits", kind="digits",
                 condition="phone+0dB", model="prisma-v3.0", ok=False, failure="length_mismatch",
                 expected="x", extracted="y", transcript="मेरा नंबर था 876543210 है।"),
            dict(seed=0, name="phone-digits-s0-01", entity="phone-digits", kind="digits",
                 condition="phone+0dB", model="prisma-v2.5", ok=True, failure="match",
                 expected="x", extracted="x", transcript="मेरा नंबर 9876543210 है।"),
            dict(seed=0, name="no-such-name", entity="n", kind="digits",
                 condition="phone+0dB", model="prisma-v2.5", ok=False, failure="substitution",
                 expected="1", extracted="2", transcript="2")]
    report(recs, ["phone+0dB"], 5)
    out = capsys.readouterr().out
    assert "failed clips with filler 1/1" in out        # prisma-v3.0
    assert "sentence unknown 1" in out                  # prisma-v2.5 unknown name
    assert "before 1" in out and "था x1" in out