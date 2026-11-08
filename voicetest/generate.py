import random

DIGIT_WORDS = "शून्य एक दो तीन चार पाँच छह सात आठ नौ".split()

NUM_WORDS = {
    1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पाँच", 6: "छह", 7: "सात",
    8: "आठ", 9: "नौ", 10: "दस", 11: "ग्यारह", 12: "बारह", 13: "तेरह",
    14: "चौदह", 15: "पंद्रह", 16: "सोलह", 17: "सत्रह", 18: "अठारह",
    19: "उन्नीस", 20: "बीस", 25: "पच्चीस", 30: "तीस", 40: "चालीस",
    50: "पचास", 60: "साठ", 75: "पचहत्तर", 80: "अस्सी", 90: "नब्बे",
}
MINUTE_WORDS = {5: "पाँच", 10: "दस", 15: "पंद्रह", 20: "बीस", 25: "पच्चीस",
                30: "तीस", 40: "चालीस", 45: "पैंतालीस", 50: "पचास"}


# (variant, how many) -> 52 sentences total
PLAN = [
    ("phone-digits", 6), ("phone-words", 6),
    ("pin-digits", 6), ("pin-words", 6),
    ("amount-symbol", 5), ("amount-words", 5),
    ("time", 6), ("acct-hinglish", 6),
    ("time-modifier", 6),          # appended at the END so earlier sentences (and their cache) never change
]

def indian_commas(n):
    """500000 -> '5,00,000', 12500 -> '12,500'"""
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
        return ",".join(groups + [tail])


def _digits(rng, n, first="0123456789"):
    return rng.choice(first) + "".join(rng.choice("0123456789") for _ in range(n - 1))

def _spoken_digits(s):
    return " ".join(DIGIT_WORDS[int(d)] for d in s)

def _amount(rng):
    """returns (value, spoken words) for a lakh / hazaar / hazaar+sau amount"""
    shape = rng.choice(["lakh", "hazaar", "hazaar-sau"])
    u = rng.choice(list(NUM_WORDS))
    if shape == "lakh":
        return u * 100000, f"{NUM_WORDS[u]} लाख"
    if shape == "hazaar":
        return u * 1000, f"{NUM_WORDS[u]} हज़ार"
    s = rng.randint(1, 9)
    return u * 1000 + s * 100, f"{NUM_WORDS[u]} हज़ार {NUM_WORDS[s]} सौ"

def _time(rng):
    """returns ((hour24, minute), sentence)"""
    if rng.random() < 0.5:
        period, h = "सुबह", rng.randint(6, 11)
        h24 = h
    else:
        period, h = "शाम", rng.randint(4, 9)
        h24 = h + 12
    m = rng.choice(list(MINUTE_WORDS))
    sentence = f"{period} {NUM_WORDS[h]} बजकर {MINUTE_WORDS[m]} मिनट पर कॉल करना"
    return (h24, m), sentence


MODIFIER_FORMS = ["saadhe", "sava", "paune", "dedh", "dhai"]

def _time_modifier(rng, i):
    """साढ़े / सवा / पौने / डेढ़ / ढाई forms. The form cycles with i, so every form appears
    in every seed; only the period and the hour are random. returns ((hour24, minute), sentence)"""
    form = MODIFIER_FORMS[(i - 1) % len(MODIFIER_FORMS)]
    if form == "dedh":
        return (13, 30), "दोपहर डेढ़ बजे मिलते हैं"
    if form == "dhai":
        return (14, 30), "दोपहर ढाई बजे मिलते हैं"
    if rng.random() < 0.5:
        period, h, shift = "सुबह", rng.randint(7, 11), 0
    else:
        period, h, shift = "शाम", rng.randint(5, 9), 12
    if form == "saadhe":
        return (h + shift, 30), f"{period} साढ़े {NUM_WORDS[h]} बजे मिलते हैं"
    if form == "sava":
        return (h + shift, 15), f"{period} सवा {NUM_WORDS[h]} बजे मिलते हैं"
    return (h - 1 + shift, 45), f"{period} पौने {NUM_WORDS[h]} बजे मिलते हैं"   # पौने दस = 9:45


def generate(seed=0):
    """Same seed -> exactly the same list of (name, kind, expected, sentence)."""
    rng = random.Random(seed)
    cases = []
    for variant, count in PLAN:
        for i in range(1, count + 1):
            name = f"{variant}-s{seed}-{i:02d}"
            if variant == "phone-digits":
                p = _digits(rng, 10, "6789")
                cases.append((name, "digits", p, f"मेरा नंबर {p} है"))
            elif variant == "phone-words":
                p = _digits(rng, 10, "6789")
                cases.append((name, "digits", p, f"मेरा नंबर {_spoken_digits(p)} है"))
            elif variant == "pin-digits":
                p = _digits(rng, 6, "123456789")
                cases.append((name, "digits", p, f"मेरा पिन कोड {p} है"))
            elif variant == "pin-words":
                p = _digits(rng, 6, "123456789")
                cases.append((name, "digits", p, f"मेरा पिन कोड {_spoken_digits(p)} है"))
            elif variant == "amount-symbol":
                value, _ = _amount(rng)
                cases.append((name, "amount", value, f"₹{indian_commas(value)} भेजना है"))
            elif variant == "amount-words":
                value, words = _amount(rng)
                cases.append((name, "amount", value, f"{words} रुपये भेजना है"))
            elif variant == "time":
                expected, sentence = _time(rng)
                cases.append((name, "time", expected, sentence))
            elif variant == "time-modifier":
                expected, sentence = _time_modifier(rng, i)
                cases.append((name, "time", expected, sentence))
            elif variant == "acct-hinglish":
                p = _digits(rng, 8, "123456789")
                cases.append((name, "digits", p, f"मेरा account number {p[:4]} {p[4:]} है"))
    return cases