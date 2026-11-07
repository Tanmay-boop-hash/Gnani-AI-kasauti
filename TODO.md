# TODO

> Last updated: Sat 31 Oct 2026.
> Deadline: Tue 10 Nov 2026 (challenge close). Internal targets: post live by Sat 7 Nov, submit by Mon 9 Nov. 10 days left.
> Light days (exams): Mondays and Thursdays.

---

## Current status

### Done
- [x] Registered for the challenge; 5,000 credits received
- [x] Measured costs: STT 0.15 min = Rs 0.07; TTS 43 characters = Rs 0.12
- [x] Hello-world scripts for STT and TTS run successfully
- [x] `voicetest/cache.py` and `voicetest/clients.py` written
- [x] `roundtrip.py`: 5 sentences run end to end (cost about Rs 0.52); second run served entirely from cache with no new API requests
- [x] First versions of PROJECT.md, LEARNINGS.md, TODO.md
- [x] Language decided: Python (PROJECT.md decision 8)
- [x] Decided the repo will be public from the start (decision 9)
- [x] Entity comparer (`voicetest/compare.py`) and 21 tests written and passing (Tanmay's run)
- [x] Found that Prisma v3.0 launched Oct 28 and read its docs

### Not done yet
- [ ] Choose the repo name
- [ ] `git init`, `.gitignore` (must list `.env`, `.cache/`, `*.wav`, `__pycache__/`), first commit
- [ ] Create the GitHub repo and push
- [ ] `requirements.txt` (the code currently imports `requests` and `python-dotenv`)

---

## Pending tasks (replanned Sat 31 Oct; the Fri 30 Oct checkpoint was missed)

| When | Task | Done when |
|---|---|---|
| **Sat 31 Oct** | Update `transcribe` (model, format in the request and cache key), run 10 hand-written cases on Prisma v2.5 and v3.0 | `pytest` green; `roundtrip.py` prints a PASS/FAIL table for both models |
| Sun 1 Nov | Test-case generator (seeded) and phone-line degrader (8 kHz, mu-law, noise at set levels, seeded) | 200 reproducible cases; one clean clip turned into 3 degraded versions you have listened to |
| Mon 2 Nov (light) | Tests for generator and degrader determinism | Same seed gives byte-identical audio |
| Tue 3 to Wed 4 Nov | Runner (one request at a time) and report | **20 sentences x 2 models x clean/phone end to end produce a report** |
| Thu 5 Nov (light) | README draft with "Prior work" | A stranger could install and run it |
| Fri 6 Nov | Findings (v2.5 vs v3.0, keyterms with/without) and the 60-second demo video | 3 clear findings with numbers |
| **Sat 7 Nov** | Post live | Post published |
| Sun 8 Nov | Repo polish; GitHub Actions for the no-API tests if time allows | Clean repo |
| Mon 9 Nov | Submission form | Submitted by Monday night |
| Tue 10 Nov | Emergencies only | |


- **On 7Nov 2026** : Hinglish variant added to generator; hand-written cases are no longer in the sweep

**Cut order if time shrinks:** GitHub Actions, real-clip comparison, latency measurement. Keep generator, degrader, runner, report, one v2.5-vs-v3.0 finding.

**Before final submission:** delete `01_stt_hello.py` and `02_tts_hello.py`; add a "Prior work" section to the README based on PROJECT.md section 6.

---

## Known issues and design questions

1. **Comparer must handle formatting differences (done for digits, amounts, times; words-as-numbers still `not_found`).** Observed in the first run: STT writes `9876543210` for spoken digits, `₹5,00,000` for "five lakh rupees", `09:30` for "half past nine", and adds a trailing `।`. A raw string comparison would mark these wrong. (LEARNINGS 1.2)
2. **Error attribution.** A text mismatch doesn't say whether TTS or STT was at fault. Plan: keep the cached WAV so we can listen. (LEARNINGS 1.3)
3. **Cache can return stale answers.** Fixed in part (Sat 31 Oct): model, format, language and keyterms are now in the STT cache key and `transcribe` returns the whole reply including `model`. Still open: a silent server-side update under the same model name; maybe add `--no-cache`.
4. **Noise must be deterministic.** If the degrader uses random noise, use a seed. Otherwise the audio bytes change every run and the STT cache never hits. (LEARNINGS 2.1)
5. **SDK vs raw `requests`.** Unverified whether the official SDK accepts Timbre v3.0 voices; we are using raw `requests` for now.
6. **Docs conflict on number handling.** Older v2.5 docs advised pre-formatting numbers as spoken words; the newer normalization guide says it is automatic. Not yet confirmed for v3.0. (LEARNINGS 1.5)
7. **Positioning / novelty.** The core idea has prior art (PROJECT.md section 6). Decide what makes this project different and write it in one sentence. Not yet decided.
8. **One active request at a time.** Gnani can return 429 `RATE_LIMITED` for parallel requests; the runner must be sequential.
9. **Check which model served our earlier calls.** Open one file in `.cache/stt/` and read its `model` field. Docs say v2.5 defaults to `verbatim`, but our first run returned digits and times; find out why.

---

## Next steps (small and concrete)

1. Pick the repo name.
2. Create `.gitignore` and `requirements.txt`, run `git status` to confirm `.env` is not listed, and make the first commit.
3. Create the GitHub repo and push.
4. Today (Sat 31 Oct): update `clients.py`, add `tests/test_clients.py`, rewrite `roundtrip.py`, run the 10 cases on both models.

---

## Open questions for you (needed to complete the docs)

- What is explicitly out of scope for this project? (PROJECT.md "Non-goals" is empty.)
- What is the one-sentence positioning of the project, given the prior art in PROJECT.md section 6?