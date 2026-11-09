# Kasauti (कसौटी): 1-Page Solution Pitch
> **Challenge:** Great Indian AI Internship Challenge (Gnani.ai)  
> **Author:** Tanmay Sonkar | **Track:** Sovereign AI for India  
> **Project Link:** [github.com/Tanmaysonkar/gnani-ai](https://github.com/Tanmaysonkar/gnani-ai)  
> **Deliverables:** [1-Page Pitch PDF (Kasauti_Solution_Pitch.pdf)](Kasauti_Solution_Pitch.pdf) &bull; [Interactive Audit Report (results/report.html)](results/report.html) &bull; Demo Video (2m 32s)

---

## 1. The Problem: The Indian Telecom Reality
Deploying conversational Voice AI across India requires operating over 8 kHz band-limited, noisy, and lossy telephony networks. Evaluating these models presents two critical roadblocks:
1. **Standard Metrics Fail on Indic Speech:** Word Error Rate (WER) penalizes legitimate spelling variations (e.g., `₹5,00,000` vs `5 लाख रुपये` vs `500000 रुपये`) or Devanagari/Latin code-mixing as complete errors.
2. **The Manual QA Bottleneck:** Crowdsourcing, recording, and human-annotating thousands of audio calls takes weeks, costs thousands in operational overhead, and cannot be deterministically re-run when upstream or downstream model checkpoints update.

---

## 2. The Solution: Closed-Loop Synthetic Regression Harness
**Kasauti** (*The Touchstone*) is a developer-first, zero-manual-labeling regression testing harness and benchmark for Indian-language voice AI, powered by Gnani’s **Timbre TTS** and **Prisma STT**.

```
[Seeded Entities] ──> [Timbre TTS] ──> [Telecom Channel DSP] ──> [Prisma STT] ──> [Semantic AST Judge]
  Known ground truth   hi-IN Voice     8 kHz, μ-law, 0 dB SNR    v2.5 & v3.0      Value, not orthography
```

* **Deterministic Ground Truth:** Synthesizes seed sentences containing known phone numbers, account PINs, rupee amounts, and timestamps.
* **Realistic Physical Telecom Channel Simulation (`voicetest/degrade.py`):** 300–3,400 Hz 4th-order bandpass filter, 16 kHz $\rightarrow$ 8 kHz downsampling, G.711 $\mu$-law companding/quantization, and calibrated noise injection down to 0 dB SNR.
* **Semantic AST Normalization (`voicetest/compare.py` & `hindi_numbers.py`):** Parses colloquial Hindi number phrases (*"सवा लाख"*, *"पौने पाँच"*) into exact numerical values, evaluating whether the critical business payload survived.

---

## 3. Experimental Discoveries (1,872 Clip Evaluations)

| Audio Condition | Prisma v2.5 | Prisma v3.0 | Key Finding |
| :--- | :---: | :---: | :--- |
| **Clean Audio** | 155 / 156 | 153 / 156 | 1 identical failure isolated to an upstream TTS stutter bug |
| **Phone Line (8 kHz $\mu$-law)** | 155 / 156 | 154 / 156 | Bandwidth compression alone caused 0% accuracy drop |
| **Phone + 10 dB Noise** | 151 / 156 | 153 / 156 | Parity performance between both engines ($p = 0.625$) |
| **Phone + 0 dB (Severe)** | **144 / 156** | **125 / 156** | **v2.5 significantly outperforms v3.0 ($p < 0.001$, sign test)** |

* **The 0 dB Noise Cliff:** At severe SNR, Prisma v3.0 experiences heavy digit substitutions (specifically transmuting `1` into `8`), whereas v2.5 preserves sequence lengths.
* **Blame Isolation:** Clean-audio baselines proved that in clip `phone-words-s2-02`, Timbre TTS spoke the digit `8` three times instead of four, proving that STT was blameless.
* **Fragility Taxonomy:** Over 82% of all failures concentrate in digit strings (phones/PINs); currency amounts and times survive because linguistic context reinforces them.
* **Hallucination Detection:** Severe acoustic stress caused models to hallucinate phantom tokens (most commonly `था`).

---

## 4. Production Feasibility & Developer Velocity
* **100% Synthetic Ground Truth:** Completely eliminates human transcription cost and labeling latency.
* **₹0.00 Cache Re-runs:** Multi-tier cryptographic input caching (`.cache/`) ensures identical audio and zero-cost re-evaluation.
* **Instant CI Verification:** 146 unit tests execute in **1.1 seconds** with 0 external network dependencies.
* **Reproducible Governance:** Generates self-contained interactive HTML audit reports (`report.py`) with synchronized waveforms and playback.
