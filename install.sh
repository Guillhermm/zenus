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
    echo "   - Latest: claude-3-5-sonnet-20241022"
    echo "   - Cost: ~\$3/1M input tokens"
    echo ""
    echo "2) DeepSeek (best value)"
    echo "   - Excellent code capabilities"
    echo "   - Latest: deepseek-chat, deepseek-coder"
    echo "   - Cost: ~\$0.14/1M tokens (20x cheaper)"
    echo ""
    echo "3) OpenAI (fast and reliable)"
    echo "   - Latest: gpt-4o, o1-preview"
    echo "   - Cost: ~\$2.50/1M input tokens"
    echo ""
    echo "4) Ollama (Local, FREE - privacy-first)"
    echo "   - Runs on your hardware"
    echo "   - Popular: llama3.2, qwen2.5, phi3"
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
            echo "1) claude-3-5-sonnet-20241022 (recommended - best reasoning)"
            echo "2) claude-3-5-haiku-20241022 (fast - good for simple tasks)"
            echo "3) claude-3-opus-20240229 (most capable - expensive)"
            
            read -p "Enter choice [1-3]: " model_choice
            
            case $model_choice in
                1) PRIMARY_MODEL="claude-3-5-sonnet-20241022" ;;
                2) PRIMARY_MODEL="claude-3-5-haiku-20241022" ;;
                3) PRIMARY_MODEL="claude-3-opus-20240229" ;;
                *) PRIMARY_MODEL="claude-3-5-sonnet-20241022" ;;
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
            echo "1) deepseek-chat (recommended - general purpose)"
            echo "2) deepseek-coder (specialized for code)"
            
            read -p "Enter choice [1-2]: " model_choice
            
            case $model_choice in
                1) PRIMARY_MODEL="deepseek-chat" ;;
                2) PRIMARY_MODEL="deepseek-coder" ;;
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
            echo "1) gpt-4o (recommended - best overall)"
            echo "2) gpt-4o-mini (fast and cheap)"
            echo "3) o1-preview (advanced reasoning - slow)"
            echo "4) o1-mini (reasoning - faster)"
            
            read -p "Enter choice [1-4]: " model_choice
            
            case $model_choice in
                1) PRIMARY_MODEL="gpt-4o" ;;
                2) PRIMARY_MODEL="gpt-4o-mini" ;;
                3) PRIMARY_MODEL="o1-preview" ;;
                4) PRIMARY_MODEL="o1-mini" ;;
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
            echo "1) llama3.2:3b (recommended - fast, 2GB)"
            echo "2) qwen2.5:7b (excellent reasoning, 4.7GB)"
            echo "3) phi3:mini (efficient, 2.3GB)"
            echo "4) mistral:7b (good balance, 4.1GB)"
            echo "5) codellama:7b (code-focused, 3.8GB)"
            
            read -p "Enter choice [1-5]: " model_choice
            
            case $model_choice in
                1) PRIMARY_MODEL="llama3.2:3b" ;;
                2) PRIMARY_MODEL="qwen2.5:7b" ;;
                3) PRIMARY_MODEL="phi3:mini" ;;
                4) PRIMARY_MODEL="mistral:7b" ;;
                5) PRIMARY_MODEL="codellama:7b" ;;
                *) PRIMARY_MODEL="llama3.2:3b" ;;
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
