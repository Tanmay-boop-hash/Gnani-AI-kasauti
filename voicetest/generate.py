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


# (variant, how many) -> 40 sentences total
PLAN = [
    ("phone-digits", 6), ("phone-words", 6),
    ("pin-digits", 6), ("pin-words", 6),
    ("amount-symbol", 5), ("amount-words", 5),
    ("time", 6),
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
    return cases
