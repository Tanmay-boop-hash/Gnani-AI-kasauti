"""Find the breaking point: same sentences, increasingly bad phone lines, both models.

python sweep.py                                    # generator seed 0, all 6 conditions
python sweep.py --seeds 0 1 2 --conditions noisy   # 3 independent seeds, 10/5/0 dB only
python sweep.py --cases hand                       # the original 10 hand-written sentences
Add --json results/x.json to save every single result.
"""

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

import requests

from voicetest.cases import CASES as HAND_CASES, judge
from voicetest.generate import generate
from voicetest.clients import ApiError, synthesize, transcribe
from voicetest.degrade import degrade

MODELS = ["prisma-v2.5", "prisma-v3.0"]
CONDITIONS = [          # (label, degrade() settings; None = untouched clean audio)
    ("clean",      None),
    ("phone",      dict(telephone=True)),
    ("phone+20dB", dict(telephone=True, snr_db=20)),
    ("phone+10dB", dict(telephone=True, snr_db=10)),
    ("phone+5dB",  dict(telephone=True, snr_db=5)),
    ("phone+0dB",  dict(telephone=True, snr_db=0)),
]

NOISY = {"phone+10dB", "phone+5dB", "phone+0dB"}
RETRY_STATUSES = {429, 500, 502, 503, 504}   # "try again later" kinds of error


def stt(wav, model):
    """transcribe(), retrying server-side hiccups with a growing wait.
    A 400-type error means OUR request is wrong, so it is not retried."""
    for attempt in range(1, 5):
        try:
            return transcribe(wav, model=model, fmt="transcribe")
        except (ApiError, requests.exceptions.RequestException) as e:
            status = getattr(e, "status", None)          # None for timeouts etc.
            transient = status is None or status in RETRY_STATUSES
            if transient and attempt < 4:
                wait = 3 * attempt
                print(f"    {status or type(e).__name__}: retry {attempt}/3 in {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise


def entity_of(name):
    """'phone-digits-s0-01' -> 'phone-digits' (sentence type without seed and number)."""
    return re.sub(r"-s\d+-\d+$", "", name)

def sign_test(b, c):
    """Exact two-sided sign test. b = clips only model A got right, c = only model B.
    Clips both got right (or both wrong) say nothing about which model is better, so
    only these disagreements count. If the models were equal, each disagreement would be
    a fair coin flip; the p-value is how likely a split this lopsided is under that."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def run(cases, seed, conditions, records, errors):
    for name, kind, expected, text in cases:
        print(f"seed {seed}  {name}", flush=True)
        clean = synthesize(text)
        for label, settings in conditions:
            # the noise seed follows the generator seed, so each seed has its own noise
            wav = clean if settings is None else degrade(clean, seed=seed, **settings)
            for model in MODELS:
                try:
                    reply = stt(wav, model)
                except (ApiError, requests.exceptions.RequestException) as e:
                    errors.append((seed, label, model, name, str(e)[:90]))
                    print(f"  ERROR {label} {model}: {str(e)[:90]}", flush=True)
                    continue
                result = judge(kind, expected, reply["transcript"])
                records.append(dict(
                    seed=seed, name=name, entity=entity_of(name), kind=kind,
                    condition=label, model=model, ok=bool(result.ok), failure=result.kind,
                    expected=result.expected, extracted=result.heard,
                    style=result.style, transcript=reply["transcript"],
                ))

def report(records, errors, conditions):
    labels = [c[0] for c in conditions]
    total, passed = Counter(), Counter()
    for r in records:
        total[(r["condition"], r["model"])] += 1
        passed[(r["condition"], r["model"])] += r["ok"]

    print(f"\n{'condition':12}" + "".join(f"{m:>14}" for m in MODELS))
    for label in labels:
        print(f"{label:12}" + "".join(
            f"{str(passed[(label, m)]) + '/' + str(total[(label, m)]):>14}" for m in MODELS))

    print("\nHOW THEY FAILED (condition, model, kind: count)")
    kinds = Counter((r["condition"], r["model"], r["failure"]) for r in records if not r["ok"])
    for (label, model, kind), count in sorted(kinds.items()):
        print(f"  {label:12} {model:12} {kind:16} {count}")

    print("\nFAILED / TOTAL BY SENTENCE TYPE (all conditions above pooled)")
    ent_total, ent_fail = Counter(), Counter()
    for r in records:
        ent_total[(r["entity"], r["model"])] += 1
        ent_fail[(r["entity"], r["model"])] += not r["ok"]
    print(f"  {'type':16}" + "".join(f"{m:>14}" for m in MODELS))
    for ent in sorted({r["entity"] for r in records}):
        print(f"  {ent:16}" + "".join(
            f"{str(ent_fail[(ent, m)]) + '/' + str(ent_total[(ent, m)]):>14}" for m in MODELS))

    print("\nHOW THE ENTITY WAS WRITTEN (kind, style: count per model; all records, passes and failures)")
    styles = Counter((r["kind"], r.get("style", "digits"), r["model"]) for r in records)
    print(f"  {'kind / style':20}" + "".join(f"{m:>14}" for m in MODELS))
    for kind, style in sorted({(k, s) for k, s, _ in styles}):
        print(f"  {kind + ' / ' + style:20}" + "".join(f"{styles[(kind, style, m)]:>14}" for m in MODELS))

    pairs = defaultdict(dict)       # (seed, sentence, condition) -> {model: ok}
    for r in records:
        pairs[(r["seed"], r["name"], r["condition"])][r["model"]] = r["ok"]

    def tally(keys):
        both = only_a = only_b = neither = 0
        for k in keys:
            d = pairs[k]
            if len(d) < 2:          # one model errored out: not a pair
                continue
            a, b = d[MODELS[0]], d[MODELS[1]]
            if a and b:
                both += 1
            elif a:
                only_a += 1
            elif b:
                only_b += 1
            else:
                neither += 1
        return both, only_a, only_b, neither

    print("\nPAIRED COMPARISON (same sentence, same noisy clip, both models)")
    print(f"  {'condition':12}{'both ok':>9}{'only 2.5':>10}{'only 3.0':>10}{'both fail':>11}{'p':>8}")
    for label in labels + ["ALL"]:
        keys = [k for k in list(pairs) if label == "ALL" or k[2] == label]
        both, a, b, neither = tally(keys)
        print(f"  {label:12}{both:>9}{a:>10}{b:>10}{neither:>11}{sign_test(a, b):>8.3f}")

    bad = [r for r in records if not r["ok"]]
    print(f"\nALL FAILURES ({len(bad)})")
    for r in bad:
        print(f"  s{r['seed']} {r['condition']:12} {r['model']:12} {r['name']:22} "
              f"{r['failure']:16} {r['transcript']}")

    print(f"\nAPI ERRORS (not counted as passes): {len(errors)}")
    for seed, label, model, name, msg in errors:
        print(f"  s{seed} {label:12} {model:12} {name:22} {msg}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0], help="generator/noise seeds")
    ap.add_argument("--conditions", choices=["all", "noisy"], default="all")
    ap.add_argument("--cases", choices=["generated", "hand"], default="generated")
    ap.add_argument("--json", help="save every result to this file")
    args = ap.parse_args()

    conditions = [c for c in CONDITIONS if args.conditions == "all" or c[0] in NOISY]
    if args.cases == "hand":
        runs = [(0, HAND_CASES)]
    else:
        runs = [(s, generate(s)) for s in args.seeds]

    records, errors = [], []
    for seed, cases in runs:
        run(cases, seed, conditions, records, errors)
    report(records, errors, conditions)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nsaved {len(records)} results to {args.json}")


if __name__ == "__main__":
    main()