"""
Text-to-Speech (TTS) Module

Supports multiple TTS engines:
- Piper: High-quality neural TTS (local)
- pyttsx3: System TTS (fallback)

All processing happens locally - no cloud APIs!
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum
import pyttsx3
from zenus_core.debug import get_debug_flags

logger = logging.getLogger(__name__)


class TTSEngine(Enum):
    """Available TTS engines"""
    PIPER = "piper"      # Neural TTS, best quality
    PYTTSX3 = "pyttsx3"  # System TTS, always available


class Voice(Enum):
    """Predefined voice profiles"""
    # Piper voices (if available)
    FEMALE_WARM = "en_US-lessac-medium"
    FEMALE_NEUTRAL = "en_US-amy-medium"
    MALE_DEEP = "en_US-ryan-medium"
    MALE_NEUTRAL = "en_US-joe-medium"
    
    # Generic fallbacks
    SYSTEM_DEFAULT = "system_default"


@dataclass
class TTSConfig:
    """TTS configuration"""
    voice: Voice = Voice.FEMALE_WARM
    speed: float = 1.0  # 0.5-2.0
    pitch: float = 1.0  # 0.5-2.0 (pyttsx3 only)
    volume: float = 1.0  # 0.0-1.0


class PiperTTS:
    """
    Piper neural TTS engine (high quality, local)
    
    Requires piper-tts to be installed:
    pip install piper-tts
    """
    
    def __init__(self, voice: Voice = Voice.FEMALE_WARM):
        self.voice = voice
        self._check_installation()
    
    def _check_installation(self) -> bool:
        """Check if Piper is installed"""
        try:
            result = subprocess.run(
                ["piper", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def speak(self, text: str, config: TTSConfig = TTSConfig()) -> bool:
        """
        Speak text using Piper
        
        Returns:
            True if successful
        """
        try:
            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                output_path = tmp_file.name
            
            # Run Piper
            cmd = [
                "piper",
                "--model", config.voice.value if config.voice != Voice.SYSTEM_DEFAULT else Voice.FEMALE_WARM.value,
                "--output_file", output_path
            ]
            
            # Adjust speed if needed
            if config.speed != 1.0:
                cmd.extend(["--length_scale", str(1.0 / config.speed)])
            
            # Run Piper with text as input
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=text, timeout=30)
            
            if process.returncode != 0:
                logger.error("Piper error: %s", stderr)
                return False

            # Play the audio file
            self._play_audio(output_path)

            # Clean up
            Path(output_path).unlink(missing_ok=True)

            return True

        except Exception as e:
            logger.error("Piper TTS failed: %s", e)
            return False
    
    def speak_to_file(self, text: str, output_path: str, config: TTSConfig = TTSConfig()) -> bool:
        """Save speech to audio file"""
        try:
            cmd = [
                "piper",
                "--model", config.voice.value if config.voice != Voice.SYSTEM_DEFAULT else Voice.FEMALE_WARM.value,
                "--output_file", output_path
            ]
            
            if config.speed != 1.0:
                cmd.extend(["--length_scale", str(1.0 / config.speed)])
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=text, timeout=30)
            
            return process.returncode == 0
            
        except Exception as e:
            logger.error("Piper TTS to file failed: %s", e)
            return False
    
    def _play_audio(self, audio_path: str):
        """Play audio file using system player"""
        import platform
        
        system = platform.system()
        
        try:
            if system == "Linux":
                # Try multiple players
                for player in ["aplay", "paplay", "ffplay", "mpv"]:
                    try:
                        subprocess.run([player, audio_path], check=True, timeout=30)
                        return
                    except (FileNotFoundError, subprocess.CalledProcessError):
                        continue
            elif system == "Darwin":  # macOS
                subprocess.run(["afplay", audio_path], check=True, timeout=30)
            elif system == "Windows":
                import winsound
                winsound.PlaySound(audio_path, winsound.SND_FILENAME)
        except Exception as e:
            logger.error("Failed to play audio: %s", e)


class SystemTTS:
    """
    System TTS using pyttsx3 (fallback option)
    
    Works on all platforms but lower quality than Piper
    """
    
    def __init__(self):
        self.engine = pyttsx3.init()
        self._configure_default()
    
    def _configure_default(self):
        """Set default configuration"""
        # Set default voice (prefer female)
        voices = self.engine.getProperty('voices')
        if voices:
            # Try to find a female voice
            for voice in voices:
                if 'female' in voice.name.lower() or 'woman' in voice.name.lower():
                    self.engine.setProperty('voice', voice.id)
                    break
    
    def speak(self, text: str, config: TTSConfig = TTSConfig()) -> bool:
        """Speak text using system TTS"""
        try:
            # Apply configuration
            self.engine.setProperty('rate', int(200 * config.speed))  # Words per minute
            self.engine.setProperty('volume', config.volume)
            
            # Speak
            self.engine.say(text)
            self.engine.runAndWait()
            
            return True
            
        except Exception as e:
            logger.error("System TTS failed: %s", e)
            return False

    def speak_to_file(self, text: str, output_path: str, config: TTSConfig = TTSConfig()) -> bool:
        """Save speech to audio file"""
        try:
            self.engine.setProperty('rate', int(200 * config.speed))
            self.engine.setProperty('volume', config.volume)

            self.engine.save_to_file(text, output_path)
            self.engine.runAndWait()

            return True

        except Exception as e:
            logger.error("System TTS to file failed: %s", e)
            return False
    
    def list_voices(self) -> List[str]:
        """List available system voices"""
        voices = self.engine.getProperty('voices')
        return [voice.name for voice in voices]


class TextToSpeech:
    """
    Unified TTS interface with automatic fallback
    
    Tries Piper first (best quality), falls back to system TTS
    """
    
    def __init__(
        self,
        preferred_engine: TTSEngine = TTSEngine.PIPER,
        voice: Voice = Voice.FEMALE_WARM
    ):
        self.preferred_engine = preferred_engine
        self.voice = voice
        
        # Initialize engines
        self.piper = None
        self.system_tts = None
        
        if preferred_engine == TTSEngine.PIPER:
            try:
                self.piper = PiperTTS(voice)
                if get_debug_flags().voice:
                    logger.debug("Using Piper TTS (high quality)")
            except Exception as e:
                if get_debug_flags().voice:
                    logger.debug("Piper not available (%s), falling back to system TTS", e)
                self.system_tts = SystemTTS()
        else:
            self.system_tts = SystemTTS()
            if get_debug_flags().voice:
                logger.debug("Using system TTS")
    
    def speak(self, text: str, config: Optional[TTSConfig] = None) -> bool:
        """
        Speak text using best available engine
        
        Args:
            text: Text to speak
            config: TTS configuration
        
        Returns:
            True if successful
        """
        if not text or not text.strip():
            return False
        
        config = config or TTSConfig(voice=self.voice)
        
        # Try Piper first
        if self.piper:
            if self.piper.speak(text, config):
                return True
            # Piper failed, try system TTS
            if get_debug_flags().voice:
                logger.debug("Piper failed, falling back to system TTS")
            if not self.system_tts:
                self.system_tts = SystemTTS()
        
        # Use system TTS
        if self.system_tts:
            return self.system_tts.speak(text, config)
        
        return False
    
    def speak_to_file(self, text: str, output_path: str, config: Optional[TTSConfig] = None) -> bool:
        """Save speech to audio file"""
        config = config or TTSConfig(voice=self.voice)
        
        if self.piper:
            if self.piper.speak_to_file(text, output_path, config):
                return True
        
        if self.system_tts:
            return self.system_tts.speak_to_file(text, output_path, config)
        
        return False
    
    def speak_async(self, text: str, config: Optional[TTSConfig] = None):
        """Speak text in background thread (non-blocking)"""
        import threading
        
        thread = threading.Thread(target=self.speak, args=(text, config))
        thread.daemon = True
        thread.start()


# Singleton instance
_tts_instance: Optional[TextToSpeech] = None


def get_tts(
    engine: TTSEngine = TTSEngine.PIPER,
    voice: Voice = Voice.FEMALE_WARM
) -> TextToSpeech:
    """Get or create TTS instance"""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TextToSpeech(engine, voice)
    return _tts_instance
