"""
Wake Word Detection

Listens in the background for "Hey Zenus" (or any configured phrase) to activate
voice control.  Uses openwakeword — fully local, no API key required.

openwakeword pre-trained models (installed automatically):
  alexa, hey_jarvis, hey_mycroft, okay_rhasspy, timers, weather

Custom models can be provided as ONNX files via the `custom_model_paths` argument.

Design:
  - WakeWordDetector: main class, wraps openwakeword in a blocking listen loop.
  - TextFallbackDetector: backup that runs a tiny-Whisper STT pass on short
    audio snippets and does plain-text matching — zero extra dependencies.
  - create_wake_detector(): factory that picks the right implementation.
"""

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Callable, List, Optional

import numpy as np
import pyaudio

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Wake word enum — maps to openwakeword model names
# ---------------------------------------------------------------------------

class WakeWord(Enum):
    """Supported wake words / phrases."""
    # openwakeword built-in pre-trained models
    ALEXA      = "alexa"
    HEY_JARVIS = "hey_jarvis"
    HEY_MYCROFT = "hey_mycroft"
    OKAY_RHASSPY = "okay_rhasspy"
    # Alias used by the Zenus CLI — backed by hey_jarvis model by default
    HEY_ZENUS  = "hey_jarvis"


# ---------------------------------------------------------------------------
# WakeWordDetector (openwakeword)
# ---------------------------------------------------------------------------

class WakeWordDetector:
    """
    Wake word detection using openwakeword (local, no API key).

    openwakeword processes 80 ms audio frames at 16 kHz (1280 samples).
    When the model confidence for a frame exceeds *threshold*, the
    *on_wake* callback is fired.

    Args:
        wake_word:          Wake word to detect.
        threshold:          Minimum confidence score (0-1) to trigger.  0.5 is
                            a good starting point; lower = more sensitive.
        on_wake:            Called with no arguments when wake word detected.
        custom_model_paths: Optional list of paths to .onnx custom model files.
    """

    # openwakeword requires exactly 80 ms frames at 16 kHz
    SAMPLE_RATE  = 16_000
    FRAME_SAMPLES = 1280   # 80 ms × 16 000 Hz

    def __init__(
        self,
        wake_word: WakeWord = WakeWord.HEY_ZENUS,
        threshold: float = 0.5,
        on_wake: Optional[Callable[[], None]] = None,
        custom_model_paths: Optional[List[str]] = None,
    ) -> None:
        try:
            from openwakeword.model import Model as OwwModel
        except ImportError as exc:
            raise ImportError(
                "openwakeword is not installed.  Install with:\n"
                "  pip install openwakeword\n"
                "Then download the default models:\n"
                "  python -m openwakeword.utils download_models"
            ) from exc

        self.wake_word  = wake_word
        self.threshold  = threshold
        self.on_wake    = on_wake
        self.is_listening = False
        self._thread: Optional[threading.Thread] = None

        model_names = [wake_word.value]
        kwargs: dict = {"inference_framework": "onnx"}
        if custom_model_paths:
            kwargs["custom_verifier_models"] = custom_model_paths
        else:
            kwargs["wakeword_models"] = model_names

        self._model = OwwModel(**kwargs)
        logger.info("WakeWordDetector ready (model=%s, threshold=%.2f)", wake_word.value, threshold)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_listening(self, background: bool = False) -> None:
        """
        Start listening for the wake word.

        Args:
            background: If True, run the listen loop in a daemon thread
                        so the caller is not blocked.
        """
        if self.is_listening:
            return

        if background:
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
        else:
            self._listen_loop()

    def stop_listening(self) -> None:
        """Signal the listen loop to stop."""
        self.is_listening = False
        logger.debug("WakeWordDetector stop requested")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _listen_loop(self) -> None:
        self.is_listening = True
        audio = pyaudio.PyAudio()
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.SAMPLE_RATE,
                input=True,
                frames_per_buffer=self.FRAME_SAMPLES,
            )
            logger.info("Listening for wake word '%s'…", self.wake_word.value)

            while self.is_listening:
                raw  = stream.read(self.FRAME_SAMPLES, exception_on_overflow=False)
                frame = np.frombuffer(raw, dtype=np.int16)

                prediction = self._model.predict(frame)
                score = prediction.get(self.wake_word.value, 0.0)

                if score >= self.threshold:
                    logger.info("Wake word detected (score=%.3f)", score)
                    if self.on_wake:
                        self.on_wake()
                    # Reset internal state to avoid repeated triggers
                    self._model.reset()

            stream.stop_stream()
            stream.close()

        except Exception as exc:
            logger.error("Wake word listen loop error: %s", exc)
        finally:
            audio.terminate()
            self.is_listening = False


# ---------------------------------------------------------------------------
# TextFallbackDetector (no extra dependencies beyond stt.py)
# ---------------------------------------------------------------------------

class TextFallbackDetector:
    """
    Fallback wake word detection via text matching.

    Records 3-second audio snippets, runs faster-whisper (tiny model) on each
    snippet, and checks whether the transcription contains the wake phrase.
    This is less power-efficient than openwakeword but requires no extra models.

    Args:
        wake_phrase: Phrase to listen for (case-insensitive).
        on_wake:     Called with no arguments when phrase detected.
    """

    def __init__(
        self,
        wake_phrase: str = "hey zenus",
        on_wake: Optional[Callable[[], None]] = None,
    ) -> None:
        self.wake_phrase  = wake_phrase.lower()
        self.on_wake      = on_wake
        self.is_listening = False

        from zenus_voice.stt import SpeechToText, WhisperModel
        self._stt = SpeechToText(WhisperModel.TINY)
        logger.info("TextFallbackDetector ready (phrase=%r)", wake_phrase)

    def start_listening(self, background: bool = False) -> None:
        """Start listening (blocking unless background=True)."""
        if self.is_listening:
            return

        if background:
            t = threading.Thread(target=self._listen_loop, daemon=True)
            t.start()
        else:
            self._listen_loop()

    def stop_listening(self) -> None:
        self.is_listening = False

    def _listen_loop(self) -> None:
        self.is_listening = True
        logger.info("TextFallbackDetector listening for %r…", self.wake_phrase)
        while self.is_listening:
            try:
                result = self._stt.listen_and_transcribe(duration=3.0, silence_duration=0.8)
                if result.text and self.wake_phrase in result.text.lower():
                    logger.info("Wake phrase detected: %r", result.text)
                    if self.on_wake:
                        self.on_wake()
            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.debug("TextFallbackDetector error: %s", exc)
        self.is_listening = False


# ---------------------------------------------------------------------------
# SimpleWakeWordDetector (alias kept for backward compatibility)
# ---------------------------------------------------------------------------

SimpleWakeWordDetector = TextFallbackDetector


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_wake_detector(
    wake_word: WakeWord = WakeWord.HEY_ZENUS,
    threshold: float = 0.5,
    on_wake: Optional[Callable[[], None]] = None,
    custom_model_paths: Optional[List[str]] = None,
) -> WakeWordDetector | TextFallbackDetector:
    """
    Create a wake word detector, falling back to :class:`TextFallbackDetector`
    if openwakeword is not installed.

    Args:
        wake_word:          Wake word to detect.
        threshold:          openwakeword confidence threshold (0-1).
        on_wake:            Callback fired when the wake word is detected.
        custom_model_paths: Optional ONNX model paths for openwakeword.
    """
    try:
        return WakeWordDetector(
            wake_word=wake_word,
            threshold=threshold,
            on_wake=on_wake,
            custom_model_paths=custom_model_paths,
        )
    except (ImportError, Exception) as exc:
        logger.warning("openwakeword unavailable (%s), using text-matching fallback", exc)
        phrase = wake_word.value.replace("_", " ")
        return TextFallbackDetector(wake_phrase=phrase, on_wake=on_wake)
