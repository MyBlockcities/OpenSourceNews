#!/usr/bin/env python3
"""
Quick test script to verify scheduler improvements
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def test_deduplication():
    """Test URL-based deduplication"""
    from pipelines.daily_run import deduplicate_items
    
    items = [
        {'url': 'https://example.com/1', 'title': 'A'},
        {'url': 'https://example.com/1', 'title': 'A'},  # Duplicate
        {'url': 'https://example.com/2', 'title': 'B'},
        {'url': 'https://example.com/3', 'title': 'C'},
        {'url': 'https://example.com/2', 'title': 'B'},  # Duplicate
    ]
    
    unique = deduplicate_items(items)
    
    assert len(unique) == 3, f"Expected 3 unique items, got {len(unique)}"
    urls = [item['url'] for item in unique]
    assert len(urls) == len(set(urls)), "Deduplication failed - duplicates still present"
    
    print("✅ Deduplication test PASSED")
    return True

def test_rss_feeds():
    """Test updated RSS feed URLs"""
    from pipelines.daily_run import fetch_rss
    
    # Test Google AI Blog (updated URL)
    print("\nTesting Google AI Blog RSS feed...")
    items = fetch_rss('https://blog.google/technology/ai/rss/', limit=3)
    
    if items and len(items) > 0:
        print(f"✅ Google AI Blog RSS: {len(items)} items fetched")
        print(f"   Sample: {items[0].get('title', 'N/A')[:60]}...")
        return True
    else:
        print("⚠️  Google AI Blog RSS: No items (may need different URL)")
        return False

def test_gemini_error_handling():
    """Test that Gemini error handling code is in place"""
    import inspect
    from pipelines.daily_run import analyze_with_transcript
    
    source = inspect.getsource(analyze_with_transcript)
    
    checks = [
        ('hasattr(response, \'text\')', 'Multi-level response extraction'),
        ('startswith(\'```\')', 'Markdown cleanup'),
        ('json.JSONDecodeError', 'JSON error handling'),
        ('type(e).__name__', 'Detailed error logging'),
    ]
    
    all_passed = True
    for check, description in checks:
        if check in source:
            print(f"✅ {description}: Present")
        else:
            print(f"❌ {description}: Missing")
            all_passed = False
    
    return all_passed

def main():
    print("=" * 60)
    print("SCHEDULER IMPROVEMENTS - LOCAL TESTS")
    print("=" * 60)
    
    tests = [
        ("Deduplication Logic", test_deduplication),
        ("RSS Feed URLs", test_rss_feeds),
        ("Gemini Error Handling", test_gemini_error_handling),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n📋 Testing: {name}")
        print("-" * 60)
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests PASSED! Ready for deployment.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review before deployment.")
        return 1

if __name__ == "__main__":
    sys.exit(main())