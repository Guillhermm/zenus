# 🎤 Voice Interface Testing Guide

Step-by-step guide to test Zenus Voice Interface.

## Prerequisites

- Working microphone
- Speakers or headphones
- ~100MB free disk space (for Whisper model)

---

## Step 1: Pull Latest Code

```bash
cd ~/projects/zenus
git pull
./update.sh
```

---

## Step 2: Install Voice Dependencies

### Option A: Automatic (Recommended)

```bash
./install_voice.sh
```

This will install:
- System audio libraries (portaudio)
- Python packages (whisper, pyaudio, pyttsx3, etc.)

### Option B: Manual

**Linux:**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio ffmpeg
cd packages/voice
poetry install --extras full
```

**macOS:**
```bash
brew install portaudio ffmpeg
cd packages/voice
poetry install --extras full
```

---

## Step 3: Run Installation Test

```bash
python3 test_voice.py
```

**What it checks:**
- ✓ Package imports
- ✓ Dependencies installed
- ✓ Microphone detected
- ✓ TTS works
- ✓ Voice interface creation

**Expected output:**
```
🎤 ZENUS VOICE INTERFACE TEST
============================================================

📦 Test 1: Checking imports...
✓ zenus_core imported
✓ zenus_voice imported

📦 Test 2: Checking dependencies...
✓ whisper available
✓ pyaudio available
✓ pyttsx3 available
✓ webrtcvad available

🧠 Test 3: Creating Zenus orchestrator...
✓ Orchestrator created

🎤 Test 4: Checking microphone...
✓ Found 1 input device(s):
  [0] Default Microphone

🔊 Test 5: Testing TTS initialization...
✓ System TTS initialized
  Available system voices: 3
    - english-us
    - english-uk
    - spanish

🎤 Test 6: Creating voice interface...
  Creating voice interface (this may take a moment)...
  Whisper will download model on first run (~74MB for base model)...
Loading Whisper tiny model...
✓ Whisper model loaded
✓ Using system TTS
✓ Voice interface created successfully!

  Testing TTS (you should hear this)...
💬 Voice interface test successful!
✓ TTS working

============================================================
🎉 VOICE INTERFACE READY!
============================================================
```

**Troubleshooting:**

❌ **"No microphone detected"**
- Connect a microphone
- Check system audio settings
- On Linux: `arecord -l` to list devices
- On macOS: System Preferences → Sound → Input

❌ **"pyaudio not installed"**
- Linux: `sudo apt-get install portaudio19-dev && pip install pyaudio`
- macOS: `brew install portaudio && pip install pyaudio`

❌ **"whisper not installed"**
```bash
cd packages/voice
poetry install
```

---

## Step 4: Test Single Voice Command

```bash
python3 test_voice_interactive.py
```

**What happens:**
1. Zenus starts and loads Whisper
2. You'll see "🎤 Listening..."
3. **Speak a command** (e.g., "list files")
4. Zenus transcribes, executes, and responds

**Example session:**
```
🎤 Zenus Voice - Interactive Test
========================================
Initializing Zenus...
Loading voice interface (Whisper model will download on first run)...
Loading Whisper tiny model...
✓ Whisper model loaded
✓ Using system TTS

✓ Ready!
========================================

Speak your command when you see '🎤 Listening...'
Example commands:
  - 'List files in current directory'
  - 'Show system information'
  - 'What's the current time'

Press Ctrl+C to exit

🎤 Listening... (speak now)
🎤 Speech detected...
🎤 Processing...

🗣️  You said: list files in the current directory

[Zenus executes command and shows files]

💬 Alright, here are the files: file1.txt, file2.txt, README.md

========================================
✓ Command executed!
========================================
```

**Tips:**
- Speak clearly and not too fast
- Wait for "Speech detected..." before speaking
- Say "stop" or "cancel" to abort
- Press Ctrl+C to exit

---

## Step 5: Test Continuous Mode (Optional)

```bash
cd packages/voice
poetry run zenus-voice --continuous
```

**What happens:**
- Zenus keeps listening for commands
- Say commands one after another
- Say "stop listening" to exit

**Example:**
```
Voice control activated. Say 'stop listening' to exit.

🎤 Listening...
You: "list files"
Zenus: [shows files]

🎤 Listening...
You: "what's the current time"
Zenus: "It's 11:40 PM"

🎤 Listening...
You: "stop listening"
Zenus: "Goodbye!"
```

---

## Step 6: Test Different Voices (Optional)

```bash
# Female warm voice (default)
poetry run zenus-voice --voice female_warm

# Male deep voice
poetry run zenus-voice --voice male_deep

# Male neutral
poetry run zenus-voice --voice male_neutral

# Female neutral
poetry run zenus-voice --voice female_neutral
```

---

## Step 7: Test Different Models (Optional)

**Speed vs Accuracy trade-off:**

```bash
# Fastest (good for testing)
poetry run zenus-voice --model tiny

# Best balance (recommended)
poetry run zenus-voice --model base

# Better accuracy (slower)
poetry run zenus-voice --model small

# Best accuracy (much slower)
poetry run zenus-voice --model large
```

**Model sizes:**
- tiny: 39MB, ~1s latency
- base: 74MB, ~2s latency
- small: 244MB, ~5s latency
- large: 1.5GB, ~25s latency

---

## Common Issues & Solutions

### Issue: "No module named 'whisper'"

**Solution:**
```bash
cd packages/voice
poetry install
```

### Issue: "PyAudio not found"

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

### Issue: "Microphone not working"

**Test microphone:**
```bash
# Linux
arecord -d 5 test.wav && aplay test.wav

# macOS
# Go to System Preferences → Sound → Input
# Check input level meter while speaking
```

### Issue: "TTS not speaking"

**Check volume:**
- Make sure system volume is not muted
- Check speaker/headphone connection
- Try: `espeak "test"` (Linux) or `say "test"` (macOS)

### Issue: "Whisper model download failed"

**Manual download:**
```bash
# Models are cached in ~/.cache/whisper/
# Try downloading again:
python3 -c "import whisper; whisper.load_model('tiny')"
```

### Issue: "Voice recognition inaccurate"

**Solutions:**
1. Use a better model: `--model base` or `--model small`
2. Speak more clearly and slowly
3. Reduce background noise
4. Use a better microphone

---

## Advanced Testing

### Test Wake Word (Requires Setup)

**Note:** Wake word requires Picovoice access key (free at picovoice.ai)

```bash
# Set access key
export PICOVOICE_ACCESS_KEY="your-key-here"

# Start wake word detection
poetry run zenus-voice --wake-word hey_zenus
```

Now say "Hey Zenus" followed by your command.

### Test with GPU (If Available)

```bash
poetry run zenus-voice --device cuda
```

5-10x faster transcription!

---

## What to Test

**Basic Commands:**
- "list files in current directory"
- "what's the current time"
- "show me system information"

**File Operations:**
- "create a file called test.txt"
- "show me the contents of README.md"
- "delete file test.txt"

**Complex Commands:**
- "find all Python files modified today"
- "show me the largest files in this directory"
- "check if any services are down"

**Special Commands:**
- "repeat" (repeats last response)
- "stop" or "cancel" (cancels operation)
- "clear context" (clears conversation history)
- "stop listening" (exits continuous mode)

---

## Performance Expectations

**STT Latency:**
- tiny model: ~1-2 seconds
- base model: ~2-3 seconds
- small model: ~5-7 seconds

**TTS Latency:**
- System TTS: ~200ms
- Piper TTS: ~500ms (if installed)

**Accuracy:**
- Quiet environment: >95%
- Moderate noise: 80-90%
- Noisy environment: 60-80%

---

## Success Criteria

✅ Test passes if:
1. Microphone detected
2. TTS speaks successfully
3. Voice command recognized
4. Command executed by Zenus
5. Response spoken back

---

## Next Steps

Once working:
1. Try different voices and speeds
2. Test in continuous mode
3. Try complex multi-step commands
4. Set up wake word detection
5. Integrate into your workflow!

---

## Support

If you encounter issues:
1. Check this guide first
2. Review `packages/voice/README.md`
3. Check system audio settings
4. Test microphone with other apps
5. Try different Whisper models

---

**Happy voice testing!** 🎤🎉
