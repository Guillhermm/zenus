"""
Zenus Voice — hands-free control with local STT and TTS.

All processing happens on-device:
  - Speech-to-text: faster-whisper (CTranslate2 backend, no PyTorch)
  - Wake word:      openwakeword (no API key required)
  - Text-to-speech: Piper (neural) or pyttsx3 (system fallback)

Entry point::

    from zenus_core.orchestrator import Orchestrator
    from zenus_voice.pipeline import VoicePipeline

    pipeline = VoicePipeline(Orchestrator())
    pipeline.run()
"""

from zenus_voice.stt import (
    SpeechToText,
    WhisperModel,
    TranscriptionResult,
    VoiceActivityDetector,
    MicrophoneRecorder,
    get_stt,
)

from zenus_voice.tts import (
    TextToSpeech,
    TTSEngine,
    Voice,
    TTSConfig,
    get_tts,
)

from zenus_voice.wake_word import (
    WakeWord,
    WakeWordDetector,
    TextFallbackDetector,
    SimpleWakeWordDetector,  # backward-compat alias
    create_wake_detector,
)

from zenus_voice.pipeline import (
    VoicePipeline,
    VoiceSession,
    VoiceTurn,
    PipelineState,
    create_voice_pipeline,
)

from zenus_voice.voice_orchestrator import (
    VoiceOrchestrator,
    ConversationState,
    ConversationTurn,
    ConversationContext,
    create_voice_interface,
)

__version__ = "0.2.0"

__all__ = [
    # STT
    "SpeechToText",
    "WhisperModel",
    "TranscriptionResult",
    "VoiceActivityDetector",
    "MicrophoneRecorder",
    "get_stt",
    # TTS
    "TextToSpeech",
    "TTSEngine",
    "Voice",
    "TTSConfig",
    "get_tts",
    # Wake word
    "WakeWord",
    "WakeWordDetector",
    "TextFallbackDetector",
    "SimpleWakeWordDetector",
    "create_wake_detector",
    # Pipeline (canonical entry point)
    "VoicePipeline",
    "VoiceSession",
    "VoiceTurn",
    "PipelineState",
    "create_voice_pipeline",
    # Legacy voice orchestrator
    "VoiceOrchestrator",
    "ConversationState",
    "ConversationTurn",
    "ConversationContext",
    "create_voice_interface",
]
