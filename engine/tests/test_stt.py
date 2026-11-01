import io
import wave

import numpy as np
import pytest

from siegesense_engine.coach.stt import FakeStt, SttUnavailable, WhisperStt, wav_to_float


def wav(channels=1, rate=16000, seconds=0.5):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        samples = np.sin(np.linspace(0, 440 * 2 * np.pi * seconds, int(rate * seconds))) * 8000
        w.writeframes(np.repeat(samples.astype(np.int16), channels).tobytes())
    return buf.getvalue()


def test_wav_to_float_valid():
    audio = wav_to_float(wav())
    assert audio.dtype == np.float32 and len(audio) == 8000
    assert 0.2 < np.abs(audio).max() <= 1.0


def test_wav_to_float_rejects_stereo():
    with pytest.raises(ValueError, match="mono"):
        wav_to_float(wav(channels=2))


def test_wav_to_float_rejects_wrong_rate():
    with pytest.raises(ValueError, match="16 kHz"):
        wav_to_float(wav(rate=44100))


def test_wav_to_float_rejects_garbage():
    with pytest.raises(ValueError):
        wav_to_float(b"nope")


async def test_fake_stt():
    assert await FakeStt("why do I keep dying").transcribe(wav()) == "why do I keep dying"


def test_whisper_state_not_downloaded(tmp_path):
    assert WhisperStt(download_root=tmp_path).state() == "not_downloaded"


async def test_stt_unavailable_message(tmp_path, monkeypatch):
    stt = WhisperStt(download_root=tmp_path)

    def fail(*a, **k):
        raise OSError("network unreachable")

    monkeypatch.setattr(stt, "_load_model", fail)
    with pytest.raises(SttUnavailable, match="speech model"):
        await stt.transcribe(wav())
    assert stt.state() == "unavailable"
