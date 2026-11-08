from voicetest.cases import judge
from voicetest.generate import generate


def modifier_cases(seed):
    return [c for c in generate(seed) if c[0].startswith("time-modifier")]


def test_six_modifier_sentences_per_seed_and_all_five_forms_appear():
    cs = modifier_cases(0)
    assert len(cs) == 6
    text = " ".join(c[3] for c in cs)
    for word in ("साढ़े", "सवा", "पौने", "डेढ़", "ढाई"):
        assert word in text


def test_modifier_sentences_are_deterministic():
    assert modifier_cases(3) == modifier_cases(3)


def test_old_sentences_come_first_and_unchanged_in_order():
    names = [c[0] for c in generate(0)]
    assert names[45].startswith("acct-hinglish") and names[46].startswith("time-modifier")


def test_expected_times_are_what_the_sentence_says():
    for seed in range(5):
        for name, kind, expected, text in modifier_cases(seed):
            assert kind == "time"
            # the sentence spoken exactly as written must pass the comparer
            assert judge(kind, expected, text + "।").ok, (name, text, expected)


def test_paune_is_one_hour_back():
    found = 0
    for name, _, expected, text in modifier_cases(0):
        if "पौने" in text:
            found += 1
            assert expected[1] == 45
    assert found == 1