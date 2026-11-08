"""Re-score a saved sweep JSON with the CURRENT comparer. Zero API calls.

python rejudge.py results/sweep4-all-conditions.json
python rejudge.py results/sweep4-all-conditions.json --json results/sweep4-rejudged.json

The stored transcripts are re-judged against the expected values rebuilt from the sentence
name (generate(seed) for generated sentences, cases.CASES for the hand-written ones).
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from sweep import CONDITIONS, report
from voicetest.cases import CASES as HAND_CASES, judge
from voicetest.generate import generate


def expected_table(seeds):
    table = {name: (kind, expected) for name, kind, expected, _ in HAND_CASES}
    for seed in seeds:
        for name, kind, expected, _ in generate(seed):
            table[name] = (kind, expected)
    return table


def rejudge(records):
    table = expected_table(sorted({r["seed"] for r in records}))
    out, moves = [], []
    for r in records:
        if r["name"] not in table:
            raise SystemExit(f"{r['name']!r} is not produced by generate(seed {r['seed']}) or the hand cases: ""the generator changed since this JSON was made, so it cannot be re-judged safely.")
        kind, expected = table[r["name"]]
        if kind != r["kind"]:
            raise SystemExit(f"{r['name']}: kind {kind!r} now, {r['kind']!r} in the file")
        res = judge(kind, expected, r["transcript"])
        new = dict(r, ok=bool(res.ok), failure=res.kind, expected=res.expected,
                   extracted=res.heard, style=res.style)
        if (new["ok"], new["failure"]) != (r["ok"], r["failure"]):
            moves.append((r, new))
        out.append(new)
    return out, moves


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("json_in")
    ap.add_argument("--json", help="save the re-judged records here")
    args = ap.parse_args()

    records = json.loads(Path(args.json_in).read_text(encoding="utf-8"))
    new_records, moves = rejudge(records)

    print(f"re-judged {len(records)} records; {len(moves)} changed verdict or failure kind")
    flows = Counter((("pass" if o["ok"] else "fail"), ("pass" if n["ok"] else "fail"),
                     o["failure"], n["failure"]) for o, n in moves)
    for (a, b, ka, kb), c in sorted(flows.items()):
        print(f"  {a}->{b}  {ka} -> {kb}: {c}")
    worse = [(o, n) for o, n in moves if o["ok"] and not n["ok"]]
    print(f"\nPASS -> FAIL (the comparer is now stricter here): {len(worse)}")
    for o, n in worse[:30]:
        print(f"  s{n['seed']} {n['condition']:12} {n['model']:12} {n['name']:22} {n['failure']:15} {n['transcript']}")

    present = {r["condition"] for r in new_records}
    conditions = [c for c in CONDITIONS if c[0] in present]
    print("\n" + "=" * 70 + "\nREPORT WITH THE UPGRADED COMPARER\n" + "=" * 70)
    report(new_records, [], conditions)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(new_records, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nsaved {len(new_records)} results to {args.json}")


if __name__ == "__main__":
    main()