"""Hindi number phrases -> exact values.

Turns "बारह हज़ार पाँच सौ", "सवा लाख", "50 लाख", "5,00,000" or "पौने दस" into an exact
number (fractions.Fraction, so quarters and halves have no rounding error).

UNVERIFIED: the 0-99 word table below was written from knowledge, not checked against a
reference library (num2words has no Hindi). 
tests/test_hindi_numbers.py only checks that the table is internally consistent, not that every spelling is how Hindi speakers write it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from fractions import Fraction
from decimal import Decimal

_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def canon(word: str) -> str:
    """Spelling-variant folding: drop the nukta (ज़->ज, ड़->ड, ढ़->ढ) and turn chandrabindu
    into anusvara (पाँच -> पांच), so both spellings hit the same table entry."""
    w = unicodedata.normalize("NFKC", word)
    for ch in ("\u093c", "\u200c", "\u200d"):
        w = w.replace(ch, "")
    return w.replace("\u0901", "\u0902")


# value -> spellings, separated by spaces
_WORDS = {
    0: "शून्य सिफर ज़ीरो जीरो",
    1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पाँच पांच", 6: "छह छः छे छ", 7: "सात", 8: "आठ", 9: "नौ", 10: "दस", 
    11: "ग्यारह", 12: "बारह", 13: "तेरह", 14: "चौदह", 15: "पंद्रह पन्द्रह", 16: "सोलह", 17: "सत्रह", 18: "अठारह", 19: "उन्नीस", 
    20: "बीस", 21: "इक्कीस", 22: "बाईस बाइस", 23: "तेईस तेइस", 24: "चौबीस", 25: "पच्चीस", 26: "छब्बीस", 27: "सत्ताईस", 28: "अट्ठाईस अठाईस", 29: "उनतीस", 
    30: "तीस", 31: "इकतीस इकत्तीस", 32: "बत्तीस", 33: "तैंतीस तेंतीस तैतीस", 34: "चौंतीस चौतीस", 35: "पैंतीस पैतीस", 36: "छत्तीस", 37: "सैंतीस सेंतीस", 38: "अड़तीस", 39: "उनतालीस उन्तालीस",
    40: "चालीस", 41: "इकतालीस", 42: "बयालीस बेयालीस", 43: "तैंतालीस तेंतालीस तैतालीस तिरतालीस", 44: "चौवालीस चवालीस चौंवालीस", 45: "पैंतालीस पैतालीस", 46: "छियालीस छयालीस", 47: "सैंतालीस सेंतालीस", 48: "अड़तालीस", 49: "उनचास",
    50: "पचास", 51: "इक्यावन इकावन", 52: "बावन", 53: "तिरपन तिरेपन", 54: "चौवन", 55: "पचपन", 56: "छप्पन", 57: "सत्तावन", 58: "अट्ठावन अठावन", 59: "उनसठ",
    60: "साठ", 61: "इकसठ", 62: "बासठ", 63: "तिरसठ तिरेसठ", 64: "चौंसठ चौसठ", 65: "पैंसठ पैसठ", 66: "छियासठ छासठ", 67: "सड़सठ", 68: "अड़सठ", 69: "उनहत्तर उन्हत्तर",
    70: "सत्तर", 71: "इकहत्तर", 72: "बहत्तर", 73: "तिहत्तर", 74: "चौहत्तर", 75: "पचहत्तर", 76: "छिहत्तर", 77: "सतहत्तर", 78: "अठहत्तर", 79: "उन्यासी उनासी उन्नासी",
    80: "अस्सी", 81: "इक्यासी", 82: "बयासी", 83: "तिरासी", 84: "चौरासी", 85: "पचासी", 86: "छियासी", 87: "सत्तासी", 88: "अट्ठासी अठासी", 89: "नवासी",
    90: "नब्बे", 91: "इक्यानवे", 92: "बानवे बानबे", 93: "तिरानवे", 94: "चौरानवे", 95: "पंचानवे पचानवे", 96: "छियानवे", 97: "सत्तानवे", 98: "अट्ठानवे अठानवे", 99: "निन्यानवे निन्यानबे निन्यानवें",
}


def _build(table: dict[int, str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value, spellings in table.items():
        for s in spellings.split():
            c = canon(s)
            if out.get(c, value) != value:          # same spelling for two values = a typo in the table
                raise ValueError(f"spelling {s!r} is listed for both {out[c]} and {value}")
            out[c] = value
    return out


NUMBER_WORDS = _build(_WORDS)                                     # 0-99
DIGIT_WORDS = {w: v for w, v in NUMBER_WORDS.items() if v < 10}   # single digits, for digit-by-digit speech
SCALES = {canon(w): v for w, v in {"सौ": 100, "हज़ार": 1000, "हजार": 1000, "लाख": 10**5,
                                   "करोड़": 10**7, "करोड": 10**7}.items()}
# modifiers: applied to the NEXT number (or to an implicit 1 before a scale word)
MODIFIERS = {canon(w): d for w, d in {"सवा": Fraction(1, 4), "साढ़े": Fraction(1, 2),
                                      "पौने": Fraction(-1, 4)}.items()}
# standalone fractional numbers
FRACTION_NUMBERS = {canon(w): v for w, v in {"डेढ़": Fraction(3, 2), "ढाई": Fraction(5, 2),
                                             "अढ़ाई": Fraction(5, 2)}.items()}
MULTIPLIERS = {canon("डबल"): 2, "double": 2, canon("ट्रिपल"): 3, "triple": 3}   # "double eight" = 88


@dataclass(frozen=True)
class Tok:
    kind: str            # num | scale | mod | word | sym
    word: str            # canonical word, or the raw text of a digit token
    value: Fraction | None = None
    digit: bool = False  # True for tokens written with digits (5,00,000)


@dataclass(frozen=True)
class Phrase:
    value: Fraction
    style: str           # digits (only digit tokens) | mixed (digits + words, like 50 लाख) | words
    start: int           # token index range [start, end)
    end: int


_TOKEN = re.compile(r"₹|\d[\d,]*(?:\.\d+)?|[\u0900-\u0963\u0970-\u097F]+|[A-Za-z]+")


def tokenize(text: str) -> list[Tok]:
    text = unicodedata.normalize("NFKC", text).translate(_DEV_DIGITS)
    toks = []
    for raw in _TOKEN.findall(text):
        if raw == "₹":
            toks.append(Tok("sym", raw))
        elif raw[0].isdigit():
            raw = raw.rstrip(",")
            toks.append(Tok("num", raw, Fraction(Decimal(raw.replace(",", ""))), True))
        elif raw.isascii():
            toks.append(Tok("word", raw.lower()))
        else:
            c = canon(raw)
            if c in SCALES:
                toks.append(Tok("scale", c, Fraction(SCALES[c])))
            elif c in MODIFIERS:
                toks.append(Tok("mod", c, MODIFIERS[c]))
            elif c in FRACTION_NUMBERS:
                toks.append(Tok("num", c, FRACTION_NUMBERS[c]))
            elif c in NUMBER_WORDS:
                toks.append(Tok("num", c, Fraction(NUMBER_WORDS[c])))
            else:
                toks.append(Tok("word", c))
    return toks


class _Builder:
    """Builds one number from consecutive tokens. add() returns False when the next token
    cannot belong to the same number (e.g. two plain numbers in a row), so the caller
    starts a new number."""

    def __init__(self, start: int):
        self.start, self.end = start, start
        self.total = Fraction(0)     # finished big groups (lakh, hazaar ...)
        self.cur: Fraction | None = None
        self.last: str | None = None   # None | num | hundred | big
        self.delta: Fraction | None = None
        self.has_digit = self.has_word = False

    def add(self, t: Tok, i: int) -> bool:
        if t.kind == "mod":
            if self.last not in (None, "big") or self.delta is not None:
                return False
            self.delta = t.value
        elif t.kind == "num":
            if self.last in (None, "big"):
                self.cur = t.value + (self.delta or 0)
                self.delta = None
            elif (self.last == "hundred" and self.delta is None
                  and t.value.denominator == 1 and t.value < 100):
                self.cur += t.value                       # पाँच सौ पच्चीस
            else:
                return False
            self.last = "num"
        else:  # scale
            base = (self.cur if self.cur is not None else Fraction(1)) + (self.delta or 0)
            if t.value == 100:
                if self.last not in (None, "num"):
                    return False
                self.cur, self.last = base * 100, "hundred"
            else:
                if self.last not in (None, "num", "hundred"):
                    return False
                self.total += base * t.value
                self.cur, self.last = None, "big"
            self.delta = None
        if t.digit:
            self.has_digit = True
        else:
            self.has_word = True
        self.end = i + 1
        return True

    def phrase(self) -> Phrase | None:
        if self.last is None:                             # only a dangling modifier
            return None
        style = "words" if not self.has_digit else ("digits" if not self.has_word else "mixed")
        return Phrase(self.total + (self.cur or 0), style, self.start, self.end)


def find_numbers(tokens: list[Tok]) -> list[Phrase]:
    out: list[Phrase] = []
    b: _Builder | None = None
    for i, t in enumerate(tokens):
        if t.kind not in ("num", "scale", "mod"):
            if b and (p := b.phrase()):
                out.append(p)
            b = None
            continue
        if b is None:
            b = _Builder(i)
        if not b.add(t, i):
            if p := b.phrase():
                out.append(p)
            b = _Builder(i)
            b.add(t, i)
    if b and (p := b.phrase()):
        out.append(p)
    return out


def parse_numbers(text: str) -> tuple[list[Tok], list[Phrase]]:
    toks = tokenize(text)
    return toks, find_numbers(toks)


def digit_word_runs(text: str) -> list[str]:
    """Digits spoken one by one ("नौ आठ सात" -> "987", "डबल आठ" -> "88"). Digit tokens inside a
    run count too ("98765 चार"), but a run is only returned if it holds at least one digit WORD."""
    runs: list[str] = []
    cur: list[str] = []
    saw_word = False
    mult = 1

    def flush():
        nonlocal cur, saw_word, mult
        if cur and saw_word:
            runs.append("".join(cur))
        cur, saw_word, mult = [], False, 1

    for t in tokenize(text):
        if t.kind == "word" and t.word in MULTIPLIERS:
            mult = MULTIPLIERS[t.word]
        elif t.kind == "num" and not t.digit and t.word in DIGIT_WORDS:
            cur.append(str(DIGIT_WORDS[t.word]) * mult)
            saw_word, mult = True, 1
        elif t.kind == "num" and t.digit and t.word.isdigit():
            cur.append(t.word * mult)
            mult = 1
        else:
            flush()
    flush()
    return runs