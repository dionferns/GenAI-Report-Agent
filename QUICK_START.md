# Quick Start Guide

## Setup (One Time)

### 1. Create Virtual Environment
```bash
~/.pyenv/versions/3.11.9/bin/python3 -m venv .venv
```

### 2. Activate Virtual Environment
```bash
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
nano .env
```

---

## Testing (After Setup Complete)

### 1. Test Everything Works
```bash
source .venv/bin/activate
python run_full_test.py
```

### 2. Seed Sample Data
```bash
source .venv/bin/activate
python scripts/seed_corpus.py
```

### 3. Run One Ingestion Cycle
```bash
source .venv/bin/activate
python scripts/trigger_once.py
```

### 4. Start the Chat UI
```bash
source .venv/bin/activate
streamlit run src/reportagent/ui/app.py
```
Then open: http://localhost:8501

### 5. Run Tests
```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## Common Commands (After Activated)

Once you've run `source .venv/bin/activate`, you can run these directly:

```bash
# Test everything
python run_full_test.py

# Seed data
python scripts/seed_corpus.py

# Run ingestion
python scripts/trigger_once.py

# Chat UI
streamlit run src/reportagent/ui/app.py

# Tests
pytest tests/ -v

# Lint code
ruff check src/ tests/ evals/
```

---

## Troubleshooting

### "ModuleNotFoundError"
Make sure you've activated the venv:
```bash
source .venv/bin/activate
```

### "ANTHROPIC_API_KEY not set"
Edit your .env file and add your API key:
```bash
nano .env
# Add: ANTHROPIC_API_KEY=sk-ant-...
```

### Dependencies still installing?
The `pip install -r requirements.txt` can take a few minutes. You can check progress by running:
```bash
tail -f /path/to/output/file
```

---

## That's it!

Once dependencies are installed and .env is configured, you can start testing immediately.
