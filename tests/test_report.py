import report
from voicetest.degrade import write_wav
from voicetest.generate import generate
import numpy as np


def rec(name, seed, cond, model, ok, failure="match", transcript="x", expected="e", style="digits"):
    return dict(seed=seed, name=name, entity=name.rsplit(f"-s{seed}", 1)[0], kind="digits", condition=cond,
                model=model, ok=ok, failure="match" if ok else failure, expected=expected,
                extracted=None, transcript=transcript, style=style)


def fake_records():
    names = [c[0] for c in generate(0)][:12]
    out = []
    for n in names:
        for cond in ("clean", "phone+0dB"):
            out.append(rec(n, 0, cond, "prisma-v2.5", True))
            out.append(rec(n, 0, cond, "prisma-v3.0", cond == "clean" or n.endswith(("01", "02")) is False))
    # a clean failure in both models (a TTS-fault-like clip)
    out.append(rec("phone-words-s2-02", 2, "clean", "prisma-v2.5", False, "length_mismatch", "794744888"))
    out.append(rec("phone-words-s2-02", 2, "clean", "prisma-v3.0", False, "length_mismatch", "794744888"))
    return out


def test_tables_and_sign_test():
    recs = fake_records()
    passed, total = report.pass_table(recs)
    assert total[("clean", "prisma-v2.5")] == 13 and passed[("clean", "prisma-v2.5")] == 12
    rows = {r[0]: r for r in report.paired_rows(recs, ["clean", "phone+0dB"])}
    label, both, only_a, only_b, neither, p = rows["phone+0dB"]
    assert only_a > 0 and only_b == 0 and 0 < p <= 1


def test_page_builds_without_audio_and_escapes():
    recs = fake_records()
    recs[0]["transcript"] = "<script>alert(1)</script>"
    page = report.build_html(recs, source="x.json", audio=False)
    assert "<script>" not in page.split("</style>")[1]
    assert "TTS FAULT" in page and "Pass rate by condition" in page and "<svg" in page
    assert "<audio" not in page


def test_page_embeds_audio_from_cache(tmp_path, monkeypatch):
    wav = tmp_path / "a.wav"
    write_wav(wav, np.zeros(1600), 16000)
    monkeypatch.setattr(report, "synthesize", lambda text: wav)
    monkeypatch.setattr(report, "degrade", lambda clean, **kw: wav)
    page = report.build_html(fake_records(), audio=True)
    assert "data:audio/wav;base64," in page


def test_missing_audio_is_not_fatal_and_costs_nothing(monkeypatch):
    def boom(text):
        raise RuntimeError("not in cache")
    monkeypatch.setattr(report, "synthesize", boom)
    page = report.build_html(fake_records(), audio=True)
    assert "audio not available" in page