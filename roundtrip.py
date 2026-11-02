from voicetest.clients import synthesize, transcribe
from voicetest.cases import CASES, judge

# (model, output style) combinations to compare on the SAME audio
CONFIGS = [
    ("prisma-v2.5", "transcribe"),
    ("prisma-v3.0", "transcribe"),
]


passed = {cfg: 0 for cfg in CONFIGS}
for name, kind, expected, text in CASES:
    wav = synthesize(text)                      # same audio for every config
    print(f"\n{name}  (expected {expected})")
    for model, fmt in CONFIGS:
        reply = transcribe(wav, model=model, fmt=fmt)
        if reply.get("model") != model:         # verify, don't assume
            print(f"  WARNING: asked for {model}, server says {reply.get('model')}")
        result = judge(kind, expected, reply["transcript"])
        passed[(model, fmt)] += result.ok
        flag = "PASS" if result.ok else "FAIL"
        print(f"  {flag} {model:12} {fmt:10} {result.kind:16} {reply['transcript']}")

print("\nSUMMARY")
for (model, fmt), n in passed.items():
    print(f"  {model} / {fmt}: {n}/{len(CASES)} passed")