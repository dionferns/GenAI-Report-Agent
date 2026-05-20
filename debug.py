#!/usr/bin/env python
"""
Quick debugging script to diagnose any issues.
Run: python debug.py
"""

import sys
import os

def check_venv():
    """Check if virtual environment is active."""
    print("[CHECK] Virtual Environment")
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("  ✅ Virtual environment is active")
        print(f"     Location: {sys.prefix}")
        return True
    else:
        print("  ❌ Virtual environment NOT active")
        print("     Run: source .venv/bin/activate")
        return False

def check_env_file():
    """Check .env file exists and has API key."""
    print("\n[CHECK] Environment File")
    if not os.path.exists('.env'):
        print("  ❌ .env file not found")
        print("     Run: cp .env.example .env")
        return False

    with open('.env') as f:
        content = f.read()

    if 'ANTHROPIC_API_KEY=sk-' in content:
        print("  ✅ .env exists and has API key set")
        return True
    else:
        print("  ⚠️  .env exists but ANTHROPIC_API_KEY not set correctly")
        print("     Edit: nano .env")
        return False

def check_imports():
    """Check if all modules can be imported."""
    print("\n[CHECK] Module Imports")
    modules = [
        'reportagent.config',
        'reportagent.schemas',
        'reportagent.llm',
        'reportagent.storage.vector',
        'reportagent.storage.archive',
        'reportagent.guardrails.injection',
        'reportagent.guardrails.pii',
        'reportagent.graphs.ingestion',
        'reportagent.graphs.chat',
    ]

    failed = []
    for module in modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except Exception as e:
            print(f"  ❌ {module}: {str(e)[:60]}")
            failed.append((module, str(e)))

    return len(failed) == 0, failed

def check_database():
    """Check if database is initialized."""
    print("\n[CHECK] Database")
    try:
        from reportagent.storage.archive import Archive
        from pathlib import Path

        Path('./data').mkdir(exist_ok=True)
        Path('./logs').mkdir(exist_ok=True)

        archive = Archive()
        print("  ✅ Database initialized")

        import sqlite3
        conn = sqlite3.connect('./data/archive.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        conn.close()

        print(f"  ✅ Tables: {', '.join(tables)}")
        return True
    except Exception as e:
        print(f"  ❌ Database error: {e}")
        return False

def check_vector_store():
    """Check if vector store works."""
    print("\n[CHECK] Vector Store")
    try:
        from reportagent.storage.vector import VectorStore
        vs = VectorStore('uk_ai_regulation')
        stats = vs.get_collection_stats()
        print(f"  ✅ Vector store initialized")
        print(f"  ℹ️  {stats['document_count']} documents in store")
        return True
    except Exception as e:
        print(f"  ❌ Vector store error: {e}")
        return False

def check_llm():
    """Check if LLM works."""
    print("\n[CHECK] LLM Connectivity")
    try:
        from reportagent.llm import get_llm_provider
        provider = get_llm_provider()
        response = provider.invoke(
            [{'role': 'user', 'content': 'Say OK in one word'}],
            max_tokens=10
        )
        print(f"  ✅ LLM responding: '{response.strip()}'")
        return True
    except Exception as e:
        print(f"  ❌ LLM error: {e}")
        print("     Check: ANTHROPIC_API_KEY in .env")
        return False

def main():
    print("=" * 60)
    print("  GenAI Report Agent - Diagnostic Check")
    print("=" * 60)

    results = []

    results.append(("Virtual Env", check_venv()))
    results.append((".env File", check_env_file()))

    imports_ok, failed = check_imports()
    results.append(("Imports", imports_ok))

    results.append(("Database", check_database()))
    results.append(("Vector Store", check_vector_store()))
    results.append(("LLM", check_llm()))

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nScore: {passed}/{total}")

    if passed == total:
        print("\n🎉 Everything looks good!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} issue(s) found. See above for fixes.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
