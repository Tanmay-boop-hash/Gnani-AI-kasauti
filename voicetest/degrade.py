"""Make clean TTS audio sound like a bad phone call.

Order mirrors real life: noise enters at the microphone, the phone network
squashes the audio (8 kHz, narrow band, mu-law), then packets may get lost.
Everything is seeded, so the same inputs always give byte-identical audio
(which also keeps the STT cache working).
"""

from __future__ import annotations

import hashlib
import wave
from math import gcd
from pathlib import Path

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt

from .cache import CACHE_DIR, key_for

MU = 255.0   # standard mu-law constant (North America / Japan telephony)

# reading and writing WAV
def read_wav(path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("expected a 16-bit mono WAV file")
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    return x, sr


def write_wav(path, x: np.ndarray, sr: int) -> None:
    pcm = (np.clip(x, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


# the indiviual damage steps
def add_noise(x: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    """White noise scaled so signal power / noise power = snr_db."""
    signal_power = np.mean(x ** 2)
    noise_power = signal_power / (10 ** (snr_db / 10))
    return x + rng.standard_normal(len(x)) * np.sqrt(noise_power)

def mu_law_roundtrip(x: np.ndarray) -> np.ndarray:
    """Compress with mu-law, store in 8 bits (256 levels), expand again.
    Quiet sounds keep more detail than loud ones, like a phone codec.
    (An approximation of G.711, not bit-exact.)"""
    x = np.clip(x, -1.0, 1.0)
    y = np.sign(x) * np.log1p(MU * np.abs(x)) / np.log1p(MU)   # compress
    q = np.round((y + 1) / 2 * 255)                             # 8-bit levels
    y = q / 255 * 2 - 1
    return np.sign(y) * ((1 + MU) ** np.abs(y) - 1) / MU        # expand

def to_telephone(x: np.ndarray, sr: int) -> tuple[np.ndarray, int]:
    """8 kHz sampling, 300-3400 Hz band-pass, then mu-law."""
    if sr != 8000:
        g = gcd(8000, sr)
        x = resample_poly(x, 8000 // g, sr // g)   # low-pass first, then drop samples
    sos = butter(4, [300, 3400], btype="bandpass", fs=8000, output="sos")
    return mu_law_roundtrip(sosfilt(sos, x)), 8000

def drop_frames(x: np.ndarray, sr: int, loss: float, rng: np.random.Generator,
                frame_ms: int = 20) -> np.ndarray:
    """Silence random 20 ms chunks, like lost network packets."""
    n = int(sr * frame_ms / 1000)
    y = x.copy()
    for start in range(0, len(y), n):
        if rng.random() < loss:
            y[start:start + n] = 0.0
    return y

# the one function the rest of the project calls
def degrade(wav_path, *, snr_db=None, telephone=False, loss=0.0, seed=0) -> Path:
    audio = Path(wav_path).read_bytes()
    key = key_for("degrade", hashlib.sha256(audio).hexdigest(),
                  snr_db, telephone, loss, seed)
    out = CACHE_DIR / "degraded" / f"{key}.wav"
    if out.exists():
        return out
    x, sr = read_wav(wav_path)
    rng = np.random.default_rng(seed)
    if snr_db is not None:
        x = add_noise(x, snr_db, rng)
    if telephone:
        x, sr = to_telephone(x, sr)
    if loss > 0:
        x = drop_frames(x, sr, loss, rng)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_wav(out, x, sr)
    return out