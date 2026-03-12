#!/bin/bash
# Install Zenus Voice dependencies

echo "🎤 Installing Zenus Voice Dependencies"
echo "======================================"

# Check OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Detected: Linux"
    
    # Install system dependencies
    echo ""
    echo "Installing system audio libraries..."
    sudo apt-get update
    sudo apt-get install -y portaudio19-dev python3-pyaudio ffmpeg
    
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Detected: macOS"
    
    # Check if brew is installed
    if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew not found. Install from https://brew.sh"
        exit 1
    fi
    
    echo ""
    echo "Installing system audio libraries..."
    brew install portaudio ffmpeg
    
else
    echo "⚠️  Unsupported OS: $OSTYPE"
    echo "Please install portaudio manually:"
    echo "  - Windows: Download PyAudio wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio"
    echo "  - Linux: sudo apt-get install portaudio19-dev"
    echo "  - macOS: brew install portaudio"
    exit 1
fi

echo ""
echo "✓ System dependencies installed"
echo ""
echo "Installing Python packages..."

# Install voice package
cd packages/voice
poetry install --extras full

echo ""
echo "======================================"
echo "✓ Installation complete!"
echo "======================================"
echo ""
echo "Test the installation:"
echo "  python3 test_voice.py"
echo ""
echo "Try voice control:"
echo "  python3 test_voice_interactive.py"
echo ""
