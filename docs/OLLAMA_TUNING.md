# Ollama Tuning Guide

## Current Configuration

Zenus uses these Ollama settings for reliable output:

```python
{
    "temperature": 0.1,       # Low = more deterministic
    "num_predict": 2048,      # Max response tokens
    "num_ctx": 8192,          # Context window size
    "top_k": 10,              # Limit vocabulary choices
    "top_p": 0.9,             # Nucleus sampling
    "timeout": 300            # 5 minutes max
}
```

## Why These Settings?

**temperature: 0.1**
- Intent translation needs consistency
- Lower = more predictable JSON output
- Trade-off: Less creative, more reliable

**num_predict: 2048**
- Allows complex multi-step plans
- Most commands need <500 tokens
- Large file operations may need more

**num_ctx: 8192**
- Fits entire system prompt + user input
- Enables context from memory
- Default models support 4k-8k

**timeout: 300s**
- Some models slow on CPU
- Complex commands take longer
- Better to wait than fail

## If Output is Still Wrong

### Symptom: Invalid JSON
```bash
# Check Ollama logs
journalctl -u ollama -f

# Test model directly
ollama run phi3:mini "Output this JSON: {\"test\": true}"
```

**Fix:** Try a different model
```bash
ollama pull qwen2.5:3b    # Better at structured output
# Edit .env: OLLAMA_MODEL=qwen2.5:3b
```

### Symptom: Wrong tools/actions
The model might not understand the schema.

**Fix:** Simplify system prompt (edit `ollama_llm.py` SYSTEM_PROMPT)

### Symptom: Too slow
**Fix 1:** Use smaller model
```bash
ollama pull llama3.2:3b   # Faster, less capable
```

**Fix 2:** Use quantized model
```bash
ollama pull phi3:mini-q4_0   # 4-bit quantization
```

**Fix 3:** Run on GPU
- Install NVIDIA drivers + CUDA
- Ollama auto-detects GPU
- 10-100x faster

## Benchmark Your Model

```bash
# Test speed
time ollama run phi3:mini "List 5 files"

# Test JSON compliance
ollama run phi3:mini '{
  "goal": "test",
  "requires_confirmation": false,
  "steps": []
}' --format json
```

Good: <3s response, valid JSON
Acceptable: 3-10s, valid JSON
Bad: >10s or invalid JSON → switch models

## Recommended Models by Hardware

**4-8GB RAM:**
- llama3.2:3b (fastest)
- phi3:mini (balanced)

**8-16GB RAM:**
- phi3:mini (recommended)
- qwen2.5:3b (best reasoning)
- mistral:7b (most capable)

**16GB+ RAM:**
- llama3:8b
- qwen2.5:7b

**GPU Available:**
- Any 7B+ model will be fast enough

## Advanced Tuning

Edit `src/brain/llm/ollama_llm.py`:

```python
"options": {
    "temperature": 0.0,      # Even more deterministic
    "num_predict": 4096,     # Double response size
    "repeat_penalty": 1.1,   # Reduce repetition
    "seed": 42,              # Reproducible (testing)
}
```

## Still Having Issues?

1. **Check Ollama version:** `ollama --version` (should be 0.1.0+)
2. **Verify model:** `ollama list`
3. **Test endpoint:** `curl http://localhost:11434/api/tags`
4. **Check system resources:** `htop` (during generation)
5. **Try cloud LLM:** Switch to OpenAI/DeepSeek temporarily to isolate problem

If Ollama works but Zenus doesn't, the issue is in intent translation prompt.
