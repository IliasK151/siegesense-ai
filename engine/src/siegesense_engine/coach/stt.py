"""Speech-to-text for push-to-talk questions (spec §4.10): faster-whisper on the CPU, offline
once the model has been downloaded (about 140 MB, one time)."""

from __future__ import annotations

import asyncio
import io
import threading
import wave
from pathlib import Path
from typing import Literal, Protocol

import numpy as np

SttState = Literal["ready", "not_downloaded", "downloading", "unavailable"]
MODEL = "base.en"


class SttUnavailable(RuntimeError):
    pass


class SpeechToText(Protocol):
    def state(self) -> SttState: ...

    async def transcribe(self, wav: bytes) -> str: ...


def wav_to_float(wav: bytes) -> np.ndarray:
    """16-bit PCM, mono, 16 kHz WAV → float32 samples in [-1, 1]."""
    try:
        with wave.open(io.BytesIO(wav), "rb") as w:
            channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
            frames = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"not a WAV file: {exc}") from exc
    if channels != 1:
        raise ValueError("audio must be mono")
    if width != 2:
        raise ValueError("audio must be 16-bit PCM")
    if rate != 16000:
        raise ValueError("audio must be 16 kHz")
    return np.frombuffer(frames, np.int16).astype(np.float32) / 32768.0


class FakeStt:
    def __init__(self, text: str = "", state: SttState = "ready") -> None:
        self._text = text
        self._state = state

    def state(self) -> SttState:
        return self._state

    async def transcribe(self, wav: bytes) -> str:
        if self._state == "unavailable":
            raise SttUnavailable("speech model unavailable")
        wav_to_float(wav)
        return self._text


class WhisperStt:
    def __init__(self, download_root: Path, model: str = MODEL) -> None:
        self._root = Path(download_root)
        self._name = model
        self._model = None
        self._lock = threading.Lock()
        self._downloading = False
        self._error: str | None = None

    def state(self) -> SttState:
        if self._error:
            return "unavailable"
        if self._model is not None:
            return "ready"
        if self._downloading:
            return "downloading"
        has_files = (
            any(self._root.glob(f"**/*{self._name}*/**/model.bin"))
            if self._root.exists()
            else False
        )
        return "ready" if has_files else "not_downloaded"

    def _load_model(self):
        from faster_whisper import WhisperModel

        return WhisperModel(
            self._name, device="cpu", compute_type="int8", download_root=str(self._root)
        )

    def _ensure(self):
        with self._lock:
            if self._model is None:
                self._downloading = True
                try:
                    self._model = self._load_model()
                    self._error = None
                except Exception as exc:
                    self._error = str(exc)
                    raise SttUnavailable(
                        f"Couldn't load the speech model ({exc}). Check your internet connection "
                        "for the one-time download, then try again."
                    ) from exc
                finally:
                    self._downloading = False
            return self._model

    async def download(self) -> None:
        self._error = None
        await asyncio.to_thread(self._ensure)

    def _run(self, audio: np.ndarray) -> str:
        model = self._ensure()
        segments, _ = model.transcribe(audio, language="en", beam_size=1, vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()

    async def transcribe(self, wav: bytes) -> str:
        audio = wav_to_float(wav)
        return await asyncio.to_thread(self._run, audio)
