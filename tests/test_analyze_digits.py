from analyze_digits import align, fillers_in_digit_span, heard_digits

def non_match(ops):
    return [o for o in ops if o[0] != "match"]

def test_identical_is_all_match():
    assert {o[0] for o in align("9876543210", "9876543210")} == {"match"}

def test_substitution_reports_position_and_digits():
    assert non_match(align("9876543210", "9876573210")) == [("sub", 5, "4", "7")]

def test_dropped_last_digit_is_a_deletion_at_the_last_position():
    assert non_match(align("400076", "40007")) == [("del", 5, "6", None)]

def test_extra_digits_count_as_one_insertion():
    ops = align("123", "1223")
    assert [o[0] for o in ops].count("ins") == 1
    assert not any(o[0] in ("sub", "del") for o in ops)

def test_nothing_heard_is_all_deletions():
    assert [o[0] for o in align("123", "")] == ["del"] * 3

def test_heard_digits_joins_split_runs_and_reads_devanagari_digits():
    assert heard_digits("मेरा नंबर था 1 था 0975351।") == "10975351"
    assert heard_digits("नंबर ९८७६") == "9876"


def test_filler_words_between_digits_are_found():
    assert fillers_in_digit_span("मेरा अकाउंट नंबर 5540 था 114 है।") == ["था"]
    assert fillers_in_digit_span("मेरा नंबर 9876543210 है।") == []