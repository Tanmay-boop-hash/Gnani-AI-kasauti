"""Digit-level error analysis of a sweep's --json results (digit-string sentences only).

python analyze_digits.py results/sweep3-multiseed.json
python analyze_digits.py results/sweep4-all-conditions.json --conditions phone+0dB
"""

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from voicetest.compare import normalize

NOISY = ["phone+10dB", "phone+5dB", "phone+0dB"]
NO_NOISE = ["clean", "phone", "phone+20dB"]      # failures here point at TTS or the comparer

def heard_digits(transcript):
    """Every digit in the transcript, in order. Our digit sentences contain no other numbers. (Limit: a spoken +91 prefix would show up as two extra digits.)"""
    return re.sub(r"\D", "", normalize(transcript))

def fillers_in_digit_span(transcript):
    """Non-digit words sitting between the first and last digit, e.g. 'था' in '5540 था 114'."""
    t = normalize(transcript)
    idx = [k for k, c in enumerate(t) if c.isdigit()]
    if len(idx) < 2:
        return []
    span = t[idx[0]: idx[-1] + 1] 
    tokens = re.findall(r"\d+|[^\d\s]+", span)
    return [tok for tok in tokens 
            if not any(c.isdigit() for c in tok)
            and any(unicodedata.category(c)[0] in "LM" for c in tok)]

def align(expected, heard):
    """Minimum-edit alignment of two digit strings.
    Returns a list of (op, expected_index, expected_digit, heard_digit):
      match / sub : a digit was heard (correctly / as a different digit)
      del         : an expected digit is missing (heard_digit is None)
      ins         : an extra heard digit (expected_index = the position it appears before)
    When several alignments are equally good (e.g. one 8 lost from '888'), ties prefer
    match/sub, then del, then ins, so results are deterministic but not unique."""
    n, m = len(expected), len(heard)
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cost[i][0] = i
    for j in range(1, m + 1):
        cost[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost[i][j] = min(
                cost[i - 1][j - 1] + (expected[i - 1] != heard[j - 1]),
                cost[i - 1][j] + 1,
                cost[i][j - 1] + 1,
            )
    ops, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and cost[i][j] == cost[i - 1][j - 1] + (expected[i - 1] != heard[j - 1]):
            op = "match" if expected[i - 1] == heard[j - 1] else "sub"
            ops.append((op, i - 1, expected[i - 1], heard[j - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and cost[i][j] == cost[i - 1][j] + 1:
            ops.append(("del", i - 1, expected[i - 1], None))
            i -= 1
        else:
            ops.append(("ins", i, None, heard[j - 1]))
            j -= 1
    ops.reverse()
    return ops


def enrich(r):
    exp = r["expected"]
    heard = heard_digits(r["transcript"])
    # a clip the comparer accepted (e.g. with a +91 prefix) counts as fully correct
    ops = [("match", i, d, d) for i, d in enumerate(exp)] if r["ok"] else align(exp, heard)
    return dict(r, exp=exp, heard=heard, ops=ops)


def report(records, conditions, top):
    digit_all = [enrich(r) for r in records if r["kind"] == "digits"]
    use = [r for r in digit_all if r["condition"] in conditions]
    if not use:
        print("no digit-string records for those conditions")
        return
    models = sorted({r["model"] for r in use})
    head = "".join(f"{m:>16}" for m in models)
    print(f"digit-string clips analysed: {len(use)}   conditions: {', '.join(conditions)}")

    # 1. what kind of edits
    stats = {m: Counter() for m in models}
    for r in use:
        s = stats[r["model"]]
        s["clips"] += 1
        if r["ok"]:
            continue
        s["failed clips"] += 1
        c = Counter(o[0] for o in r["ops"])
        s["digits substituted"] += c["sub"]
        s["digits missing"] += c["del"]
        s["digits extra"] += c["ins"]
        present = tuple(k for k in ("sub", "del", "ins") if c[k])
        label = {("sub",): "only substitutions", ("del",): "only missing digits",
                 ("ins",): "only extra digits", (): "no edit found"}.get(present, "mixed edits")
        s["  " + label] += 1
    print("\n1. WHAT KIND OF EDITS")
    print(f"  {'':24}{head}")
    for key in ["clips", "failed clips", "  only substitutions", "  only missing digits",
                "  only extra digits", "  mixed edits", "  no edit found",
                "digits substituted", "digits missing", "digits extra"]:
        if any(stats[m][key] for m in models) or key in ("clips", "failed clips"):
            print(f"  {key:24}" + "".join(f"{stats[m][key]:>16}" for m in models))

    # 2. position
    print("\n2. WHERE IN THE STRING  (digits substituted or missing, counted per expected position)")
    for L in sorted({len(r["exp"]) for r in use}):
        print(f"  length {L}            position" + "".join(f"{i + 1:>4}" for i in range(L)))
        for m in models:
            clips = [r for r in use if r["model"] == m and len(r["exp"]) == L]
            errs = Counter(o[1] for r in clips for o in r["ops"] if o[0] in ("sub", "del"))
            print(f"    {m:12} n={len(clips):<5}      " + "".join(f"{errs[i]:>4}" for i in range(L)))
    print("\n  first / middle / last digit   (missing | substituted)")
    for m in models:
        c = Counter()
        for r in use:
            if r["model"] != m:
                continue
            L = len(r["exp"])
            for o in r["ops"]:
                if o[0] in ("sub", "del"):
                    where = "first" if o[1] == 0 else "last" if o[1] == L - 1 else "middle"
                    c[(o[0], where)] += 1
        print(f"    {m:12} first {c[('del', 'first')]} | {c[('sub', 'first')]}    "
              f"middle {c[('del', 'middle')]} | {c[('sub', 'middle')]}    "
              f"last {c[('del', 'last')]} | {c[('sub', 'last')]}")

    # 3. confusion
    print(f"\n3. MOST COMMON SUBSTITUTIONS (expected->heard), top {top}")
    for m in models:
        c = Counter((o[2], o[3]) for r in use if r["model"] == m for o in r["ops"] if o[0] == "sub")
        line = "  ".join(f"{e}->{h} x{n}" for (e, h), n in c.most_common(top))
        print(f"  {m} ({sum(c.values())} total): {line}")

    # 4. per digit
    print("\n4. ERROR RATE BY EXPECTED DIGIT  (substituted or missing / times it was spoken)")
    for m in models:
        occ = Counter(d for r in use if r["model"] == m for d in r["exp"])
        err = Counter(o[2] for r in use if r["model"] == m for o in r["ops"] if o[0] in ("sub", "del"))
        print(f"  {m:12}" + "  ".join(f"{d}:{err[d]}/{occ[d]}" for d in "0123456789"))

    # 5. length and repeats
    print("\n5. FAILED / TOTAL CLIPS BY STRING LENGTH, AND BY REPEATED ADJACENT DIGITS")
    for m in models:
        parts = []
        for L in sorted({len(r["exp"]) for r in use}):
            cl = [r for r in use if r["model"] == m and len(r["exp"]) == L]
            parts.append(f"len {L}: {sum(not r['ok'] for r in cl)}/{len(cl)}")
        for label, has in (("has repeat", True), ("no repeat", False)):
            cl = [r for r in use if r["model"] == m and bool(re.search(r"(\d)\1", r["exp"])) == has]
            parts.append(f"{label}: {sum(not r['ok'] for r in cl)}/{len(cl)}")
        print(f"  {m:12}" + "   ".join(parts))

    # 6. filler words
    print("\n6. FILLER WORDS INSIDE THE DIGITS (failed clips)")
    for m in models:
        failed = [r for r in use if r["model"] == m and not r["ok"]]
        words = Counter(w for r in failed for w in fillers_in_digit_span(r["transcript"]))
        with_f = sum(bool(fillers_in_digit_span(r["transcript"])) for r in failed)
        print(f"  {m:12} {with_f}/{len(failed)} failed clips   "
              + "  ".join(f"{w} x{n}" for w, n in words.most_common(top)))

    # 7. same wrong answer repeated
    print("\n7. SAME WRONG DIGITS REPEATED (>= 3 failed results with the identical heard string)")
    groups = defaultdict(list)
    for r in use:
        if not r["ok"]:
            groups[(r["seed"], r["name"], r["heard"])].append(r)
    repeated = sorted((kv for kv in groups.items() if len(kv[1]) >= 3), key=lambda kv: -len(kv[1]))
    for (seed, name, heard), recs in repeated[:top]:
        conds = ", ".join(sorted({x["condition"] for x in recs}))
        print(f"  s{seed} {name:22} expected {recs[0]['exp']}  heard {heard}  "
              f"x{len(recs)}  models {len({x['model'] for x in recs})}  [{conds}]")
    if not repeated:
        print("  none")

    # 8. failures without noise
    base = [r for r in digit_all if r["condition"] in NO_NOISE]
    print(f"\n8. FAILURES WITHOUT NOISE ({', '.join(NO_NOISE)})")
    if not base:
        print("  this file has no clean/phone/20dB records, so TTS faults cannot be separated yet")
    else:
        by_seed = Counter(r["seed"] for r in base)
        print(f"  {len(base)} clips, per seed {dict(sorted(by_seed.items()))}")
        bad = [r for r in base if not r["ok"]]
        for r in bad:
            print(f"  s{r['seed']} {r['condition']:12} {r['model']:12} {r['name']:22} "
                  f"expected {r['exp']}  heard {r['heard']}")
        if not bad:
            print("  none failed")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("json_path")
    ap.add_argument("--conditions", nargs="+", default=NOISY)
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()
    records = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    report(records, args.conditions, args.top)


if __name__ == "__main__":
    main()