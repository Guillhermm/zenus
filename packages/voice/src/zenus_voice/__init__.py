"""
Zenus Voice - Voice interface for Zenus

Hands-free control using Speech-to-Text and Text-to-Speech.
All processing happens locally - no cloud APIs!

Features:
- Local STT using Whisper
- Local TTS using Piper or system TTS
- Conversational flow with context carryover
- Wake word detection (optional)
- Natural interruptions
"""

from zenus_voice.stt import (
    SpeechToText,
    WhisperModel,
    TranscriptionResult,
    get_stt
)

from zenus_voice.tts import (
    TextToSpeech,
    TTSEngine,
    Voice,
    TTSConfig,
    get_tts
)

from zenus_voice.voice_orchestrator import (
    VoiceOrchestrator,
    ConversationState,
    ConversationTurn,
    ConversationContext,
    create_voice_interface
)

from zenus_voice.wake_word import (
    WakeWordDetector,
    SimpleWakeWordDetector,
    WakeWord,
    create_wake_detector
)

__version__ = "0.1.0"

__all__ = [
    # STT
    'SpeechToText',
    'WhisperModel',
    'TranscriptionResult',
    'get_stt',
    
    # TTS
    'TextToSpeech',
    'TTSEngine',
    'Voice',
    'TTSConfig',
    'get_tts',
    
    # Voice Orchestrator
    'VoiceOrchestrator',
    'ConversationState',
    'ConversationTurn',
    'ConversationContext',
    'create_voice_interface',
    
    # Wake Word
    'WakeWordDetector',
    'SimpleWakeWordDetector',
    'WakeWord',
    'create_wake_detector',
]
