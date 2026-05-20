#!/usr/bin/env python
"""
Simple test script to verify the system is working.
Run this after: source .venv/bin/activate
"""

def test_1_imports():
    """Test 1: Can we import all modules?"""
    print("\n[Test 1] Testing imports...")
    try:
        from reportagent.config import get_settings
        from reportagent.schemas import Article, Report
        from reportagent.llm import get_llm_provider
        from reportagent.storage.vector import VectorStore
        from reportagent.storage.archive import Archive
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_2_config():
    """Test 2: Is configuration loaded?"""
    print("\n[Test 2] Testing configuration...")
    try:
        from reportagent.config import get_settings
        settings = get_settings()

        if not settings.anthropic_api_key:
            print("⚠️  ANTHROPIC_API_KEY not set in .env")
            return False

        print(f"✅ Config loaded: {settings.llm_provider}")
        return True
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False

def test_3_llm():
    """Test 3: Can we call Claude?"""
    print("\n[Test 3] Testing LLM connectivity...")
    try:
        from reportagent.llm import get_llm_provider
        provider = get_llm_provider()
        response = provider.invoke(
            [{'role': 'user', 'content': 'Say "Hello" in one word only'}],
            max_tokens=20
        )
        print(f"✅ Claude responded: '{response.strip()}'")
        return True
    except Exception as e:
        print(f"❌ LLM test failed: {e}")
        return False

def test_4_database():
    """Test 4: Can we access the database?"""
    print("\n[Test 4] Testing database...")
    try:
        from pathlib import Path
        Path("./data").mkdir(exist_ok=True)
        Path("./logs").mkdir(exist_ok=True)

        from reportagent.storage.archive import Archive
        archive = Archive()
        print("✅ Database initialized")
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_5_vector_store():
    """Test 5: Can we use the vector store?"""
    print("\n[Test 5] Testing vector store...")
    try:
        from reportagent.storage.vector import VectorStore
        from reportagent.schemas import Chunk
        from sentence_transformers import SentenceTransformer

        vs = VectorStore('uk_ai_regulation')
        embedder = SentenceTransformer('all-MiniLM-L6-v2')
        embedding = embedder.encode('test').tolist()

        chunk = Chunk(
            article_id='test',
            text='test chunk',
            chunk_index=0,
            embedding=embedding,
            metadata={'url': 'test'}
        )
        vs.upsert_chunks([chunk])
        print("✅ Vector store working")
        return True
    except Exception as e:
        print(f"❌ Vector store test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("  GenAI Report Agent - Simple Test Suite")
    print("=" * 60)

    tests = [
        test_1_imports,
        test_2_config,
        test_3_llm,
        test_4_database,
        test_5_vector_store,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed!")
        print("\nNext steps:")
        print("  1. python scripts/seed_corpus.py")
        print("  2. streamlit run src/reportagent/ui/app.py")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
