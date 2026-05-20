# Implementation Checklist

Use this to track your progress through setup and testing.

## Phase 1: Environment Setup

- [ ] Created virtual environment: `.venv/`
- [ ] Activated venv: `source .venv/bin/activate`
- [ ] Ran: `pip install -r requirements.txt`
- [ ] Created `.env` file: `cp .env.example .env`
- [ ] Added ANTHROPIC_API_KEY to `.env`

## Phase 2: Verification

- [ ] Ran: `python test_simple.py` - All 5 tests passed
- [ ] Ran: `python debug.py` - All checks passed
- [ ] Verified database: `./data/archive.db` exists
- [ ] Verified vector store: `./data/chroma/` directory exists

## Phase 3: Seeding Data

- [ ] Ran: `python scripts/seed_corpus.py`
- [ ] Got output: "✅ Seeding complete! X articles added"
- [ ] Vector store has documents in collection

## Phase 4: Ingestion Testing

- [ ] Ran: `python scripts/trigger_once.py`
- [ ] Got output: "✅ Ingestion successful!"
- [ ] Report was saved to database
- [ ] Check logs: `tail -20 logs/agent.log`

## Phase 5: Chat System

- [ ] Ran: `streamlit run src/reportagent/ui/app.py`
- [ ] Opened: http://localhost:8501
- [ ] Latest report appears in sidebar
- [ ] Asked a question and got a response
- [ ] Response has citations

## Phase 6: Testing

- [ ] Ran: `pytest tests/ -v` - All tests passed
- [ ] Ran: `python run_full_test.py` - All 8 tests passed
- [ ] Ran: `ruff check src/` - No errors

## Phase 7: Evaluation

- [ ] Ran: `python evals/run_summary_eval.py`
- [ ] Report validation: ✅ PASS

## Phase 8: Optional - Production Simulation

- [ ] Started scheduler: `python -m reportagent.scheduler`
- [ ] Let it run for 1 cycle (60 minutes or configured interval)
- [ ] New report was generated automatically

---

## Quick Command Reference

```bash
# Activate environment
source .venv/bin/activate

# Quick test
python test_simple.py

# Diagnostic check
python debug.py

# Seed data
python scripts/seed_corpus.py

# Run ingestion once
python scripts/trigger_once.py

# Start chat UI
streamlit run src/reportagent/ui/app.py

# Run tests
pytest tests/ -v

# Full test suite
python run_full_test.py

# Linting
ruff check src/ tests/ evals/

# Structure validation
python evals/run_summary_eval.py

# Start scheduler (hourly runs)
python -m reportagent.scheduler
```

---

## Troubleshooting Quick Links

| Issue | Solution |
|-------|----------|
| "ModuleNotFoundError" | `source .venv/bin/activate` |
| "ANTHROPIC_API_KEY not set" | `nano .env` → Add key |
| "No chunks found" | `python scripts/seed_corpus.py` |
| "Connection refused" | Check .env, API quota |
| "Test fails" | Run `python debug.py` |
| "Streamlit not found" | `pip install -r requirements.txt` |

---

## Success Criteria

You'll know everything is working when:

✅ `test_simple.py` shows 5/5 passed  
✅ `debug.py` shows all 6 checks passing  
✅ `seed_corpus.py` populates vector store  
✅ `trigger_once.py` generates a report  
✅ Streamlit UI opens and displays data  
✅ Chat responds to questions with citations  
✅ `pytest` tests all pass  

---

## Files You'll Create/Modify

During setup, these files will be created:

```
.venv/                    ← Virtual environment
data/
  ├── chroma/            ← Vector store
  └── archive.db         ← Reports database
logs/
  └── agent.log          ← Application logs
.env                      ← Configuration (YOUR API KEY HERE)
```

---

## What Happens Next (Optional)

After everything works:

1. **Schedule hourly runs**: `python -m reportagent.scheduler`
2. **Monitor progress**: `tail -f logs/agent.log`
3. **Deploy to production**: See README.md Section 18
4. **Customize sources**: Edit `src/reportagent/config.py`
5. **Fine-tune prompts**: Edit ingestion/chat graph prompts

---

## Documentation Files

- **START_HERE.md** - 5-step quick start
- **QUICK_START.md** - Common commands
- **IMPLEMENTATION_GUIDE.md** - Detailed walkthrough
- **README.md** - Full specification (1000+ lines)
- **docs/architecture.md** - Technical details
- **IMPLEMENTATION_STATUS.md** - What's been built

---

Good luck! 🚀
