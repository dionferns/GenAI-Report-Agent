#!/bin/bash
set -e

echo "=========================================="
echo "  GenAI Report Agent - Setup Script"
echo "=========================================="

# Step 1: Create venv
echo ""
echo "[1/4] Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "  ⚠️  .venv already exists, skipping..."
else
    ~/.pyenv/versions/3.11.9/bin/python3 -m venv .venv
    echo "  ✅ Virtual environment created"
fi

# Step 2: Activate and install
echo ""
echo "[2/4] Activating virtual environment and upgrading pip..."
source .venv/bin/activate
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
echo "  ✅ Pip upgraded"

# Step 3: Install dependencies
echo ""
echo "[3/4] Installing dependencies (this may take 2-3 minutes)..."
pip install -r requirements.txt > /dev/null 2>&1
echo "  ✅ Dependencies installed"

# Step 4: Check .env
echo ""
echo "[4/4] Checking configuration..."
if [ ! -f ".env" ]; then
    echo "  ℹ️  Creating .env from template..."
    cp .env.example .env
    echo "  ⚠️  IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY"
    echo "     Run: nano .env"
else
    if grep -q "ANTHROPIC_API_KEY=sk-" .env; then
        echo "  ✅ ANTHROPIC_API_KEY is set"
    else
        echo "  ⚠️  ANTHROPIC_API_KEY not configured in .env"
        echo "     Run: nano .env"
    fi
fi

echo ""
echo "=========================================="
echo "  ✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Make sure .env has your ANTHROPIC_API_KEY"
echo "  2. Run: source .venv/bin/activate"
echo "  3. Run: python run_full_test.py"
echo "  4. Run: python scripts/seed_corpus.py"
echo "  5. Run: streamlit run src/reportagent/ui/app.py"
echo ""
