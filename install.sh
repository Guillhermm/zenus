#!/bin/bash
set -e

echo "╔════════════════════════════════════╗"
echo "║   Zenus OS Installation Script     ║"
echo "╚════════════════════════════════════╝"
echo ""

# Get absolute path to project
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    echo "Installing Python 3..."
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# Check/Install Poetry
echo "════════════════════════════════════"
echo "  Checking Poetry..."
echo "════════════════════════════════════"
echo ""

if ! command -v poetry &> /dev/null; then
    echo "Poetry not found. Installing..."
    curl -sSL https://install.python-poetry.org | python3 -
    
    # Add poetry to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"
    
    echo "✓ Poetry installed: $(poetry --version)"
else
    echo "✓ Poetry already installed: $(poetry --version)"
fi

echo ""
echo "════════════════════════════════════"
echo "  Installing Zenus Packages..."
echo "════════════════════════════════════"
echo ""

# Install core package first
echo "→ Installing zenus-core..."
cd "$PROJECT_DIR/packages/core"
poetry install --no-interaction --quiet
echo "✓ zenus-core installed"

# Install CLI package
echo "→ Installing zenus-cli..."
cd "$PROJECT_DIR/packages/cli"
poetry install --no-interaction --quiet
echo "✓ zenus-cli installed"

# Install TUI package
echo "→ Installing zenus-tui..."
cd "$PROJECT_DIR/packages/tui"
poetry install --no-interaction --quiet
echo "✓ zenus-tui installed"

cd "$PROJECT_DIR"

echo ""
echo "════════════════════════════════════"
echo "  LLM Configuration"
echo "════════════════════════════════════"
echo ""

# Config files locations
# When running from source: .env in project directory
# config.yaml can be in ~/.zenus/ for user preferences OR project directory
SECRETS_FILE="$PROJECT_DIR/.env"
CONFIG_FILE="$PROJECT_DIR/config.yaml"

echo "Running from source, using project directory for config"

# Check if already configured
SKIP_CONFIG=false
if [ -f "$CONFIG_FILE" ] && [ -f "$SECRETS_FILE" ]; then
    echo ""
    echo "⚠️  Configuration already exists:"
    echo "  Config: $CONFIG_FILE"
    echo "  Secrets: $SECRETS_FILE"
    echo ""
    read -p "Reconfigure? (y/N): " reconfigure
    if [ "$reconfigure" != "y" ] && [ "$reconfigure" != "Y" ]; then
        SKIP_CONFIG=true
        echo "Keeping existing configuration"
    fi
fi

if [ "$SKIP_CONFIG" = "false" ]; then
    echo ""
    echo "Creating configuration files..."
    
    # Copy base config
    if [ ! -f "$PROJECT_DIR/config.yaml.example" ]; then
        echo "❌ Error: config.yaml.example not found in $PROJECT_DIR"
        exit 1
    fi
    
    cp "$PROJECT_DIR/config.yaml.example" "$CONFIG_FILE"
    echo "✓ Created: $CONFIG_FILE"
    
    # Create secrets file
    > "$SECRETS_FILE"
    chmod 600 "$SECRETS_FILE"
    echo "✓ Created: $SECRETS_FILE (chmod 600)"
    
    echo ""
    echo "Choose your PRIMARY LLM backend:"
    echo ""
    echo "1) Anthropic Claude (recommended for complex tasks)"
    echo "   - Best reasoning and code generation"
    echo "   - Models: claude-sonnet-4-6, claude-opus-4-6, claude-haiku-4-5"
    echo "   - Cost: ~\$3/1M input tokens"
    echo ""
    echo "2) DeepSeek (best value)"
    echo "   - Excellent code and reasoning capabilities"
    echo "   - Models: deepseek-chat (V3), deepseek-reasoner (R1)"
    echo "   - Cost: ~\$0.27/1M tokens (10x cheaper than Claude)"
    echo ""
    echo "3) OpenAI"
    echo "   - Models: gpt-4o, gpt-4.1, o3, o4-mini"
    echo "   - Cost: ~\$2.50/1M input tokens"
    echo ""
    echo "4) Ollama (Local, FREE - privacy-first)"
    echo "   - Runs on your hardware, no API key needed"
    echo "   - Popular: llama3.1, qwen3, deepseek-r1, mistral"
    echo "   - Requires 4-16GB RAM"
    echo ""

    read -p "Enter choice [1-4]: " primary_choice

    PRIMARY_PROVIDER=""
    PRIMARY_MODEL=""

    case $primary_choice in
        1)
            PRIMARY_PROVIDER="anthropic"
            echo ""
            read -sp "Enter your Anthropic API key: " api_key
            echo ""
            
            if [ -z "$api_key" ]; then
                echo "❌ Error: API key cannot be empty"
                exit 1
            fi
            
            echo "ANTHROPIC_API_KEY=$api_key" >> "$SECRETS_FILE"
            
            echo ""
            echo "Choose Claude model:"
            echo "1) claude-sonnet-4-6  (recommended - best speed/intelligence balance)"
            echo "2) claude-opus-4-6    (most capable - best for complex agents & coding)"
            echo "3) claude-haiku-4-5   (fastest - near-frontier, great for simple tasks)"

            read -p "Enter choice [1-3]: " model_choice

            case $model_choice in
                1) PRIMARY_MODEL="claude-sonnet-4-6" ;;
                2) PRIMARY_MODEL="claude-opus-4-6" ;;
                3) PRIMARY_MODEL="claude-haiku-4-5" ;;
                *) PRIMARY_MODEL="claude-sonnet-4-6" ;;
            esac
            
            echo "✓ Anthropic configured with $PRIMARY_MODEL"
            ;;
            
        2)
            PRIMARY_PROVIDER="deepseek"
            echo ""
            echo "Get your API key from: https://platform.deepseek.com"
            echo ""
            read -sp "Enter your DeepSeek API key: " api_key
            echo ""
            
            if [ -z "$api_key" ]; then
                echo "❌ Error: API key cannot be empty"
                exit 1
            fi
            
            echo "DEEPSEEK_API_KEY=$api_key" >> "$SECRETS_FILE"
            
            echo ""
            echo "Choose DeepSeek model:"
            echo "1) deepseek-chat      (recommended - DeepSeek-V3, general purpose, 8K output)"
            echo "2) deepseek-reasoner  (DeepSeek-R1, chain-of-thought reasoning, 64K output)"

            read -p "Enter choice [1-2]: " model_choice

            case $model_choice in
                1) PRIMARY_MODEL="deepseek-chat" ;;
                2) PRIMARY_MODEL="deepseek-reasoner" ;;
                *) PRIMARY_MODEL="deepseek-chat" ;;
            esac
            
            echo "✓ DeepSeek configured with $PRIMARY_MODEL"
            ;;
            
        3)
            PRIMARY_PROVIDER="openai"
            echo ""
            echo "Get your API key from: https://platform.openai.com/api-keys"
            echo ""
            read -sp "Enter your OpenAI API key: " api_key
            echo ""
            
            if [ -z "$api_key" ]; then
                echo "❌ Error: API key cannot be empty"
                exit 1
            fi
            
            echo "OPENAI_API_KEY=$api_key" >> "$SECRETS_FILE"
            
            echo ""
            echo "Choose OpenAI model:"
            echo "1) gpt-4o        (recommended - flagship multimodal model)"
            echo "2) gpt-4o-mini   (fast and cost-efficient)"
            echo "3) gpt-4.1       (strong instruction-following, 1M context)"
            echo "4) o3            (frontier reasoning - math, coding, science)"
            echo "5) o4-mini       (cost-efficient reasoning)"

            read -p "Enter choice [1-5]: " model_choice

            case $model_choice in
                1) PRIMARY_MODEL="gpt-4o" ;;
                2) PRIMARY_MODEL="gpt-4o-mini" ;;
                3) PRIMARY_MODEL="gpt-4.1" ;;
                4) PRIMARY_MODEL="o3" ;;
                5) PRIMARY_MODEL="o4-mini" ;;
                *) PRIMARY_MODEL="gpt-4o" ;;
            esac
            
            echo "✓ OpenAI configured with $PRIMARY_MODEL"
            ;;
            
        4)
            PRIMARY_PROVIDER="ollama"
            echo ""
            echo "Setting up Ollama..."
            
            # Check if ollama installed
            if ! command -v ollama &> /dev/null; then
                echo "Ollama not found. Installing..."
                curl -fsSL https://ollama.com/install.sh | sh
            fi
            
            echo "✓ Ollama installed"
            
            # Start Ollama service
            echo "Starting Ollama service..."
            
            # Try systemctl first (most common)
            if command -v systemctl &> /dev/null; then
                sudo systemctl start ollama 2>/dev/null || true
                sudo systemctl enable ollama 2>/dev/null || true
            fi
            
            # Start manually if service not available
            if ! pgrep -x ollama &> /dev/null; then
                echo "Starting Ollama in background..."
                nohup ollama serve > /dev/null 2>&1 &
                sleep 2
            fi
            
            # Verify it's running
            if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
                echo "⚠️  Ollama service didn't start automatically"
                echo "Please run: ollama serve"
                echo "Then run this installer again"
                exit 1
            fi
            
            echo "✓ Ollama service running"
            echo ""
            echo "Choose a model:"
            echo "1) llama3.1:8b      (recommended - most popular, great general model, ~5GB)"
            echo "2) qwen3:8b         (Qwen 3 latest generation, excellent reasoning, ~5GB)"
            echo "3) deepseek-r1:7b   (reasoning model, think-before-answer, ~4.7GB)"
            echo "4) mistral:7b       (fast and capable, good for coding, ~4.1GB)"
            echo "5) llama3.2:3b      (small & fast, low memory, ~2GB)"
            echo "6) phi4:14b         (Microsoft Phi-4, efficient, ~8.5GB)"
            echo "7) gemma3:4b        (Google Gemma 3, lightweight, ~3.3GB)"
            echo "8) qwen2.5-coder:7b (code-specialized, ~4.7GB)"

            read -p "Enter choice [1-8]: " model_choice

            case $model_choice in
                1) PRIMARY_MODEL="llama3.1:8b" ;;
                2) PRIMARY_MODEL="qwen3:8b" ;;
                3) PRIMARY_MODEL="deepseek-r1:7b" ;;
                4) PRIMARY_MODEL="mistral:7b" ;;
                5) PRIMARY_MODEL="llama3.2:3b" ;;
                6) PRIMARY_MODEL="phi4:14b" ;;
                7) PRIMARY_MODEL="gemma3:4b" ;;
                8) PRIMARY_MODEL="qwen2.5-coder:7b" ;;
                *) PRIMARY_MODEL="llama3.1:8b" ;;
            esac
            
            echo "Pulling model $PRIMARY_MODEL (this may take a few minutes)..."
            ollama pull $PRIMARY_MODEL
            
            echo "OLLAMA_MODEL=$PRIMARY_MODEL" >> "$SECRETS_FILE"
            echo "✓ Ollama configured with $PRIMARY_MODEL"
            ;;
            
        *)
            echo "❌ Invalid choice"
            exit 1
            ;;
    esac
    
    # Update config.yaml with primary provider
    sed -i "s/provider: anthropic/provider: $PRIMARY_PROVIDER/" "$CONFIG_FILE"
    sed -i "s/model: claude-3-5-sonnet-20241022/model: $PRIMARY_MODEL/" "$CONFIG_FILE"
    
    echo ""
    echo "✓ Primary provider configured: $PRIMARY_PROVIDER ($PRIMARY_MODEL)"
    
    echo ""
    echo "════════════════════════════════════"
    echo "  Fallback Configuration (Optional)"
    echo "════════════════════════════════════"
    echo ""
    echo "Zenus can route tasks to different models based on complexity"
    echo "and fallback to more powerful models when needed."
    echo ""
    echo "Benefits:"
    echo "  • Save money (simple tasks → cheap models)"
    echo "  • Reliability (automatic fallback on failure)"
    echo "  • Flexibility (use best model for each task)"
    echo ""
    read -p "Configure fallback providers? (Y/n): " configure_fallback
    
    if [ "$configure_fallback" = "n" ] || [ "$configure_fallback" = "N" ]; then
        # Disable fallback in config
        sed -i '/^fallback:/,/^[^ ]/ s/enabled: true/enabled: false/' "$CONFIG_FILE"
        # Clear the providers list to only include primary (prevents router from trying others)
        sed -i "/^fallback:/,/^[^ ]/ {
            /providers:/,/^[^ ]/ {
                /providers:/!d
                a\\    - $PRIMARY_PROVIDER
            }
        }" "$CONFIG_FILE"
        echo "✓ Fallback disabled (single provider mode)"
    else
        echo ""
        echo "Available fallback providers:"
        FALLBACK_OPTIONS=""
        FALLBACK_COUNT=0
        
        if [ "$PRIMARY_PROVIDER" != "anthropic" ]; then
            FALLBACK_COUNT=$((FALLBACK_COUNT + 1))
            echo "  [$FALLBACK_COUNT] Anthropic Claude"
            FALLBACK_OPTIONS="${FALLBACK_OPTIONS}anthropic:$FALLBACK_COUNT "
        fi
        if [ "$PRIMARY_PROVIDER" != "deepseek" ]; then
            FALLBACK_COUNT=$((FALLBACK_COUNT + 1))
            echo "  [$FALLBACK_COUNT] DeepSeek"
            FALLBACK_OPTIONS="${FALLBACK_OPTIONS}deepseek:$FALLBACK_COUNT "
        fi
        if [ "$PRIMARY_PROVIDER" != "openai" ]; then
            FALLBACK_COUNT=$((FALLBACK_COUNT + 1))
            echo "  [$FALLBACK_COUNT] OpenAI"
            FALLBACK_OPTIONS="${FALLBACK_OPTIONS}openai:$FALLBACK_COUNT "
        fi
        if [ "$PRIMARY_PROVIDER" != "ollama" ]; then
            FALLBACK_COUNT=$((FALLBACK_COUNT + 1))
            echo "  [$FALLBACK_COUNT] Ollama (local)"
            FALLBACK_OPTIONS="${FALLBACK_OPTIONS}ollama:$FALLBACK_COUNT "
        fi
        
        echo ""
        echo "Enter numbers separated by space (e.g., '1 3' for first and third)"
        echo "Or press Enter to skip fallback configuration"
        read -p "Fallback providers: " fallback_choices
        
        if [ -n "$fallback_choices" ]; then
            for choice in $fallback_choices; do
                for option in $FALLBACK_OPTIONS; do
                    provider="${option%:*}"
                    number="${option#*:}"
                    
                    if [ "$choice" = "$number" ]; then
                        case $provider in
                            anthropic)
                                echo ""
                                read -sp "Enter Anthropic API key: " api_key
                                echo ""
                                echo "ANTHROPIC_API_KEY=$api_key" >> "$SECRETS_FILE"
                                echo "✓ Anthropic added as fallback"
                                ;;
                            deepseek)
                                echo ""
                                read -sp "Enter DeepSeek API key: " api_key
                                echo ""
                                echo "DEEPSEEK_API_KEY=$api_key" >> "$SECRETS_FILE"
                                echo "✓ DeepSeek added as fallback"
                                ;;
                            openai)
                                echo ""
                                read -sp "Enter OpenAI API key: " api_key
                                echo ""
                                echo "OPENAI_API_KEY=$api_key" >> "$SECRETS_FILE"
                                echo "✓ OpenAI added as fallback"
                                ;;
                            ollama)
                                if command -v ollama &> /dev/null; then
                                    echo "✓ Ollama added as fallback"
                                else
                                    echo "⚠️  Ollama not installed, skipping"
                                fi
                                ;;
                        esac
                    fi
                done
            done
            
            echo ""
            echo "✓ Fallback providers configured"
            echo "  Edit $CONFIG_FILE to customize fallback order"
        else
            sed -i '/^fallback:/,/^[^ ]/ s/enabled: true/enabled: false/' "$CONFIG_FILE"
            echo "✓ Fallback skipped"
        fi
    fi
    
    echo ""
    echo "════════════════════════════════════"
    echo "  Verifying Configuration..."
    echo "════════════════════════════════════"
    echo ""
    
    if [ -f "$CONFIG_FILE" ]; then
        echo "✓ Config file created: $CONFIG_FILE"
    else
        echo "❌ Error: Config file not created!"
        exit 1
    fi
    
    if [ -f "$SECRETS_FILE" ]; then
        echo "✓ Secrets file created: $SECRETS_FILE"
        echo "  Permissions: $(ls -l "$SECRETS_FILE" | awk '{print $1}')"
    else
        echo "❌ Error: Secrets file not created!"
        exit 1
    fi
    
    echo ""
    echo "Configuration summary:"
    echo "  Primary: $PRIMARY_PROVIDER ($PRIMARY_MODEL)"
    grep -q "enabled: true" <<< "$(sed -n '/^fallback:/,/^[^ ]/p' "$CONFIG_FILE")" && \
        echo "  Fallback: Enabled" || echo "  Fallback: Disabled"
fi

echo ""
echo "════════════════════════════════════"
echo "  Setting up shell aliases..."
echo "════════════════════════════════════"
echo ""

# Define the aliases
ZENUS_ALIAS="alias zenus='$PROJECT_DIR/zenus.sh'"
ZENUS_TUI_ALIAS="alias zenus-tui='$PROJECT_DIR/zenus-tui.sh'"

# Check if aliases already exist in bashrc
if grep -q "alias zenus=" ~/.bashrc 2>/dev/null; then
    echo "⚠️  Zenus aliases already exist in ~/.bashrc"
    echo "   Updating to current paths..."
    
    # Remove old aliases
    sed -i '/alias zenus_os=/d' ~/.bashrc
    sed -i '/alias zenus=/d' ~/.bashrc
    sed -i '/alias zenus-tui=/d' ~/.bashrc
    
    # Add new aliases
    echo "" >> ~/.bashrc
    echo "# Zenus OS aliases" >> ~/.bashrc
    echo "$ZENUS_ALIAS" >> ~/.bashrc
    echo "$ZENUS_TUI_ALIAS" >> ~/.bashrc
    
    echo "✓ Aliases updated"
else
    # Add aliases for the first time
    echo "" >> ~/.bashrc
    echo "# Zenus OS aliases" >> ~/.bashrc
    echo "$ZENUS_ALIAS" >> ~/.bashrc
    echo "$ZENUS_TUI_ALIAS" >> ~/.bashrc
    
    echo "✓ Aliases added to ~/.bashrc"
fi

echo ""
echo "════════════════════════════════════"
echo "  Installation Complete! 🚀"
echo "════════════════════════════════════"
echo ""
echo "Configuration:"
echo "  $CONFIG_FILE"
echo "  $SECRETS_FILE"
echo ""
echo "To start using Zenus:"
echo "  source ~/.bashrc"
echo ""
echo "Then run:"
echo "  zenus              # Interactive shell"
echo "  zenus help         # Show help"
echo "  zenus \"command\"    # Direct execution"
echo "  zenus-tui          # Launch TUI interface"
echo ""
