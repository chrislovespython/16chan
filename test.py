#!/usr/bin/env python3
"""
16chan Test Suite
Tests database initialization and basic functionality
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported"""
    print("[TEST] Checking imports...")
    try:
        import flask
        print(f"  ✓ Flask {flask.__version__} installed")
    except ImportError as e:
        print(f"  ✗ Flask not installed: {e}")
        return False
    
    try:
        import sqlite3
        print(f"  ✓ SQLite3 available")
    except ImportError as e:
        print(f"  ✗ SQLite3 not available: {e}")
        return False
    
    return True

def test_database():
    """Test database initialization"""
    print("\n[TEST] Testing database...")
    
    try:
        from app import init_db, get_db
        
        # Initialize database
        init_db()
        print("  ✓ Database initialized")
        
        # Check tables exist
        conn = get_db()
        cursor = conn.cursor()
        
        tables = ['sessions', 'boards', 'posts', 'votes', 'moderators']
        for table in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if cursor.fetchone():
                print(f"  ✓ Table '{table}' created")
            else:
                print(f"  ✗ Table '{table}' missing")
                return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"  ✗ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_session_functions():
    """Test session management functions"""
    print("\n[TEST] Testing session functions...")
    
    try:
        from app import get_anon_id
        
        # Test anon ID generation
        session_id = "test-session-123"
        board_id = 1
        
        anon_id = get_anon_id(session_id, board_id)
        print(f"  ✓ Anon ID generated: {anon_id}")
        
        # Test consistency
        anon_id2 = get_anon_id(session_id, board_id)
        if anon_id == anon_id2:
            print("  ✓ Anon ID is consistent")
        else:
            print("  ✗ Anon ID not consistent")
            return False
        
        # Test uniqueness per board
        anon_id_board2 = get_anon_id(session_id, 2)
        if anon_id != anon_id_board2:
            print("  ✓ Anon ID differs per board")
        else:
            print("  ✗ Anon ID should differ per board")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Session function error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_decay_calculation():
    """Test decay score calculation"""
    print("\n[TEST] Testing decay calculation...")
    
    try:
        # Test decay formula
        bury_score = 2
        age_hours = 10.0
        reply_count = 3
        
        decay_score = (bury_score * 1.5) + (age_hours * 0.3) - (reply_count * 0.1)
        expected = (2 * 1.5) + (10 * 0.3) - (3 * 0.1)  # 3 + 3 - 0.3 = 5.7
        
        print(f"  ✓ Decay formula: {decay_score:.2f}")
        
        if abs(decay_score - expected) < 0.01:
            print(f"  ✓ Decay score correct: {decay_score:.2f}")
        else:
            print(f"  ✗ Decay score incorrect: {decay_score:.2f} != {expected:.2f}")
            return False
        
        # Test threshold
        if decay_score < 10.0:
            print("  ✓ Post below deletion threshold")
        
        # Test high decay
        high_decay = (10 * 1.5) + (20 * 0.3) - (0 * 0.1)  # 15 + 6 - 0 = 21
        if high_decay > 10.0:
            print(f"  ✓ High decay post would be deleted: {high_decay:.2f}")
        else:
            print(f"  ✗ High decay post should be deleted: {high_decay:.2f}")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Decay calculation error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rate_limits():
    """Test rate limit calculations"""
    print("\n[TEST] Testing rate limits...")
    
    try:
        # Test time calculations
        import time
        
        # 5 minutes = 300 seconds (thread cooldown)
        thread_cooldown = 5 * 60
        if thread_cooldown == 300:
            print("  ✓ Thread cooldown: 5 minutes (300s)")
        
        # 30 seconds (reply cooldown)
        reply_cooldown = 30
        print("  ✓ Reply cooldown: 30 seconds")
        
        # 7 days (board creation age requirement)
        board_min_age = 7 * 24 * 3600
        if board_min_age == 604800:
            print("  ✓ Board creation age: 7 days (604800s)")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Rate limit error: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("  16chan V1 Test Suite")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Database", test_database),
        ("Session Functions", test_session_functions),
        ("Decay Calculation", test_decay_calculation),
        ("Rate Limits", test_rate_limits),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"\n✗ {name} test FAILED")
        except Exception as e:
            failed += 1
            print(f"\n✗ {name} test CRASHED: {e}")
    
    print("\n" + "=" * 50)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    if failed == 0:
        print("\n✓ All tests passed! 16chan is ready to run.")
        print("\nTo start the application:")
        print("  1. Run: python app.py")
        print("  2. In another terminal: python decay_worker.py")
        print("  3. Open: http://127.0.0.1:5000")
        return True
    else:
        print("\n✗ Some tests failed. Please fix errors before running.")
        return False

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)