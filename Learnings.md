# LEARNINGS

> Last updated: Sat 31 Oct 2026 (pytest, failure kinds, defaults, mocking).
> Sections: 1 Concepts, 2 Code explained, 3 Bugs, 4 Mistakes and lessons, 5 Interview questions.

---

## 1. Concepts in simple language

### 1.1 Round-trip testing
We make Timbre (text to speech) say a sentence we already know, then give that audio to Prisma (speech to text) and compare what it wrote with what we sent. Because we know the correct answer in advance, a difference is a measurable failure, with no human labelling.

### 1.2 Inverse text normalization (ITN): what our first run showed
STT output is not a literal word-for-word transcript. Prisma converts spoken forms into written forms ("inverse text normalization"). It is the opposite of the TTS step that converts written forms into spoken ones.

First run (5 sentences, `hi-IN`):

| Said (sent to TTS) | Heard (STT output) | What we learn |
|---|---|---|
| `मेरा नंबर 9876543210 है` | `मेरा नंबर 9876543210 है।` | Digits survive the round trip |
| digits spoken as Hindi words | `मेरा नंबर 9876543210 है।` | Spoken digits are written back as one digit string |
| `पाँच लाख रुपये भेजना है` | `₹5,00,000 भेजना है।` | Words become a rupee amount with Indian comma grouping |
| `₹5,00,000 भेजना है` | `₹5,00,000 भेजना है।` | Amount survives |
| `सुबह साढ़े नौ बजे मिलते हैं` | `सुबह 09:30 बजे मिलते हैं।` | "Half past nine" becomes `09:30` |

Consequences for the comparer: a plain string comparison would mark most of these wrong. The output also adds a trailing `।` (danda) every time. We must compare meaning (normalized form), not raw strings.

### 1.3 Attribution: who made the mistake?
A mismatch could be Timbre reading the text wrongly, Prisma hearing it wrongly, or both. Text alone cannot tell you which. All our audio is saved in `.cache/tts/`, so when something fails we can listen to the clip: if the clip sounds wrong, TTS is at fault; if it sounds right, STT is. Also, our first run only shows the loop works. It does not prove each step is individually correct.

### 1.4 Billing: credits, rupees, and units
Credits and rupees match 1:1 in the usage history, but the two APIs are metered differently:
- STT is billed by **audio duration** (0.15 min cost Rs 0.07; 0.03 min cost Rs 0.02), roughly Rs 0.5 per minute.
- TTS is billed by **characters** (43 characters cost Rs 0.12), roughly Rs 2.8 per 1,000 characters.

So "credits are about equal to rupees" does not mean the two cost the same. A silent pause in an STT clip costs money; a long sentence costs more in TTS. The rates above are rough, computed from rounded dashboard values.

### 1.5 Q1. What changed in Timbre v3.0, and why do we prefer it?
(The model is Timbre **v3.0**. "v0.3" is just the digits swapped.)

What Gnani's docs say changed compared with Timbre v2.5:
- **Voices:** v2.5 has 42 voices, each with one preferred language. v3.0 has 13 voices, and each speaks all 10 supported languages (Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati).
- **Audio tags:** you can put tags inline in the text, such as `<coughs>`, `<whispers>`, `<laugh>`, `<sigh>`, `<pauses>`, `<shouting>`. With v2.5 the tags are stripped and not spoken.
- **Not interchangeable:** a v2.5 voice name sent to v3.0 (or the reverse) is rejected with a 400 error.

Claims on Gnani's launch page (vendor marketing, **not yet verified by us**): more expressive speech, switching language mid-sentence (beta), reading numbers and IDs correctly without special markup, and first audio in under 150 ms.

Why we use v3.0 in this project:
1. **Harder test material.** Tags like whisper and cough let us make speech closer to real callers, which is useful for stress-testing STT.
2. **One voice, all languages.** We can vary language across the test matrix without changing the voice.
3. **Entity reading is our focus.** The claim about reading numbers and IDs directly matters to us, and we plan to test it rather than trust it.

Caveats: we have not compared v3.0 against v2.5 yet, and the docs are not fully consistent. Earlier v2.5 docs advised writing numbers out as spoken words, while Gnani's newer Text Normalization Guide says conversion is automatic. We have not confirmed which model that applies to. Our digits-as-digits sentence came back correct, which is consistent with automatic handling, but we have not listened to the clip to confirm how it was read.

### 1.6 How to choose a language (decided Sun 25 Oct 2026)
We did not choose Python on purpose; the first scripts simply started in it. We then decided properly:
1. List the hard sub-problems (generating cases, simulating a phone line with maths on audio, comparing Hindi text, many API calls, reports, automated tests).
2. Check which language already has good tools for them.
3. Check vendor support (Gnani's official SDK is Python).
4. Ask how fast you can move in the time you have. This is often the real tiebreaker.
5. Ask how costly it is to switch later (cheap early, grows with every line of code).
6. Write the decision down with a revisit trigger.

Alternatives considered: TypeScript/Node, Go, Java/Kotlin, Rust. Result: Python, mainly because Tanmay writes and understands it most easily. Language speed barely matters here, because the program mostly waits for network replies.
Lesson: deciding after the fact is fine if it is recorded honestly. Do not invent a rationale that was not there at the start.

### 1.7 Why Indic ASR evaluation is more than word error rate (WER)
WER counts every difference from a single reference spelling as an error. Indian languages have several correct forms: a code-mixed word such as "doctor" may appear in Latin script or as "डॉक्टर", and numbers may be digits or spelled out. Voice of India (arXiv 2604.19151) built OI-WER to accept valid spelling variants, and Sarvam's evaluation guide adds scores for whether entities (names, numbers, dates) survive. For us this means: score **entities** (phone numbers, amounts, times) after normalizing them, rather than comparing raw strings.

### 1.8 Why "10 out of 10 correct" proves little
If the system truly failed about 26% of the time, you would still see 10 clean passes roughly 1 time in 20. So 10/10 is consistent with a true failure rate of up to about a quarter. 100/100 passes brings that ceiling down to about 3% (rule of thumb: ceiling is roughly 3 divided by the number of tests). Comparing two conditions needs more still.
Also, clean synthetic speech from Gnani's own TTS may be unusually easy for Gnani's own STT, so passes on clean synthetic audio say little about real callers. That is why the phone-line degradation and a small set of real recordings matter. The interesting results are the *breaking points*: which entity types fail first, and at what noise level.

### Observations from 10/10 PASS on comparing between Prisma-v2.0 and Prisma-v3.0
- The models write the same thing differently: v2.5 gives ₹5,00,000 and 09:30, while v3.0 gives 5,00,000 रुपये and 9:30. The comparer tolerates both, which is why it exists.
- Both returned the evening time as 5:15 with the word शाम, not 17:15. Gnani’s ITN docs show a similar phrase becoming 17:00. The "बजकर … मिनट" wording may explain it, but it’s worth testing.
- A loophole in our own tool: compare_time ignores AM/PM, so that PASS doesn’t prove it heard PM. A lenient comparer can hide failures, so keep that in mind when the results look too good.

### 1.9 What `pytest -q` is (and why the output is green)
`pytest` is not a special command: it finds files named `test_*.py`, runs every function starting with `test_`, and reports. `-q` means *quiet* (shorter output: one dot per passing test and a summary line); `-v` is the opposite (every test name). The colours are pytest's own: green = passed, red = failed, yellow = warnings or skips. It only colours when it detects a terminal.

### 1.10 Reading the entity comparer's failure kinds
The comparer does more than say pass/fail; it names *how* an entity failed: `not_found` (the number never appeared, often because the model wrote words instead of digits), `length_mismatch` (digits dropped or added), `substitution` (same length, a wrong digit) and `wrong_value` (amount or time parsed but different). The report will count these. "Same" is defined per entity type: digits only for phones/PINs, numeric value for amounts, 12-hour clock for times (AM/PM not checked yet).

### 1.11 Never trust defaults; verify what the server actually ran
Prisma v3.0 is opt-in and the default output style differs by model and request. The reply contains a `model` field, so `roundtrip.py` compares it with what we asked for and prints a warning if they differ. Rule of thumb: send every setting that can change the answer explicitly, include each in the cache key, and check the server's echo. Gnani's own docs also note that identical audio can differ by a borderline word between runs, which is another reason to cache.

### 1.12 Mocking the network in tests
`tests/test_clients.py` replaces `requests.post` with a fake, points the cache at a temporary folder, and sets a fake API key (pytest's `monkeypatch` and `tmp_path`). The client code can then be tested (does the cache hit? is the model sent? is an HTTP error raised and not cached?) with zero credits, zero network, and instant results.

### What the fake network was for ?
A fake (or mock) is a stand-in object that replaces a real dependency during a test. Ours swaps requests.post for a fake function, uses a throwaway cache folder (tmp_path), and sets a fake API key. It matters because:

- Cost and speed. Real calls spend credits and need internet. Fake ones are instant and free.
- Failures on demand. You can’t ask Gnani to return a 400 or 429 whenever you like, but a fake can, so we can test that errors raise and aren’t cached.
- What it tests. It checks our logic: that model and format are sent, that the cache key reacts to them, and that a second identical call makes no request.

### Finding the breaking point
We make the audio worse until the models start failing. degrade.py damages a clip in the same order as real life:

- Noise at the microphone, set by SNR in decibels: 20 dB is mild, 10 is moderate, 5 is heavy, and 0 dB means the noise is as loud as the voice.
- The phone network: resample to 8 kHz (with a low-pass filter first, so you avoid aliasing), keep only 300–3400 Hz, then compress to 8 bits with µ-law, which keeps quiet detail at the cost of loud detail.
- Packet loss (built, not used in this sweep yet): silence random 20 ms chunks.

---

## 2. Code explained

### 2.1 Q2. What `key_for` does in `cache.py`

```python
def key_for(*parts) -> str:
    """Same input -> same key. This is what makes re-runs free."""
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
```

**The engineering problem:** before calling the API we need a way to ask "have I already done exactly this request?" The answer is a filename. That filename must be (a) the same every time for the same inputs, (b) different for different inputs, and (c) short and safe to use as a filename, even though the inputs can be long text full of Devanagari characters and quotes.

**What happens step by step** (using a real example from our experiments, `key_for({"text": "नमस्ते", "voice": "Shivani"})`):

1. `*parts` collects all arguments into a tuple. Calling `key_for(payload)` gives `parts = (payload,)`. Calling `key_for("stt", "hi-IN", audio_hash)` gives a tuple of three. This lets one function serve both TTS and STT.
2. `json.dumps(...)` converts the Python objects into **one text string** in a standard format, because a hash function needs bytes or text, not Python dicts. A tuple becomes a JSON list: `[{"text": "नमस्ते", "voice": "Shivani"}]`.
3. `.encode()` converts that text into **bytes** (UTF-8). Hash functions only accept bytes.
4. `hashlib.sha256(...)` computes the fingerprint (explained below).
5. `.hexdigest()` writes that fingerprint as a string of 64 hexadecimal characters.
6. `[:16]` keeps the first 16 of them. For our example this gives `e3553795b17223ea`.

**Each piece:**

- **`blob`**: just a variable name. "Blob" is programmer slang for "one opaque chunk of data". Here it is the single text string that stands for all the inputs. (After `.encode()` it becomes bytes. We checked: `str` before, `bytes` after.)
- **`hashlib`**: Python's standard-library module with hash functions (sha256, md5, and others). Nothing to install.
- **`sha256`**: a hash function. It takes input of any length and produces a fixed 256-bit (32-byte) fingerprint. Properties that matter to us:
  - *Deterministic*: same input, same output, always.
  - *Fixed size*: a 3-word sentence and a whole 30-second audio file both give 32 bytes.
  - *Avalanche effect*: a tiny change gives a completely different result. We checked: the first 16 hex characters for `hello1` are `91e9240f41522398` and for `hello2` are `87298cc2f31fba73`.
  - *One-way*: you cannot rebuild the input from the hash. We do not need to; we only need to recognise the same input again.
- **`hexdigest()`**: the hash is raw bytes (not safe to print or use in a filename). `hexdigest` shows it as 64 characters from `0-9a-f`, which is filename-safe. (`digest()` gives the raw 32 bytes; we checked: 32 bytes vs 64 characters.)
- **`sort_keys=True`**: two Python dicts with the same content but a different key order are equal (`a == b` is `True`), but `json.dumps` writes them in the order they were created, so the text differs. Our check: without sorting, `{"text":..., "voice":...}` gave key `e3553795b17223ea` but the same dict written as `{"voice":..., "text":...}` gave `bed0b211e4c4892b`. That would cause a false cache miss and a wasted API call. Sorting the keys makes the text canonical.
- **`ensure_ascii=False`**: by default `json.dumps` escapes every non-English character: `"नमस्ते"` becomes `"\u0928\u092e\u0938\u094d\u0924\u0947"`. With `False` the real Devanagari characters are kept. For correctness either choice works, as long as it never changes, because both are deterministic. We chose `False` so the text stays readable if we print the blob while debugging. Changing it later would change every key and empty the cache.
- **`default=str`**: if a part contains something JSON does not understand (for example a `Path`), call `str()` on it instead of crashing. Caveat: `str()` of some objects includes memory addresses, which would make keys unstable. Our parts are simple, so this is fine.
- **`[:16]`**: shortens the key to 64 bits, which is plenty. For 5,000 cache entries, the chance that any two collide is about 7 x 10^-13 (we computed it). If the cache ever held millions of entries we should use more characters. A collision would silently return the wrong cached audio.

**Where else this appears:** in `transcribe`, `hashlib.sha256(audio).hexdigest()` fingerprints the *audio file's bytes*, so the same sound maps to the same key regardless of the file's name.

**A consequence worth remembering:** since the STT key depends on the audio bytes, our noise-adding code must be **deterministic** (seeded random noise). If the noise differs every run, the bytes differ, the key differs, and the cache never hits.

### 2.2 Q3. What `BASE = "https://api.vachana.ai"` is

```python
BASE = "https://api.vachana.ai"
```

- **What it is:** a Python variable holding the *root address* of Gnani's API server. Python convention is to write constants in UPPERCASE, which is why we called it `BASE`. The name is ours; the **value is not**: it comes from Gnani's docs, where it is the address used in every example and the default in their Python SDK.
- **Is it an endpoint?** Not by itself. A URL has parts: `https://` (secure connection) + `api.vachana.ai` (which server) + a path (which operation). An **endpoint** is the full address of one specific operation: base + path. We use two:

| Endpoint | Method | Purpose |
|---|---|---|
| `{BASE}/api/v1/tts/inference` | POST | Text to speech |
| `{BASE}/stt/v3` | POST | Speech to text (REST) |

- **Why a variable:** the address is used in several places. Writing it once means a typo can't creep in and changing it later (the SDK docs mention pointing at a different environment) is a one-line edit.
- **Did we create anything?** No. We did not create the server or the address. We only gave Gnani's address a name in our code.

### 2.3 Q4. What `synthesize` and `transcribe` do (in `clients.py`)

These two functions are the **boundary** between our program and Gnani's servers. They are the only code that touches the network and spends credits. The rest of the project is our own logic that will call them. So yes, this is where the main work happens, but the real value of the project lies in what we build around them (generator, degrader, comparer, report).

**`synthesize(text, voice, language, model, speed, sample_rate)`** returns the path of a WAV file.
1. Builds a `payload` dict describing what we want (text, voice, model, language, speed, audio format).
2. Computes the cache path from `key_for(payload)`. Any change (different voice, speed) gives a new key, so it gets its own file automatically.
3. If that file exists, returns it immediately: no network, no credits.
4. Otherwise sends the payload as JSON (`json=payload`) with the API key in the `X-API-Key-ID` header.
5. `r.raise_for_status()` turns an HTTP error (a 400 or 500) into a Python exception, so a failure is never saved to the cache as if it were good audio.
6. Saves `r.content` (the raw audio bytes) into the cache, creating folders as needed (`mkdir(parents=True, exist_ok=True)`), and returns the path.

**`transcribe(wav_path, language_code)`** returns the transcript text.
1. Reads the audio file as bytes.
2. Builds the key from `"stt"`, the language, and the SHA-256 of the audio bytes.
3. If a cached JSON exists, returns its `transcript` field.
4. Otherwise uploads the audio as a multipart form (`files=` for the file, `data=` for the language), the format file-upload endpoints expect.
5. Checks for errors, saves the JSON response, and returns `["transcript"]`.

Both set `timeout=60` so the program doesn't hang forever if the server stops answering.

**Note:** `transcribe` returns only the text. The response also contains `request_id` and `model`, which we currently throw away. The `model` field could help us notice when Gnani updates its model (see TODO.md).

** `Results of the run after implementing the seeded generator` **
condition      prisma-v2.5   prisma-v3.0
clean                40/40         39/40
phone                40/40         40/40
phone+20dB           40/40         40/40
phone+10dB           39/40         40/40
phone+5dB            39/40         39/40
phone+0dB            36/40         32/40

HOW THEY FAILED (condition, model, kind: count)
  clean        prisma-v3.0  not_found        1
  phone+0dB    prisma-v2.5  length_mismatch  1
  phone+0dB    prisma-v2.5  substitution     3
  phone+0dB    prisma-v3.0  length_mismatch  1
  phone+0dB    prisma-v3.0  substitution     7
  phone+10dB   prisma-v2.5  length_mismatch  1
  phone+5dB    prisma-v2.5  length_mismatch  1
  phone+5dB    prisma-v3.0  substitution     1

FIRST 20 FAILURES
  phone+0dB    prisma-v2.5  phone-digits-s0-01 substitution     मेरा नंबर 9704876475 है
  phone+0dB    prisma-v3.0  phone-digits-s0-01 substitution     मेरा नंबर 9704876475 है।
  phone+0dB    prisma-v3.0  phone-digits-s0-04 substitution     मेरा नंबर 8938778708 है।
  phone+0dB    prisma-v2.5  phone-digits-s0-05 length_mismatch  मेरा नंबर था 160975351
  phone+0dB    prisma-v3.0  phone-digits-s0-05 length_mismatch  मेरा नंबर था 1 था 0975351।
  phone+0dB    prisma-v3.0  phone-words-s0-02 substitution     मेरा नंबर 8789659342 है।
  phone+0dB    prisma-v3.0  phone-words-s0-03 substitution     मेरा नंबर 7209478122 है।
  phone+0dB    prisma-v3.0  phone-words-s0-05 substitution     मेरा नंबर 9947751598।
  phone+0dB    prisma-v2.5  pin-digits-s0-01 substitution     मेरा पिनकोड 357012 है।
  phone+10dB   prisma-v2.5  pin-digits-s0-06 length_mismatch  मेरा पिन कोड 1 0 8 खना एक है।
  phone+5dB    prisma-v2.5  pin-digits-s0-06 length_mismatch  मेरा पिन कोड 1 0 8 खना एक है।
  phone+0dB    prisma-v3.0  pin-digits-s0-06 substitution     मेरा पिन कोड 108693 है।
  phone+5dB    prisma-v3.0  pin-words-s0-01 substitution     मेरा पिन कोड 513175 है।
  phone+0dB    prisma-v2.5  pin-words-s0-01 substitution     मेरा पिनकोड 513175 है।
  phone+0dB    prisma-v3.0  pin-words-s0-01 substitution     मेरा पिन कोड 513175 है।
  clean        prisma-v3.0  time-s0-02     not_found        शाम सात बजकर चालीस मिनट पर कॉल करना।


- Real: both models are solid on phone-quality audio down to 5 dB. Failures at 0 dB are almost all digit strings (phone and PIN). Amounts and times never failed under noise.
- Suggestive, not proven: v3.0 did worse than v2.5 at 0 dB (32 vs 36), and Sweep 1 pointed the same way (5/10 vs 8/10). But 4 sentences out of 40 on one noise seed has a wide margin: at n=40, 90% vs 80% could easily be luck. The multi-seed run is what decides this.
- Correlated failures: pin-digits-s0-06 failed identically for v2.5 at 10 and 5 dB, and pin-words-s0-01 produced the same wrong PIN (513175) in both models. Same seed means same noise pattern, so the effective sample is smaller than the raw counts.
- The one clean failure is not a hearing error: v3.0 heard शाम सात बजकर चालीस मिनट correctly but wrote the numbers as words, so my comparer said not_found. That is a comparer limitation (step 5), so v3.0’s clean score is really 40/40.
- Don’t headline Sweep 1’s patterns yet: the 4→7 substitution and the dropped last digit barely showed up here. The notable failures this time were phone-digits-s0-05 (leading digits lost) and a garbled word (खना) in place of a digit. Wait for the digit-level analysis before claiming any pattern.

- **`findings`**: the table above, with “one seed, 40 sentences, white noise only; v2.5 vs v3.0 gap at 0 dB not conclusive”
- **`concepts`**: “not_found on clean v3.0 time was words-instead-of-digits (a format miss). Same-seed failures are correlated across SNR levels, and across models.”

- rng means random number generator - an object that supplies random values. created using random.Random(seed) and passes it to helpers such as _digits and _time. Passing the same seed makes the generated cases repeatable.

- A leading underscore in a function name like `_digits` usually means `internal helper`, its meant to be used inside the module, its a python naming convention. In generate.py, the helpers like `_digits`, `_amount` and `_time` support the main `generate()` function. 

- adding a variant at the end of PLAN keeps the earlier sentences, and their cache, unchanged

- findings: add the 46-sentence table (clean 46/45, phone 46/46, 20 dB 46/46, 10 dB 44/46, 5 dB 44/44, 0 dB 41/36). Note v3.0’s clean miss is the words-instead-of-digits time, so its real clean score is 46/46.

## **Concepts** (from upgraded generate and added time and hinglish cases)
- Both models often make the identical mistake on the same noisy clip. pin-words-s0-01 came back as 513175 for v3.0 at 5 dB and for both models at 0 dB. acct-hinglish-s0-03 came back as 17547073 for v2.5 at 10 and 5 dB and for v3.0 at 5 dB. Clean audio passed, so TTS said it correctly. The noise masked a digit, and both models guessed the same wrong one. This is consistent with “the damage is in the audio”, but I haven’t proven it. Listening to those files (known issue #2) would test it.
- Every noise failure is a digit string (phone, PIN, account). Amounts (10 sentences) and times (6) never failed under noise. A hypothesis, untested: “five lakh rupees” is a common phrase the model can guess from context, while random digits have nothing to guess from.
- Ranking, three runs: v3.0 is behind at 0 dB by raw counts every time (5/10 vs 8/10, 32/40 vs 36/40, 36/46 vs 41/46). These are not three independent confirmations, because the 46 contains the 40 and the noise seed is the same. A 5-sentence gap on 46 is within what chance could produce, though I haven’t run a formal test. At 0 dB, 9 of v3.0’s 10 failures are substitutions (a full-length but wrong string), against 3 of v2.5’s 5. That is suggestive only; the digit-level analysis will show whether it’s real.

---

## 3. Bugs encountered

None yet. Template for later:

```
### <short title>
- Symptom:
- Root cause:
- Fix:
- How to avoid it next time:
```

---

## 4. Mistakes and lessons

- **We guessed credits might be tight, then measured.** Two dashboard rows showed STT is cheap, which changed the plan (no need to ration test runs). Lesson: measure the cost of an unknown before designing around it.
- **"Credits equal rupees" does not mean TTS and STT cost the same.** They are metered in different units (characters vs minutes). Lesson: check the unit, not just the currency.
- **Don't commit before `.gitignore` exists.** The API key lives in `.env`; if it is committed, rotate the key. Lesson: create `.gitignore` before the first `git add`.
- **We started in Python without choosing it.** The hello scripts just began in Python and the docs had a blank where the reason should be. We then compared alternatives and recorded the decision honestly (section 1.6). Lesson: when a default creeps in, evaluate it explicitly while switching is still cheap.
- **The core idea already has prior art.** Searching only after designing the project showed commercial tools and research papers on similar ideas (PROJECT.md section 6). Lesson: check prior art early, and state how your work differs.
- **A pytest import gotcha.** Plain `pytest` failed with `ModuleNotFoundError: No module named 'voicetest'` because the project root was not on Python's import path. Fix: a `pytest.ini` containing `pythonpath = .` (or run `python -m pytest`). Lesson: tests that cannot import your code are a path problem, not a code problem.
- **We tested against a model version we did not choose.** Prisma v3.0 launched mid-project and is opt-in, so every earlier call ran on the default. Lesson: pin and record the model on every call.
- **Left out compare_time because every generated time sentence is in words** (शाम सात बजकर चालीस मिनट), and compare_time can’t parse Hindi number words. That is exactly why v3.0’s clean time-s0-02 came back not_found in the sweep. The test filter also skips phone-words, pin-words and amount-words for the same reason.

---

## 5. Interview-relevant questions (practice answering out loud)

1. Why hash the inputs instead of using the text itself as the filename? (Section 2.1)
2. What makes a cache key correct? Name two ways a key can go wrong. (`sort_keys`; keys that miss something that matters, such as a model version)
3. Why does the STT cache key use the audio bytes rather than the filename? (Section 2.1)
4. When can a cache hurt rather than help in a testing tool? (Section 2.1 and TODO known issues)
5. What is the difference between a base URL and an endpoint? (Section 2.2)
6. Why separate API code from pure logic? (PROJECT.md decision 6)
7. If a round-trip test fails, how do you tell whether TTS or STT is at fault? (Section 1.3)
8. What is inverse text normalization, and how does it complicate comparing transcripts? (Section 1.2)
9. Why is STT metered by duration but TTS by characters, and what does that mean for how you design test clips? (Section 1.4)
10. How did you pick your language, and what would make you switch? (Section 1.6)
11. Why is word error rate a poor metric for Indian languages, and what would you measure instead? (Section 1.7)
12. You ran 10 tests and all passed. What can you conclude? What if it was 100? (Section 1.8)
13. Why send `model` and `format` explicitly instead of relying on API defaults? (Section 1.11)
14. How do you test code that calls a paid external API without calling it? (Section 1.12)
15. A vendor releases a new model version mid-project. What do you change in your test tool? (PROJECT.md decision 10)