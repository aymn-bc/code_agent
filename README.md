# Code Agent

A Python code generation agent with automatic correction. Describe a task in plain language and the agent generates, executes, reviews, and auto-corrects Python code using a local LLM via Ollama.

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) installed and running

---

## Installation

```bash
# Clone the repository
git clone https://github.com/aymn-bc/code_agent
cd code_agent

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install ollama

# Pull the default model
ollama pull qwen2.5-coder:1.5b

# Start Ollama server
ollama serve
```

---

## Usage

### Interactive mode (REPL)
```bash
python agent.py
```

### One-shot mode
```bash
python agent.py --task "write a fibonacci function"
```

### One-shot with save
```bash
python agent.py --task "write a bubble sort" --save sort.py
```

### Batch mode
```bash
python agent.py --batch tasks.json
```

### Use a different model
```bash
python agent.py --model deepseek-coder:6.7b
```

### Skip code execution
```bash
python agent.py --norun
```

---

## REPL Commands

| Command | Description |
|---------|-------------|
| `\history` | Show last 10 exchanges |
| `\save [file]` | Save last generated code to file (default: output.py) |
| `\clear` | Clear conversation history |
| `\quit` | Exit the agent |

---

## Batch File Format

```json
[
    {"task": "write a bubble sort", "output": "sort.py"},
    {"task": "parse a CSV file", "output": "parser.py"},
    {"task": "calculate the GCD of two numbers"}
]
```

Results are saved to `rapport.json` after batch execution.

---

## Architecture

```
plan()               ← parse arguments / REPL input
    ↓
generate_code()      ← LLM generates code
    ↓
evaluate()           ← execute + auto-correct (up to 3 retries)
    ↓
review_code() × 2    ← LLM improves code quality
    ↓
evaluate()           ← execute + auto-correct again
    ↓
output / save
```

---

## Configuration

| Constant | Default | Description |
|----------|---------|-------------|
| `MODEL` | `qwen2.5-coder:1.5b` | Ollama model to use |
| `MAX_RETRIES` | `3` | Max autocorrection attempts |
| `NUM_REVIEWS` | `2` | Number of review passes |
| `MAX_TOKENS` | `2048` | Max tokens per LLM call |
| `TEMPERATURE` | `0.2` | LLM creativity (0 = deterministic) |
| `MAX_HISTORY` | `20` | Max messages kept in history |

---

## Models

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| `qwen2.5-coder:1.5b` | ~1GB | Fast | Basic |
| `deepseek-coder:6.7b` | ~4GB | Medium | Good |
| `codellama:7b` | ~4GB | Medium | Good |