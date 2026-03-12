# Semantic Search Setup (Optional)

Semantic search allows Zenus to learn from past commands and find similar operations even when wording differs.

## What It Does

- Find similar past commands using AI embeddings
- Show "you did something similar before" suggestions
- Track success rates for different command types
- Learn from your usage patterns

## Requirements

**Warning:** Semantic search requires ~800MB of dependencies:
- PyTorch (ML framework)
- sentence-transformers (embedding model)
- CUDA libraries (if GPU available)

## Installation

```bash
cd ~/projects/zenus
source .venv/bin/activate
pip install -r requirements-ml.txt
```

**First run will download model:**
- Model: all-MiniLM-L6-v2 (~90MB)
- One-time download, cached locally

## Usage

Once installed, semantic search activates automatically.

**Explain mode shows similar commands:**
```bash
zenus > --explain organize my downloads
```

Output:
```
Similar past commands:
  1. ✓ organize desktop files (95% similar)
  2. ✓ clean up documents folder (87% similar)
  3. ✗ sort photos by date (82% similar)

✓ Similar commands have 67% success rate
```

## Performance

**CPU-only (typical laptop):**
- First command: ~5s (model load)
- Subsequent: <0.5s per search
- Memory: +200MB RAM

**With GPU:**
- First command: ~2s
- Subsequent: <0.1s per search

## Storage

Embeddings cached in `~/.zenus/semantic_cache/`:
```
embeddings.npy    # Vector representations (~1KB per command)
metadata.json     # Command history
```

**Estimate:** 1000 commands = ~1MB storage

## Disable Semantic Search

If you don't want it, simply don't install `requirements-ml.txt`.

Zenus will work perfectly without it:
- ✅ All core functionality works
- ✅ Command execution unchanged
- ✅ Memory and learning still work (just not semantic)
- ❌ No similarity matching
- ❌ No past command suggestions

## Troubleshooting

### "ModuleNotFoundError: No module named 'sentence_transformers'"

**Solution:** Either:
1. Install it: `pip install -r requirements-ml.txt`
2. Or ignore it - semantic search is optional

### "Downloading model files..."

**First run only.** Model cached for future use.

### High memory usage

**Solution:** Semantic search uses ML models. If memory is tight:
- Don't install requirements-ml.txt
- Or use a smaller model (edit `semantic_search.py`)

### Slow on old CPU

**Expected.** ML inference is CPU-intensive.

**Options:**
- Run on machine with GPU
- Use cloud LLM backends instead (no local ML needed)
- Skip semantic search entirely

## Architecture

```
User Command
    ↓
Semantic Search (optional)
    ├─ Encode to vector (sentence-transformers)
    ├─ Compare to past commands (cosine similarity)
    └─ Return top matches
    ↓
Explain Mode
    └─ Show similar + success rate
```

## Advanced: Custom Model

Edit `src/memory/semantic_search.py`:

```python
# Smaller model (faster, less accurate)
self.model = SentenceTransformer("all-MiniLM-L12-v2")

# Larger model (slower, more accurate)
self.model = SentenceTransformer("all-mpnet-base-v2")
```

## Is It Worth It?

**Yes if:**
- You use Zenus frequently (>10 commands/day)
- You have >4GB RAM available
- You want suggestions from past experience

**No if:**
- Occasional use
- Limited RAM (<4GB)
- Fast startup is critical
- You prefer simplicity

**Our recommendation:** Try Zenus without it first. Add later if you want the feature.
