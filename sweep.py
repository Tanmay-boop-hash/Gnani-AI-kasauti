"""Find the breaking point: same sentences, increasingly bad phone lines, both models."""
import time
from collections import Counter

import requests

from voicetest.cases import CASES, judge
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


passed = Counter()
kinds = Counter()
failures = []
errors = []
for name, kind, expected, text in CASES:
    print(name, flush=True)
    clean = synthesize(text)
    for label, settings in CONDITIONS:
        wav = clean if settings is None else degrade(clean, **settings)
        for model in MODELS:
            try:
                reply = stt(wav, model)
            except (ApiError, requests.exceptions.RequestException) as e:
                errors.append((label, model, name, str(e)[:90]))
                print(f"  ERROR {label} {model}: {str(e)[:90]}", flush=True)
                continue
            result = judge(kind, expected, reply["transcript"])
            passed[(label, model)] += result.ok
            if not result.ok:
                kinds[(label, model, result.kind)] += 1
                failures.append((label, model, name, result.kind, reply["transcript"]))

n = len(CASES)
print(f"\n{'condition':12}" + "".join(f"{m:>14}" for m in MODELS))
for label, _ in CONDITIONS:
    print(f"{label:12}" + "".join(f"{passed[(label, m)]:>11}/{n}" for m in MODELS))

print("\nHOW THEY FAILED (condition, model, kind: count)")
for (label, model, kind), count in sorted(kinds.items()):
    print(f"  {label:12} {model:12} {kind:16} {count}")

print("\nFIRST 20 FAILURES")
for label, model, name, kind, heard in failures[:20]:
    print(f"  {label:12} {model:12} {name:14} {kind:16} {heard}")

print(f"\nAPI ERRORS (not counted as passes): {len(errors)}")
for label, model, name, msg in errors:
    print(f"  {label:12} {model:12} {name:14} {msg}")