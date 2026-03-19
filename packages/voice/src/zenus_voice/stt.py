"""
Speech-to-Text (STT) Module

Uses faster-whisper for local, offline speech recognition.
faster-whisper is 4× faster than openai-whisper with the same accuracy,
uses CTranslate2 as the inference backend, and requires no PyTorch.

No API keys needed — runs entirely on your machine.

Model size guide:
  tiny   (~39M)  — fastest, good for simple commands
  base   (~74M)  — best balance of speed and accuracy  ← default
  small  (~244M) — higher accuracy, moderate speed
  medium (~769M) — high accuracy, slower
  large  (~1.5B) — best accuracy, GPU recommended
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np
import pyaudio
import soundfile as sf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class WhisperModel(Enum):
    """Available Whisper model sizes (same names as openai-whisper for compatibility)."""
    TINY   = "tiny"
    BASE   = "base"
    SMALL  = "small"
    MEDIUM = "medium"
    LARGE  = "large"


@dataclass
class TranscriptionResult:
    """Result from speech transcription."""
    text: str
    language: str
    confidence: float
    duration: float


# ---------------------------------------------------------------------------
# Voice Activity Detection (VAD)
# ---------------------------------------------------------------------------

class VoiceActivityDetector:
    """Detects when the user is speaking vs silence using webrtcvad."""

    def __init__(self, aggressiveness: int = 3) -> None:
        """
        Args:
            aggressiveness: 0-3; higher = more aggressive noise filtering.
        """
        import webrtcvad
        self.vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, audio_data: bytes, sample_rate: int) -> bool:
        """Return True if *audio_data* contains speech."""
        try:
            return self.vad.is_speech(audio_data, sample_rate)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# SpeechToText
# ---------------------------------------------------------------------------

class SpeechToText:
    """
    Local speech-to-text using faster-whisper.

    Compared to openai-whisper:
    - 4× faster transcription (CTranslate2 backend)
    - Lower memory footprint (int8 quantization by default)
    - No PyTorch required
    - Same model names and accuracy
    """

    # Whisper expects 16 kHz mono audio
    SAMPLE_RATE = 16_000

    def __init__(
        self,
        model: WhisperModel = WhisperModel.BASE,
        device: str = "cpu",
        compute_type: str = "int8",
        language: Optional[str] = None,
    ) -> None:
        """
        Args:
            model:        Whisper model size.
            device:       "cpu" or "cuda".
            compute_type: CTranslate2 quantization ("int8", "float16", "float32").
                          "int8" is the best default for CPU inference.
            language:     ISO language code (e.g. "en"), or None for auto-detect.
        """
        from faster_whisper import WhisperModel as _FasterWhisperModel

        self.model_name   = model.value
        self.device       = device
        self.compute_type = compute_type
        self.language     = language

        logger.info("Loading faster-whisper %s model (%s / %s)…", self.model_name, device, compute_type)
        self._model = _FasterWhisperModel(self.model_name, device=device, compute_type=compute_type)
        logger.info("faster-whisper model loaded")

        self.vad        = VoiceActivityDetector()
        self.chunk_size = int(self.SAMPLE_RATE * 0.03)  # 30 ms chunks

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe_file(self, audio_path: str) -> TranscriptionResult:
        """
        Transcribe audio from *audio_path* (wav, mp3, etc.).

        Returns a :class:`TranscriptionResult`.
        """
        import time

        start = time.time()
        segments, info = self._model.transcribe(
            audio_path,
            language=self.language,
            beam_size=5,
        )
        text = " ".join(s.text for s in segments).strip()
        elapsed = time.time() - start

        return TranscriptionResult(
            text=text,
            language=info.language,
            confidence=info.language_probability,
            duration=elapsed,
        )

    def transcribe_audio_data(self, audio_data: np.ndarray) -> TranscriptionResult:
        """
        Transcribe raw float32 numpy array sampled at 16 kHz.

        Saves to a temporary WAV file (faster-whisper accepts file paths),
        then delegates to :meth:`transcribe_file`.
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            sf.write(tmp_path, audio_data, self.SAMPLE_RATE)

        try:
            return self.transcribe_file(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def listen_and_transcribe(
        self,
        duration: Optional[float] = None,
        silence_duration: float = 1.5,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None,
    ) -> TranscriptionResult:
        """
        Record from the default microphone until silence, then transcribe.

        Args:
            duration:         Maximum recording time in seconds (None = unlimited).
            silence_duration: Seconds of silence that end the recording.
            on_speech_start:  Optional callback fired when speech is first detected.
            on_speech_end:    Optional callback fired when silence ends the recording.
        """
        import time

        audio = pyaudio.PyAudio()
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.SAMPLE_RATE,
                input=True,
                frames_per_buffer=self.chunk_size,
            )

            logger.debug("Listening…")
            frames: List[bytes] = []
            is_speaking   = False
            silence_start: Optional[float] = None
            rec_start     = time.time()

            while True:
                data      = stream.read(self.chunk_size, exception_on_overflow=False)
                has_speech = self.vad.is_speech(data, self.SAMPLE_RATE)

                if has_speech:
                    if not is_speaking and on_speech_start:
                        on_speech_start()
                    is_speaking   = True
                    silence_start = None
                    frames.append(data)
                elif is_speaking:
                    if silence_start is None:
                        silence_start = time.time()
                    frames.append(data)
                    if time.time() - silence_start > silence_duration:
                        if on_speech_end:
                            on_speech_end()
                        break

                if duration and (time.time() - rec_start) > duration:
                    break

            stream.stop_stream()
            stream.close()

        finally:
            audio.terminate()

        if not frames:
            return TranscriptionResult(text="", language="", confidence=0.0, duration=0.0)

        raw   = np.frombuffer(b"".join(frames), dtype=np.int16)
        audio_f32 = raw.astype(np.float32) / 32_768.0
        return self.transcribe_audio_data(audio_f32)


# ---------------------------------------------------------------------------
# MicrophoneRecorder (utility for recording to file)
# ---------------------------------------------------------------------------

class MicrophoneRecorder:
    """Record audio from the default microphone to a WAV file."""

    def __init__(self, sample_rate: int = 16_000) -> None:
        self.sample_rate = sample_rate
        self.chunk_size  = 1024

    def record(self, duration: float, output_path: str) -> None:
        """
        Record for *duration* seconds and save to *output_path*.
        """
        import wave

        audio = pyaudio.PyAudio()
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
            )

            frames: List[bytes] = []
            num_chunks = int(self.sample_rate / self.chunk_size * duration)
            for _ in range(num_chunks):
                frames.append(stream.read(self.chunk_size))

            stream.stop_stream()
            stream.close()

            with wave.open(output_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b"".join(frames))

        finally:
            audio.terminate()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_stt_instance: Optional[SpeechToText] = None


def get_stt(
    model: WhisperModel = WhisperModel.BASE,
    device: str = "cpu",
) -> SpeechToText:
    """Return the module-level :class:`SpeechToText` singleton."""
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = SpeechToText(model, device)
    return _stt_instance
