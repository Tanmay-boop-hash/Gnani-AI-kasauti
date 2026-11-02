import numpy as np
import pytest
import voicetest.degrade as dg


def tone(freq, sr=16000, seconds=1.0, amp=0.3):
    t = np.arange(int(sr * seconds)) / sr
    return amp * np.sin(2 * np.pi * freq * t)


def power(x):
    return float(np.mean(x ** 2))


@pytest.fixture
def clip(tmp_path):
    """A 1-second two-tone 'voice-like' clip saved as a 16 kHz WAV."""
    p = tmp_path / "clip.wav"
    dg.write_wav(p, tone(440) + tone(880), 16000)
    return p


def run_in(monkeypatch, folder, clip, **kwargs):
    monkeypatch.setattr(dg, "CACHE_DIR", folder)
    return dg.degrade(clip, **kwargs).read_bytes()


def test_same_inputs_give_byte_identical_audio(monkeypatch, tmp_path, clip):
    a = run_in(monkeypatch, tmp_path / "one", clip, snr_db=10, telephone=True, loss=0.1, seed=7)
    b = run_in(monkeypatch, tmp_path / "two", clip, snr_db=10, telephone=True, loss=0.1, seed=7)
    assert a == b


def test_different_seed_gives_different_noise(monkeypatch, tmp_path, clip):
    a = run_in(monkeypatch, tmp_path / "one", clip, snr_db=10, seed=1)
    b = run_in(monkeypatch, tmp_path / "two", clip, snr_db=10, seed=2)
    assert a != b


def test_noise_hits_the_requested_snr():
    x = tone(440) + tone(880)
    y = dg.add_noise(x, 10.0, np.random.default_rng(0))
    achieved = 10 * np.log10(power(x) / power(y - x))
    assert achieved == pytest.approx(10.0, abs=0.5)


def test_telephone_output_is_8khz_and_half_as_long(monkeypatch, tmp_path, clip):
    monkeypatch.setattr(dg, "CACHE_DIR", tmp_path / "c")
    out = dg.degrade(clip, telephone=True)
    x, sr = dg.read_wav(out)
    assert sr == 8000
    assert len(x) == pytest.approx(8000, abs=2)


def test_telephone_band_keeps_1khz_and_removes_100hz():
    mid, _ = dg.to_telephone(tone(1000), 16000)
    low, _ = dg.to_telephone(tone(100), 16000)
    assert power(low) < 0.05 * power(mid)


def test_mu_law_round_trip_stays_close_to_the_original():
    x = tone(440, sr=8000)
    y = dg.mu_law_roundtrip(x)
    assert np.corrcoef(x, y)[0, 1] > 0.99


def test_packet_loss_extremes():
    x = tone(440, sr=8000)
    rng = np.random.default_rng(0)
    assert np.all(dg.drop_frames(x, 8000, 1.0, rng) == 0)
    assert np.array_equal(dg.drop_frames(x, 8000, 0.0, rng), x)


def test_non_mono_wav_is_rejected(tmp_path):
    import wave
    p = tmp_path / "stereo.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 200)
    with pytest.raises(ValueError):
        dg.read_wav(p)