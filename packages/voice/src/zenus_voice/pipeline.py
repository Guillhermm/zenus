"""
Voice Pipeline

Canonical entry point for a Zenus voice session.

Architecture:

  ┌──────────────┐   wake word    ┌───────────────┐   transcription
  │ WakeDetector │ ─────────────► │ SpeechToText  │ ──────────────►
  └──────────────┘                └───────────────┘                │
                                                                    ▼
                                                        ┌──────────────────┐
                                                        │    Orchestrator  │
                                                        └──────────────────┘
                                                                    │
  ┌──────────────┐   TTS output   ┌───────────────┐   result       │
  │ Speaker/Text │ ◄───────────── │ TextToSpeech  │ ◄──────────────┘
  └──────────────┘                └───────────────┘

Usage::

    from zenus_core.orchestrator import Orchestrator
    from zenus_voice.pipeline import VoicePipeline

    pipeline = VoicePipeline(Orchestrator())
    pipeline.run()          # blocking; Ctrl+C to stop
    # or
    pipeline.run_once()     # single interaction cycle

The pipeline is fully optional — Zenus works without it.  No import at the
core level depends on this module.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, List, Optional

from zenus_voice.stt import SpeechToText, TranscriptionResult, WhisperModel
from zenus_voice.tts import TextToSpeech, TTSConfig, TTSEngine, Voice
from zenus_voice.wake_word import WakeWord, WakeWordDetector, create_wake_detector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class PipelineState(Enum):
    IDLE       = "idle"
    WAITING_FOR_WAKE = "waiting_for_wake"
    LISTENING  = "listening"
    PROCESSING = "processing"
    SPEAKING   = "speaking"
    STOPPED    = "stopped"


# ---------------------------------------------------------------------------
# Session data
# ---------------------------------------------------------------------------

@dataclass
class VoiceTurn:
    """One complete interaction turn."""
    timestamp:  str
    user_text:  str
    response:   str
    confidence: float
    latency_s:  float


@dataclass
class VoiceSession:
    """Aggregates turns for the current voice session."""
    turns: List[VoiceTurn] = field(default_factory=list)
    max_turns: int = 10

    def add(self, turn: VoiceTurn) -> None:
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def context_snippet(self, n: int = 3) -> str:
        """Return the last *n* turns as a plain-text context string."""
        recent = self.turns[-n:]
        if not recent:
            return ""
        lines = ["Recent conversation:"]
        for t in recent:
            lines.append(f"User: {t.user_text}")
            lines.append(f"Zenus: {t.response}")
        return "\n".join(lines)

    def clear(self) -> None:
        self.turns.clear()


# ---------------------------------------------------------------------------
# VoicePipeline
# ---------------------------------------------------------------------------

class VoicePipeline:
    """
    End-to-end voice pipeline: wake word → STT → Zenus → TTS.

    Args:
        orchestrator:       Zenus :class:`~zenus_core.orchestrator.Orchestrator`.
        stt_model:          Whisper model size (default: BASE).
        tts_engine:         TTS backend (default: PYTTSX3 for broadest compatibility).
        tts_voice:          Voice profile.
        device:             "cpu" or "cuda" for STT inference.
        use_wake_word:      If True, wait for wake word before each command.
        wake_word:          Which wake word to listen for.
        wake_threshold:     openwakeword confidence threshold.
        exit_phrases:       Phrases that end the session (case-insensitive).
        use_voice_output:   Speak responses aloud (True) or print only (False).
        on_state_change:    Optional callback fired on every state transition.
    """

    _EXIT_DEFAULTS = frozenset(["stop listening", "goodbye", "exit", "quit", "stop"])
    _CANCEL_PHRASES = frozenset(["cancel", "nevermind", "forget it", "stop"])

    def __init__(
        self,
        orchestrator,
        stt_model: WhisperModel = WhisperModel.BASE,
        tts_engine: TTSEngine = TTSEngine.PYTTSX3,
        tts_voice: Voice = Voice.FEMALE_WARM,
        device: str = "cpu",
        use_wake_word: bool = True,
        wake_word: WakeWord = WakeWord.HEY_ZENUS,
        wake_threshold: float = 0.5,
        exit_phrases: Optional[List[str]] = None,
        use_voice_output: bool = True,
        on_state_change: Optional[Callable[[PipelineState], None]] = None,
    ) -> None:
        self._orch             = orchestrator
        self.use_wake_word     = use_wake_word
        self.use_voice_output  = use_voice_output
        self.exit_phrases      = frozenset(exit_phrases or self._EXIT_DEFAULTS)
        self._on_state_change  = on_state_change
        self._state            = PipelineState.IDLE

        logger.info("Initialising voice pipeline…")
        self._stt     = SpeechToText(stt_model, device=device)
        self._tts     = TextToSpeech(tts_engine, tts_voice)
        self._tts_cfg = TTSConfig(voice=tts_voice)
        self._session = VoiceSession()
        self._running = False

        if use_wake_word:
            self._wake_event = threading.Event()
            self._wake_det   = create_wake_detector(
                wake_word=wake_word,
                threshold=wake_threshold,
                on_wake=self._wake_event.set,
            )
        else:
            self._wake_event = None
            self._wake_det   = None

        logger.info("Voice pipeline ready")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> PipelineState:
        return self._state

    def run(self) -> None:
        """
        Block until the user says an exit phrase or Ctrl+C.

        If ``use_wake_word=True``, each cycle starts by waiting for the
        configured wake word.
        """
        self._running = True
        self._set_state(PipelineState.IDLE)
        self._say("Voice control activated. Say an exit phrase to stop.")

        if self._wake_det:
            self._wake_det.start_listening(background=True)

        try:
            while self._running:
                self.run_once()
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            if self._wake_det:
                self._wake_det.stop_listening()
            self._say("Goodbye.")
            self._set_state(PipelineState.STOPPED)

    def run_once(self) -> Optional[str]:
        """
        Execute one interaction cycle:

        1. Wait for wake word (if enabled)
        2. Listen for command
        3. Execute via Zenus
        4. Speak / print response

        Returns the Zenus result string, or None if cancelled.
        """
        import time

        try:
            # --- Step 1: wait for wake word ---
            if self.use_wake_word and self._wake_event:
                self._set_state(PipelineState.WAITING_FOR_WAKE)
                self._wake_event.wait()
                self._wake_event.clear()

            # --- Step 2: listen ---
            self._set_state(PipelineState.LISTENING)
            transcription = self._stt.listen_and_transcribe(
                on_speech_start=lambda: logger.debug("Speech detected…"),
                on_speech_end=lambda: logger.debug("Recording complete"),
            )

            if not transcription.text.strip():
                self._say("I didn't catch that — please try again.")
                return None

            user_text = transcription.text.strip()
            logger.info("Transcribed: %r (lang=%s, conf=%.2f)",
                        user_text, transcription.language, transcription.confidence)

            # --- Cancel / exit detection ---
            lower = user_text.lower()
            if any(p in lower for p in self._CANCEL_PHRASES):
                self._say("Okay, cancelled.")
                return None

            if any(p in lower for p in self.exit_phrases):
                self._running = False
                return user_text

            # --- Step 3: execute ---
            self._set_state(PipelineState.PROCESSING)
            start_t = time.time()

            context = self._session.context_snippet()
            enhanced = f"{context}\n\nUser: {user_text}" if context else user_text

            result = self._orch.execute_command(enhanced)
            latency = time.time() - start_t

            # --- Step 4: respond ---
            response = self._humanise(result)
            self._set_state(PipelineState.SPEAKING)
            self._say(response)

            self._session.add(VoiceTurn(
                timestamp  = datetime.now(timezone.utc).isoformat(),
                user_text  = user_text,
                response   = response,
                confidence = transcription.confidence,
                latency_s  = latency,
            ))

            self._set_state(PipelineState.IDLE)
            return result

        except KeyboardInterrupt:
            self._running = False
            return None
        except Exception as exc:
            logger.error("Pipeline error: %s", exc)
            self._say(f"Sorry, something went wrong: {exc}")
            self._set_state(PipelineState.IDLE)
            return None

    def clear_context(self) -> None:
        """Wipe the conversation context (e.g. after a topic change)."""
        self._session.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_state(self, state: PipelineState) -> None:
        self._state = state
        if self._on_state_change:
            try:
                self._on_state_change(state)
            except Exception:
                pass

    def _say(self, text: str) -> None:
        """Print and optionally speak *text*."""
        logger.info("Response: %s", text)
        if self.use_voice_output:
            self._tts.speak(text, self._tts_cfg)
        else:
            print(f"[Zenus] {text}")

    @staticmethod
    def _humanise(result: str) -> str:
        """
        Lightly clean up a Zenus result string for speech.

        Removes terminal markup characters that sound odd when read aloud.
        """
        for sym, replacement in (("✓", "Done."), ("✗", "Failed."), ("→", "then")):
            result = result.replace(sym, replacement)
        return result.strip()


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_voice_pipeline(orchestrator, **kwargs) -> VoicePipeline:
    """
    Create a :class:`VoicePipeline` bound to *orchestrator*.

    All keyword arguments are forwarded to :class:`VoicePipeline.__init__`.
    """
    return VoicePipeline(orchestrator, **kwargs)
