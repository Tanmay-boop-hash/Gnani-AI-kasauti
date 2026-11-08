"""Build a self-contained HTML report from a sweep's --json results. Makes ZERO API calls.

python report.py results/sweep5-modifiers.json
python report.py results/sweep5-modifiers.json --out results/report.html --no-audio

Audio clips are looked up in the local cache (TTS clip + the same seeded degradation the sweep used)
and embedded in the page as base64, so the one HTML file can be opened or shared on its own
(.wav files themselves are git-ignored). Network access is switched off while the report is built:
a clip that is not in the cache is shown as "audio not in cache" instead of costing credits.
"""

import argparse
import base64
import html
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import requests

from analyze_digits import carrier_table
from sweep import CONDITIONS, MODELS, entity_of, sign_test
from voicetest.clients import synthesize
from voicetest.degrade import degrade

# Clips whose failure was traced to the TTS side by listening (not something the code can detect).
CONFIRMED_TTS_FAULTS = {
    "phone-words-s2-02": "Timbre says the digit 8 only three times instead of four (confirmed by listening). "
                         "Both Prisma models transcribe what was actually spoken, so this is not an STT error.",
}

CSS = """
:root{--bg:#fff;--fg:#1c1c1e;--mute:#6b6b70;--line:#d9d9de;--card:#f6f6f8;--a:#1d6fd6;--b:#d9531e;--ok:#1a7f3c;--bad:#c0392b;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#161618;--fg:#ececef;--mute:#9a9aa2;--line:#37373c;--card:#212125;--a:#5aa2f5;--b:#f28a5c;--ok:#4cc16f;--bad:#f06a5c}}
body{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg);max-width:900px;margin:0 auto;padding:24px 16px 64px}
h1{margin:0 0 4px}h2{margin-top:40px;border-bottom:1px solid var(--line);padding-bottom:4px}
.sub,.note{color:var(--mute)}.note{font-size:13px}
table{border-collapse:collapse;margin:12px 0;width:100%}th,td{border:1px solid var(--line);padding:5px 9px;text-align:right}
th:first-child,td:first-child{text-align:left}th{background:var(--card)}
.wrap{overflow-x:auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:12px 0}
.card h3{margin:0 0 6px;font-size:15px}.card p{margin:3px 0}
.ok{color:var(--ok)}.bad{color:var(--bad)}code,.hi{font-family:ui-monospace,Menlo,monospace;font-size:13px}
audio{width:100%;margin-top:6px}
svg text{fill:var(--fg);font-size:12px}.a{stroke:var(--a);fill:var(--a)}.b{stroke:var(--b);fill:var(--b)}
"""

E = html.escape


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "-"


# ---------------------------------------------------------------- numbers
def labels_present(records):
    present = {r["condition"] for r in records}
    return [c[0] for c in CONDITIONS if c[0] in present]


def pass_table(records):
    total, passed = Counter(), Counter()
    for r in records:
        total[(r["condition"], r["model"])] += 1
        passed[(r["condition"], r["model"])] += bool(r["ok"])
    return passed, total


def pairs_of(records):
    pairs = defaultdict(dict)       # (seed, sentence, condition) -> {model: record}
    for r in records:
        pairs[(r["seed"], r["name"], r["condition"])][r["model"]] = r
    return pairs


def paired_rows(records, labels):
    pairs = pairs_of(records)
    rows = []
    for label in labels + ["ALL"]:
        both = only_a = only_b = neither = 0
        for k, d in pairs.items():
            if (label != "ALL" and k[2] != label) or len(d) < 2:
                continue
            a, b = d[MODELS[0]]["ok"], d[MODELS[1]]["ok"]
            if a and b:
                both += 1
            elif a:
                only_a += 1
            elif b:
                only_b += 1
            else:
                neither += 1
        rows.append((label, both, only_a, only_b, neither, sign_test(only_a, only_b)))
    return rows


def type_table(records):
    tot, bad = Counter(), Counter()
    for r in records:
        tot[(r["entity"], r["model"])] += 1
        bad[(r["entity"], r["model"])] += not r["ok"]
    return sorted({r["entity"] for r in records}), tot, bad


def style_table(records):
    c = Counter((r["entity"], r.get("style", "digits"), r["model"]) for r in records)
    return sorted({r["entity"] for r in records}), c


# ---------------------------------------------------------------- html pieces
def table(headers, rows):
    head = "".join(f"<th>{E(str(h))}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="wrap"><table><tr>{head}</tr>{body}</table></div>'


def chart_svg(passed, total, labels):
    rates = [100 * passed[(l, m)] / total[(l, m)] for l in labels for m in MODELS if total[(l, m)]]
    lo = max(0, int(min(rates) // 10 * 10))      # axis floor sits below the lowest point: nothing is clamped
    w, h, ml, mr, mt, mb = 640, 280, 46, 84, 20, 44
    xs = [ml + i * (w - ml - mr) / (len(labels) - 1) for i in range(len(labels))]

    def y(v):
        return mt + (100 - max(lo, v)) / (100 - lo) * (h - mt - mb)

    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="pass rate by condition">']
    for v in range(lo, 101, 10):
        out.append(f'<line x1="{ml}" x2="{w - mr}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="var(--line)"/>'
                   f'<text x="{ml - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v}%</text>')
    for x, lab in zip(xs, labels):
        out.append(f'<text x="{x:.1f}" y="{h - 22}" text-anchor="middle">{E(lab)}</text>')
    for model, cls in zip(MODELS, ("a", "b")):
        vals = [100 * passed[(l, model)] / total[(l, model)] if total[(l, model)] else None for l in labels]
        pts = [(x, y(v)) for x, v in zip(xs, vals) if v is not None]
        out.append(f'<polyline class="{cls}" fill="none" stroke-width="2.5" points="'
                   + " ".join(f"{px:.1f},{py:.1f}" for px, py in pts) + '"/>')
        for (px, py), v in zip(pts, [v for v in vals if v is not None]):
            out.append(f'<circle class="{cls}" cx="{px:.1f}" cy="{py:.1f}" r="3.5"/>')
        last = pts[-1]
        out.append(f'<text x="{last[0] + 9:.1f}" y="{last[1] + 4:.1f}" text-anchor="start" '
                   f'class="{cls}" stroke="none">{model.replace("prisma-", "")} {vals[-1]:.0f}%</text>')
    out.append(f'<text x="{ml}" y="{h - 4}" style="font-size:11px;fill:var(--mute)">'
               f'axis starts at {lo}%</text></svg>')
    return "".join(out)


def audio_html(rec, carriers, enabled):
    if not enabled:
        return ""
    try:
        clean = synthesize(carriers[rec["name"]])
        settings = dict(CONDITIONS)[rec["condition"]]
        wav = clean if settings is None else degrade(clean, seed=rec["seed"], **settings)
        data = base64.b64encode(Path(wav).read_bytes()).decode()
    except Exception as e:                      # not cached, or no sentence known: never fatal, never paid
        return f'<p class="note">audio not available ({E(type(e).__name__)})</p>'
    return f'<audio controls preload="none" src="data:audio/wav;base64,{data}"></audio>'


def heard_line(rec):
    cls = "ok" if rec["ok"] else "bad"
    v = rec["model"].replace("prisma-", "")
    return (f'<p><b>{v}</b> <span class="{cls}">{"pass" if rec["ok"] else E(rec["failure"])}</span> '
            f'<span class="hi">{E(rec["transcript"])}</span></p>')


def card(title, recs, carriers, audio, note=""):
    exp = E(str(recs[0]["expected"]))
    body = "".join(heard_line(r) for r in sorted(recs, key=lambda r: r["model"]))
    return (f'<div class="card"><h3>{E(title)}</h3><p class="note">expected <span class="hi">{exp}</span>'
            f'{" · " + E(note) if note else ""}</p>{body}{audio_html(recs[0], carriers, audio)}</div>')


def pick_examples(records, labels):
    head = "phone+0dB" if "phone+0dB" in labels else labels[-1]
    only_a, only_b = [], []
    for k, d in sorted(pairs_of(records).items()):
        if k[2] != head or len(d) < 2:
            continue
        a, b = d[MODELS[0]], d[MODELS[1]]
        if a["ok"] and not b["ok"]:
            only_a.append((a, b))
        elif b["ok"] and not a["ok"]:
            only_b.append((a, b))
    seen, picked = set(), []
    for a, b in only_a:                         # one example per sentence type
        if a["entity"] not in seen:
            seen.add(a["entity"])
            picked.append((a, b))
    return head, picked[:7], only_b[:2]


# ---------------------------------------------------------------- the page
def build_html(records, source="", audio=True):
    labels = labels_present(records)
    carriers = carrier_table(records)
    passed, total = pass_table(records)
    seeds = sorted({r["seed"] for r in records})
    sentences = len({(r["seed"], r["name"]) for r in records})
    parts = [f"<h1>Gnani.ai-kasauti: report</h1>",
             f'<p class="sub">{len(records)} results · {sentences} sentences · seeds {", ".join(map(str, seeds))} · '
             f'{len(labels)} audio conditions · Prisma v2.5 and v3.0 · built {date.today().isoformat()} from '
             f'<code>{E(source)}</code></p>',
             '<p class="note">Scope: synthetic Hindi (hi-IN) sentences spoken by one Timbre v3.0 voice, damaged with '
             'seeded white noise plus a simulated phone line (8 kHz, 300-3400 Hz, approximate mu-law), '
             'transcribed with <code>format=transcribe</code>. White noise is not real call noise, and clean TTS from '
             'Gnani\'s own Timbre may be unusually easy for Prisma. Read every number inside that scope.</p>']

    parts.append("<h2>1. Pass rate by condition</h2>")
    rows = []
    for l in labels:
        rows.append([E(l)] + [f"{passed[(l, m)]}/{total[(l, m)]} ({pct(passed[(l, m)], total[(l, m)])})" for m in MODELS])
    parts.append(chart_svg(passed, total, labels))
    parts.append(table(["condition"] + MODELS, rows))

    parts.append("<h2>2. Paired comparison: which model is better?</h2>")
    prow = [[E(l), b, oa, ob, n, f"{p:.4f}" if p >= 0.0001 else "&lt; 0.0001"]
            for l, b, oa, ob, n, p in paired_rows(records, labels)]
    parts.append(table(["condition", "both ok", "only v2.5 ok", "only v3.0 ok", "both fail", "p (sign test)"], prow))
    parts.append('<p class="note">Same sentence, same noisy clip, both models. Only the clips where the models disagree '
                 'count: if they were equally good each disagreement would be a coin flip, and p is how likely a split '
                 'this lopsided is by luck. p below 0.05 means "unlikely to be chance" and says nothing about effect '
                 'size or about other noise types. The ALL row pools correlated clips (the same sentence at several '
                 'noise levels) and is optimistic: quote the per-condition rows.</p>')

    parts.append("<h2>3. Which sentence types fail</h2>")
    ents, tot, bad = type_table(records)
    parts.append(table(["sentence type (all conditions pooled)"] + [f"{m} failed/total" for m in MODELS],
                       [[E(e)] + [f"{bad[(e, m)]}/{tot[(e, m)]}" for m in MODELS] for e in ents]))

    parts.append("<h2>4. How each model wrote the entity</h2>")
    ents, st = style_table(records)
    parts.append(table(["sentence type"] + [f"{m} digits / mixed / words" for m in MODELS],
                       [[E(e)] + [" / ".join(str(st[(e, s, m)]) for s in ("digits", "mixed", "words")) for m in MODELS]
                        for e in ents]))
    parts.append('<p class="note">The scorer judges the value, not the writing style, so a number written as words still '
                 'passes if it is right. "mixed" is digits plus a scale word (50 लाख). A clip where nothing could be '
                 'extracted is counted under digits.</p>')

    parts.append("<h2>5. Failures with no noise: who is at fault?</h2>")
    clean_bad = defaultdict(list)
    for r in records:
        if r["condition"] == "clean" and not r["ok"]:
            clean_bad[(r["seed"], r["name"])].append(r)
    if not clean_bad:
        parts.append("<p>No failures on clean audio.</p>")
    for (seed, name), recs in sorted(clean_bad.items()):
        if name in CONFIRMED_TTS_FAULTS:
            parts.append(card(f"{name} (seed {seed}), clean audio: TTS FAULT", recs, carriers, audio,
                              CONFIRMED_TTS_FAULTS[name]))
        else:
            parts.append(card(f"{name} (seed {seed}), clean audio", recs, carriers, audio,
                              "no noise involved: a formatting behaviour or a model quirk, not noise"))

    head, picked, rev = pick_examples(records, labels)
    parts.append(f"<h2>6. Examples at {E(head)}</h2>")
    parts.append(f'<p class="note">Same clip played to both models. The audio on each card is the damaged clip they heard. '
                 f'First: one example per sentence type where only v3.0 failed. Last: clips where only v2.5 failed.</p>')
    for a, b in picked:
        parts.append(card(f"{a['name']} (seed {a['seed']}): only v3.0 failed", [a, b], carriers, audio))
    for a, b in rev:
        parts.append(card(f"{a['name']} (seed {a['seed']}): only v2.5 failed", [a, b], carriers, audio))

    parts.append("<h2>7. Limits</h2><ul>"
                 "<li>White noise only; real calls have babble, traffic and codec artefacts.</li>"
                 "<li>mu-law here is an approximation of G.711, not bit-exact.</li>"
                 "<li>One TTS voice, one language, one STT format; TTS speech from Gnani's own model may be easier than "
                 "real callers.</li>"
                 "<li>A text mismatch alone does not say whether TTS or STT was at fault; only failures on clean audio "
                 "can be separated, and only one was confirmed by listening.</li>"
                 "<li>The cache can serve stale answers if a model is silently updated under the same name.</li></ul>")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Gnani.ai-kasauti report</title><style>{CSS}</style></head><body>' + "\n".join(parts)
            + "</body></html>")


def _no_network(*a, **k):
    raise RuntimeError("report.py makes no API calls: this clip is not in the local cache")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("json_path")
    ap.add_argument("--out", default="results/report.html")
    ap.add_argument("--no-audio", action="store_true", help="skip embedding audio (much smaller file)")
    args = ap.parse_args()
    requests.post = _no_network          # a cache miss must fail, never spend credits
    records = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    page = build_html(records, source=Path(args.json_path).name, audio=not args.no_audio)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size / 1024:.0f} KB, {page.count('<audio')} audio clips)")


if __name__ == "__main__":
    main()