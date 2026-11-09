

https://github.com/user-attachments/assets/cf9e1e0c-b499-4e5f-ad70-15ba320ad7e8



# Gnani.ai-kasauti

> 📄 **[Download 1-Page Solution Pitch (PDF)](Kasauti_Solution_Pitch.pdf)** &bull;
> 📖 **[Read Solution Pitch (Markdown)](SOLUTION_PITCH.md)** &bull;
> 📊 **[Interactive HTML Report](results/report.html)**

*kasauti* = touchstone. A regression test for Indian-language voice AI.

It makes Gnani's **Timbre** TTS speak sentences containing **known** phone numbers, PINs, rupee amounts and times, damages the audio like a bad phone call (noise, 8 kHz, mu-law), sends it to Gnani's **Prisma** STT, and scores whether each entity survived. Because the right answer is known, no manual labelling is needed, and any model version can be re-tested the same way.

> Built for the Great Indian AI Internship Challenge (Gnani AI). **Synthetic data only**: no real phone numbers, account numbers or recorded calls anywhere in this repo.

```
seeded sentence -> Timbre TTS -> damage the audio -> Prisma v2.5 and v3.0 -> entity comparer -> pass/fail + failure kind
      (cached)        (cached)        (seeded, cached)        (cached)
```

## What it found

Setup: 52 sentences per seed x 3 seeds = 156 sentences, 6 audio conditions, both Prisma models, `format=transcribe`, Hindi (`hi-IN`), one Timbre voice. Full results: [`results/`](results/).

| condition | Prisma v2.5 | Prisma v3.0 |
|---|---|---|
| clean | 155/156 | 153/156 |
| phone line only | 155/156 | 154/156 |
| phone + 20 dB noise | 155/156 | 154/156 |
| phone + 10 dB | 151/156 | 153/156 |
| phone + 5 dB | 151/156 | 147/156 |
| phone + 0 dB | 144/156 | 125/156 |

- **The phone-line damage alone did not break either model** on this test set. Noise did: failures start around 10 dB and grow toward 0 dB.
- **At 0 dB, v2.5 held up better than v3.0** (paired: 21 clips only v2.5 got right, 2 only v3.0, exact sign test p < 0.001; the direction held in every seed). At 10 dB and 5 dB there is no measurable difference (p = 0.625 and 0.289). Prisma v3.0 is marketed for phone audio and white noise is not phone-call noise, so this is **not** a claim that v3.0 is worse in general.
- **Digit strings are the fragile entity**: 62 of the 75 failed results are phone numbers, PINs or account numbers (12 of those are the single TTS-fault clip below, repeated across conditions; without it, 50 of 63). Amounts and times mostly survived.
- **Which digits break** (540 noisy digit clips per model): the digit 6 is the most fragile in both models (often heard as 7); v3.0 additionally turns 1 into 8, which v2.5 did not. v3.0's extra errors are substituted digits; missing digits are about equal. Details: [`results/digit-analysis-sweep5.txt`](results/digit-analysis-sweep5.txt).
- **Filler words**: 7 of 20 (v2.5) and 6 of 35 (v3.0) failed digit clips contain a word that was not spoken, most often `था`; no passing clip does. Most failures are still substituted or missing digits.
- **Who is at fault, the TTS or the STT?** One clean-audio failure (`phone-words-s2-02`) failed identically in both models; listening to the clip confirmed that Timbre itself spoke the digit 8 three times instead of four. Failures on clean audio are the only ones where this can be separated.
- **Writing-style quirks** (not hearing errors): on clean audio v3.0 appended "pm" to two morning times (`सुबह 7:45 pm`); at 0 dB it twice wrote the hybrid `शाम सवा 5:00 बजे` for "quarter past five", which the scorer counts as wrong. v2.5 wrote 18 of the time clips as words, v3.0 only 2.

**Read these in scope:** white noise only, mu-law is an approximation of G.711, clean TTS from Gnani's own Timbre may be unusually easy for Prisma, one voice, one language, 3 seeds. Failures at several noise levels of the same sentence are correlated, so the "ALL" row of the paired table is optimistic.

## How the scoring works

`voicetest/compare.py` judges the *value*, not the writing:

- **digits** (phones, PINs, account numbers): tolerates spaces, hyphens, `+91`, Devanagari digits and digits spoken as words; failure kinds `length_mismatch`, `substitution`, `not_found`.
- **amounts**: `₹5,00,000`, `5,00,000 रुपये`, `50 लाख`, `पाँच लाख`, `सवा लाख` all parse to the same exact number (`voicetest/hindi_numbers.py`).
- **times**: `9:30`, `साढ़े नौ बजे`, `सवा`, `पौने`, `डेढ़`, `ढाई`, `शाम पाँच बजकर पंद्रह मिनट`. A contradicting period (`सुबह 7:45 pm`) is `wrong_period`; no period word at all is `missing_period` (a failure, never a silent pass).
- every result records the **style** the model used (digits / mixed / words).

The 0-99 Hindi number-word table was written by hand and is checked only for internal consistency.

## Install and run

```bash
pip install -r requirements.txt          # requests, python-dotenv, numpy, scipy (+ pytest to run the tests)
echo "GNANI_API_KEY=your_key_here" > .env   # never commit this file
pytest -q                                # no API calls, no credits
```

```bash
python roundtrip.py                                              # 10 hand-written sentences, clean audio, both models
python sweep.py --seeds 0 1 2 --json results/sweep.json          # the full test matrix
python sweep.py --seeds 0 1 2 --conditions noisy --json results/noisy.json   # only 10 / 5 / 0 dB
python rejudge.py results/sweep.json                             # re-score saved transcripts offline (no API calls)
python analyze_digits.py results/sweep.json                      # digit-level error analysis
python report.py results/sweep.json                              # self-contained HTML report with audio playback
```

Every API result is cached in `.cache/` under a hash of all its inputs, so re-runs are free; noise is seeded, so the same inputs give byte-identical audio. Gnani allows one active request at a time, so the runner is sequential and retries 429/5xx/timeouts. Measured cost: about Rs 0.07 per short STT clip and Rs 0.13 per TTS sentence.

## Layout

```
voicetest/
  clients.py        the only code that talks to Gnani (raw requests, disk cache, explicit model + format)
  cache.py          stable cache keys
  degrade.py        seeded noise at a target SNR, 8 kHz, 300-3400 Hz band-pass, mu-law, packet loss
  generate.py       seeded sentence generator (52 per seed)
  cases.py          the original 10 hand-written sentences + judge()
  compare.py        entity scoring       hindi_numbers.py   Hindi number phrases -> exact values
tests/              pytest, no network
sweep.py            test matrix runner + paired v2.5-vs-v3.0 comparison
rejudge.py          re-score saved results offline      analyze_digits.py   digit-level error analysis
report.py           HTML report
results/            raw outputs of every sweep
```

## Gnani models and APIs used

- **Prisma STT v2.5 and v3.0** via the REST endpoint `POST /stt/v3` (`language_code=hi-IN`, `format=transcribe`, `model` always sent explicitly and checked in the reply).
- **Timbre TTS v3.0** via `POST /api/v1/tts/inference` (voice `Shivani`, `hi-IN`, 16 kHz mono).

## Prior work

The core loop (speak known text, transcribe it, compare) is not new. Related work:

- Voice-agent testing platforms that simulate callers with noise and accents, mostly scoring whole conversations: Bluejay and Evalion (listed in Cekura's roundup), Vapi's Test Suite, Relyable, FutureAGI Simulate, TestMu AI.
- *Voice of India* benchmark (arXiv 2604.19151): real telephonic Indic speech, scored with OI-WER, which accepts valid spelling variants.
- Sarvam AI, *Evaluating Indian Language ASR*: argues WER is a poor fit for Indian languages and proposes entity-based scoring.
- *The TTS-STT Flywheel* (arXiv 2605.03073): synthetic, entity-dense Indic test audio generated with TTS.

What this project adds is a small, reproducible developer tool: Indic entity scoring (phones, amounts, times, with Hindi number words), telephone-style damage, a paired version-to-version comparison with an exact test, digit-level error analysis, and an honest account of what the numbers do and do not show. Whether Gnani runs similar tests internally on real data is not known to me.

## Limitations

- White noise only; real calls have babble, traffic and codec artefacts. The mu-law step approximates G.711.
- Synthetic speech from one Timbre voice in one language; real callers will be harder.
- A text mismatch does not say who is at fault; only failures on clean audio can be separated.
- The cache can serve stale answers if Gnani silently updates a model under the same name.
- Docs vs behaviour oddities seen and unexplained: Gnani's ITN docs show `शाम 17:00` for "शाम पाँच बजे" but the models returned `शाम 05:15` / `शाम 5:15`; v2.5's documented default format is `verbatim`, yet an early call without `format` returned digits (now moot: `format` is always sent).
- Alignment of repeated digits (e.g. `8888`) is ambiguous, so per-position error counts are approximate.

## Future work

Not done yet: Prisma v3.0 `keyterms` with vs without, `verbatim` vs `transcribe` output, packet-loss conditions, Timbre audio tags (whisper, cough) as hard speech, a few real recordings of someone reading fake numbers, more seeds (3-4) to pass 250 sentences, a `--no-cache` flag, and CI that runs only the no-API tests.
