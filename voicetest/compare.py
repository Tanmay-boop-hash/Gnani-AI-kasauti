from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
import math

from .hindi_numbers import canon, digit_word_runs, parse_numbers, tokenize

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

@dataclass(frozen=True)
class Result:
    ok: bool                 # did the entity survive the round trip?
    kind: str                # match | not_found | length_mismatch | substitution | wrong_value
                             # | wrong_period | missing_period   (times only)
    expected: str            # what we said
    heard: str | None        # what we extracted from the transcript
    style: str = "digits"    # how the model wrote it: digits | mixed (50 लाख) | words

def normalize(text: str) -> str:
    """
    Normalize text for comparison:
    - convert Devanagari digits to ASCII digits
    - normalize Unicode to NFKC
    - replace "|" with space (for Google TTS)
    - collapse whitespace
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_DEVANAGARI_DIGITS)
    text = text.replace("|", " ")
    text = re.sub(r"\s+", " ", text)  
    return text.strip()

# digit strings: phone numbers, pin codes, IDs
def _longest_digit_run(text: str) -> str | None:
    runs = re.findall(r"\d(?:[\s\-]?\d)+", text)
    if not runs:
        return None
    digits = [re.sub(r"\D", "", r) for r in runs]
    return max(digits, key=len)

def _judge_digits(exp: str, got: str, style: str) -> Result:
    if got != exp and got.endswith(exp) and got[: len(got) - len(exp)] in ("91", "0"):
        got = exp          # tolerate +91 / leading 0
    if got == exp:
        return Result(True, "match", exp, got, style)
    if len(got) != len(exp):
        return Result(False, "length_mismatch", exp, got, style)
    return Result(False, "substitution", exp, got, style)

def compare_digits(expected: str, heard_text: str) -> Result:
    exp = re.sub(r"\D", "", expected)
    results = []
    got = _longest_digit_run(normalize(heard_text))
    if got is not None:
        r = _judge_digits(exp, got, "digits")
        if r.ok:
            return r
        results.append(r)
    runs = digit_word_runs(heard_text)            # digits spoken as words (verbatim format)
    if runs:
        r = _judge_digits(exp, max(runs, key=len), "words")
        if r.ok:
            return r
        results.append(r)
    if not results:
        return Result(False, "not_found", exp, None)
    return max(results, key=lambda r: len(r.heard))   # ties keep the digits result

# rupee amounts
_AMOUNT_WITH_SYMBOL = re.compile(r"(?:₹|rs\.?|inr)\s*(\d[\d,]*(?:\.\d+)?)", re.IGNORECASE)
_ANY_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

def _amount_digits(expected: int | str, heard_text: str) -> Result:
    """The original digits-only amount check."""
    exp = Decimal(str(expected))
    text = normalize(heard_text)
    m = _AMOUNT_WITH_SYMBOL.search(text)
    if m: 
        raw = m.group(1)
    else:
        n = _ANY_NUMBER.search(text)
        raw = n.group(0) if n else None
    if raw is None:
        return Result(False, "not_found", str(exp), None)
    got = Decimal(raw.replace(",", "").rstrip("."))
    if got == exp:
        return Result(True, "match", str(exp), str(got))
    return Result(False, "wrong_value", str(exp), str(got))

def _fmt(v: Fraction) -> str:
    return format((Decimal(v.numerator) / Decimal(v.denominator)).normalize(), "f")

def _is_rupee_marker(t) -> bool:
    if t.kind == "sym":
        return True
    return t.kind == "word" and (t.word.startswith(("रुप", "रूप")) or t.word in {"rs", "inr", "rupee", "rupees"})

def _pick_amount_phrase(toks, phrases):
    """The number right before/after a rupee marker; else the first number that has a digit or
    a scale word (so a bare "दो" in "भेज दो" is never taken for an amount)."""
    for p in phrases:
        before = p.end < len(toks) and _is_rupee_marker(toks[p.end])
        after = p.start > 0 and _is_rupee_marker(toks[p.start - 1])
        if before or after:
            return p
    for p in phrases:
        if any(t.digit or t.kind == "scale" for t in toks[p.start:p.end]):
            return p
    return None

def compare_amount(expected: int | str, heard_text: str) -> Result:
    old = _amount_digits(expected, heard_text)
    if old.ok:
        return old                              # digits already right: untouched
    toks, phrases = parse_numbers(heard_text)
    p = _pick_amount_phrase(toks, phrases)
    if p is None:
        return old
    exp = Decimal(str(expected))
    if p.value == Fraction(exp):
        return Result(True, "match", str(exp), _fmt(p.value), p.style)
    return Result(False, "wrong_value", str(exp), _fmt(p.value), p.style)

# clock times
_TIME = re.compile(r"(\d{1,2})\s*[:.]\s*(\d{2})")
_AM_WORDS = {canon(w) for w in ("सुबह", "सवेरे", "प्रातः", "भोर")}
_PM_WORDS = {canon(w) for w in ("शाम", "दोपहर", "अपराह्न")}
_NIGHT_WORDS = {canon(w) for w in ("रात", "रात्रि")}
_SUFFIX = re.compile(r"(?<![a-z])([ap])\.?\s?m\b\.?")

def _period_indicators(toks, text: str) -> list[str]:
    ind = []
    for t in toks:
        if t.kind == "word":
            if t.word in _AM_WORDS:
                ind.append("am")
            elif t.word in _PM_WORDS:
                ind.append("pm")
            elif t.word in _NIGHT_WORDS:
                ind.append("night")
    ind += [m.group(1) + "m" for m in _SUFFIX.finditer(normalize(text).lower())]
    return ind

def _period_ok(indicator: str, h24: int) -> bool:
    if indicator == "am":
        return h24 < 12
    if indicator == "pm":
        return h24 >= 12
    return h24 >= 18 or h24 <= 5          # night

def _style_of(*phrases) -> str:
    return "words" if all(p.style == "words" for p in phrases) else "mixed"

def _extract_time(text: str, toks, phrases):
    """-> (hour, minute, style) or None. Tries 9:30 / 9.30, then '<h> बजकर <m> मिनट',
    then 'साढ़े/सवा/पौने/डेढ़/ढाई <h> बजे' and plain '<h> बजे'."""
    m = _TIME.search(normalize(text))
    if m:
        return int(m.group(1)), int(m.group(2)), "digits"
    for i, t in enumerate(toks):
        if t.kind == "word" and t.word == canon("बजकर"):
            hp = next((p for p in phrases if p.end == i), None)
            mp = next((p for p in phrases if p.start == i + 1), None)
            if hp and mp and hp.value.denominator == 1 and mp.value.denominator == 1:
                return int(hp.value), int(mp.value), _style_of(hp, mp)
    for i, t in enumerate(toks):
        if t.kind == "word" and t.word == canon("बजे"):
            hp = next((p for p in phrases if p.end == i), None)
            if hp and hp.value < 24:
                h = math.floor(hp.value)
                minutes = (hp.value - h) * 60
                if minutes.denominator == 1:
                    return h, int(minutes), _style_of(hp)
    return None

def compare_time(expected: tuple[int, int], heard_text: str, require_period: bool = True) -> Result:
    exp_h, exp_m = expected
    exp_str = f"{exp_h:02d}:{exp_m:02d}"
    toks, phrases = parse_numbers(heard_text)
    found = _extract_time(heard_text, toks, phrases)
    if found is None:
        return Result(False, "not_found", exp_str, None)
    got_h, got_m, style = found
    got_str = f"{got_h:02d}:{got_m:02d}"
    if got_m != exp_m or got_h % 12 != exp_h % 12:
        return Result(False, "wrong_value", exp_str, got_str, style)
    indicators = _period_indicators(toks, heard_text)
    if any(not _period_ok(i, exp_h) for i in indicators):
        return Result(False, "wrong_period", exp_str, got_str, style)      # e.g. सुबह 7:45 pm
    if not indicators and require_period:
        return Result(False, "missing_period", exp_str, got_str, style)
    return Result(True, "match", exp_str, got_str, style)