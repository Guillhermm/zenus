# Zenus Voice 🎤

**Hands-free voice control for Zenus**

Talk to your computer naturally - no typing required!

## Features

- 🎤 **Speech-to-Text**: Local Whisper (no cloud, no API keys)
- 🔊 **Text-to-Speech**: High-quality Piper TTS or system TTS
- 💬 **Conversational**: Remembers context, natural interruptions
- 👂 **Wake Words**: "Hey Zenus" activation (optional)
- 🌍 **Multi-language**: Supports 50+ languages
- 🔒 **Privacy**: Everything runs locally on your machine

## Installation

```bash
cd packages/voice
poetry install

# For best quality TTS (optional)
poetry install --extras piper

# For wake word detection (optional)
poetry install --extras wake

# For everything
poetry install --extras full
```

## Quick Start

### Basic Voice Command

```python
from zenus_core.cli.orchestrator import Orchestrator
from zenus_voice import create_voice_interface

# Create Zenus orchestrator
orch = Orchestrator()

# Create voice interface
voice = create_voice_interface(orch)

# Listen and execute one command
voice.listen_and_execute()
```

### Continuous Mode

```python
# Keep listening for commands
voice.continuous_mode()

# Say "stop listening" to exit
```

### Wake Word

```python
from zenus_voice import create_wake_detector, WakeWord

def on_wake():
    print("Wake word detected!")
    voice.listen_and_execute()

# Create wake detector
detector = create_wake_detector(
    wake_word=WakeWord.HEY_ZENUS,
    on_wake=on_wake
)

# Start listening for "Hey Zenus"
detector.start_listening()
```

## Command Line

```bash
# Start voice interface
zenus-voice

# Continuous mode
zenus-voice --continuous

# With wake word
zenus-voice --wake-word "hey zenus"

# Change voice
zenus-voice --voice female_warm

# Adjust speed
zenus-voice --speed 1.2
```

## Examples

### Ask Questions

```python
response = voice.ask("What's the weather?")
print(f"You said: {response}")
```

### Get Confirmation

```python
if voice.confirm("Delete all logs?"):
    # User said yes
    print("Deleting...")
else:
    print("Cancelled")
```

### Change Settings

```python
# Disable voice responses (text only)
voice.set_voice_responses(False)

# Change voice
voice.set_voice(Voice.MALE_DEEP)

# Adjust speed
voice.set_speed(1.3)
```

## Configuration

### STT Models

```python
from zenus_voice import WhisperModel

# Fastest (lower accuracy)
voice = create_voice_interface(orch, stt_model=WhisperModel.TINY)

# Best balance (recommended)
voice = create_voice_interface(orch, stt_model=WhisperModel.BASE)

# Best accuracy (slower)
voice = create_voice_interface(orch, stt_model=WhisperModel.LARGE)
```

### TTS Engines

```python
from zenus_voice import TTSEngine, Voice

# High-quality Piper TTS (requires piper-tts)
voice = create_voice_interface(
    orch,
    tts_engine=TTSEngine.PIPER,
    tts_voice=Voice.FEMALE_WARM
)

# System TTS (always available)
voice = create_voice_interface(
    orch,
    tts_engine=TTSEngine.PYTTSX3
)
```

### Voices

Available voices:
- `Voice.FEMALE_WARM` - Warm, friendly female voice (default)
- `Voice.FEMALE_NEUTRAL` - Neutral female voice
- `Voice.MALE_DEEP` - Deep male voice
- `Voice.MALE_NEUTRAL` - Neutral male voice
- `Voice.SYSTEM_DEFAULT` - Use system default

## Requirements

### Required
- Python 3.10+
- `openai-whisper` - STT
- `pyttsx3` - Fallback TTS
- `pyaudio` - Audio I/O
- Working microphone and speakers

### Optional
- `piper-tts` - High-quality TTS (recommended)
- `pvporcupine` - Wake word detection
- GPU (CUDA) - Faster Whisper (optional)

## Troubleshooting

### PyAudio Installation Issues

**Linux:**
```bash
sudo apt-get install portaudio19-dev
pip install pyaudio
```

**macOS:**
```bash
brew install portaudio
pip install pyaudio
```

**Windows:**
```bash
# Download prebuilt wheel from:
# https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
pip install PyAudio‑*.whl
```

### No Microphone Detected

```python
import pyaudio
audio = pyaudio.PyAudio()

# List available devices
for i in range(audio.get_device_count()):
    info = audio.get_device_info_by_index(i)
    print(f"{i}: {info['name']}")
```

### Whisper Model Download

First time running downloads models (~40MB-1.5GB depending on size).
Models are cached in `~/.cache/whisper/`.

## Performance

### STT Latency

| Model  | Size  | Latency (CPU) | Accuracy |
|--------|-------|---------------|----------|
| tiny   | 39MB  | ~1s           | Good     |
| base   | 74MB  | ~2s           | Better   |
| small  | 244MB | ~5s           | Great    |
| medium | 769MB | ~12s          | Excellent |
| large  | 1.5GB | ~25s          | Best     |

**GPU**: 5-10x faster with CUDA

### TTS Latency

- Piper: ~500ms for short text
- System TTS: ~200ms (platform dependent)

## Privacy

**Everything runs locally:**
- No data sent to cloud
- No API keys needed
- Works offline
- Private conversations

## License

MIT License - Same as Zenus

## Credits

- OpenAI Whisper for STT
- Piper TTS for high-quality TTS
- Porcupine for wake word detection
