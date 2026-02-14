"""
Production Database Configuration Helper
This script adds PostgreSQL support to app.py and decay_worker.py
Run this before deploying to production
"""

import os
import shutil

def backup_file(filepath):
    """Create a backup of the file"""
    backup_path = f"{filepath}.backup"
    shutil.copy(filepath, backup_path)
    print(f"✓ Created backup: {backup_path}")

def add_postgres_support_to_app():
    """Add PostgreSQL support to app.py"""
    print("\n[1/2] Updating app.py for PostgreSQL...")
    
    with open('app.py', 'r') as f:
        content = f.read()
    
    # Check if already updated
    if 'psycopg2' in content:
        print("✓ app.py already has PostgreSQL support")
        return
    
    # Backup first
    backup_file('app.py')
    
    # Add imports at the top
    import_section = '''"""
16chan V1 - Anonymous imageboard with decay mechanics
Main Flask application handling all routes and core logic
Production version with PostgreSQL support
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import hashlib
import time
import uuid
from functools import wraps
import os

# Database configuration - supports both SQLite (dev) and PostgreSQL (production)
if os.environ.get('DATABASE_URL'):
    # Production: Use PostgreSQL
    import psycopg2
    from psycopg2.extras import RealDictCursor
    DATABASE_URL = os.environ['DATABASE_URL']
    USE_POSTGRES = True
    print("[INFO] Using PostgreSQL database (production mode)")
else:
    # Development: Use SQLite
    import sqlite3
    DATABASE = 'db.sqlite'
    USE_POSTGRES = False
    print("[INFO] Using SQLite database (development mode)")
'''
    
    # Replace the imports section
    lines = content.split('\n')
    
    # Find where imports end (look for first function or class definition)
    import_end = 0
    for i, line in enumerate(lines):
        if line.startswith('app = Flask'):
            import_end = i
            break
    
    # Reconstruct file
    new_content = import_section + '\n' + '\n'.join(lines[import_end:])
    
    # Update get_db function
    old_get_db = '''def get_db():
    """Get database connection with row factory for dict-like access"""
    debug_print(f"Opening database connection to {DATABASE}")
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn'''
    
    new_get_db = '''def get_db():
    """Get database connection with row factory for dict-like access"""
    if USE_POSTGRES:
        debug_print("Opening PostgreSQL connection")
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        conn.autocommit = False
        return conn
    else:
        debug_print(f"Opening database connection to {DATABASE}")
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn'''
    
    new_content = new_content.replace(old_get_db, new_get_db)
    
    # Update init_db function for PostgreSQL
    # This is complex, so we'll add a note for manual update
    
    # Update app.run for production
    old_run = '''if __name__ == '__main__':
    debug_print("Starting 16chan V1...")
    init_db()
    debug_print("Server starting on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)'''
    
    new_run = '''if __name__ == '__main__':
    debug_print("Starting 16chan V1...")
    init_db()
    
    # Get port from environment (Render/Heroku use PORT env variable)
    port = int(os.environ.get('PORT', 5000))
    
    # Check if running in production
    is_production = os.environ.get('DATABASE_URL') is not None
    
    if is_production:
        debug_print(f"Server starting in PRODUCTION mode on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        debug_print(f"Server starting in DEVELOPMENT mode on http://127.0.0.1:{port}")
        app.run(debug=True, port=port)'''
    
    new_content = new_content.replace(old_run, new_run)
    
    # Write updated file
    with open('app_production.py', 'w') as f:
        f.write(new_content)
    
    print("✓ Created app_production.py with PostgreSQL support")
    print("  Note: You'll need to manually update init_db() function for PostgreSQL")
    print("  See RENDER_DEPLOYMENT.md for the updated init_db() code")

def add_postgres_support_to_worker():
    """Add PostgreSQL support to decay_worker.py"""
    print("\n[2/2] Updating decay_worker.py for PostgreSQL...")
    
    with open('decay_worker.py', 'r') as f:
        content = f.read()
    
    # Check if already updated
    if 'psycopg2' in content:
        print("✓ decay_worker.py already has PostgreSQL support")
        return
    
    # Backup first
    backup_file('decay_worker.py')
    
    # Add database configuration
    db_config = '''"""
16chan Decay Worker
Background process that calculates decay scores and soft-deletes posts/boards
Runs every 5 minutes
Production version with PostgreSQL support
"""

import time
from datetime import datetime
import os

# Database configuration - supports both SQLite (dev) and PostgreSQL (production)
if os.environ.get('DATABASE_URL'):
    # Production: Use PostgreSQL
    import psycopg2
    from psycopg2.extras import RealDictCursor
    DATABASE_URL = os.environ['DATABASE_URL']
    USE_POSTGRES = True
else:
    # Development: Use SQLite
    import sqlite3
    DATABASE = 'db.sqlite'
    USE_POSTGRES = False

DECAY_INTERVAL = 300  # 5 minutes in seconds
'''
    
    # Replace imports section
    lines = content.split('\n')
    
    # Find where imports end
    import_end = 0
    for i, line in enumerate(lines):
        if line.startswith('def '):
            import_end = i
            break
    
    # Reconstruct
    new_content = db_config + '\n' + '\n'.join(lines[import_end:])
    
    # Update get_db function
    old_get_db = '''def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn'''
    
    new_get_db = '''def get_db():
    """Get database connection"""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        conn.autocommit = False
        return conn
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn'''
    
    new_content = new_content.replace(old_get_db, new_get_db)
    
    # Write updated file
    with open('decay_worker_production.py', 'w') as f:
        f.write(new_content)
    
    print("✓ Created decay_worker_production.py with PostgreSQL support")

def create_init_script():
    """Create database initialization script for production"""
    print("\n[3/3] Creating database initialization script...")
    
    init_script = '''"""
Database Initialization Script for Production
Run this once after deploying to initialize the PostgreSQL database
"""

import os
import sys

# Import from your app
if os.environ.get('DATABASE_URL'):
    print("Initializing production database...")
    from app import init_db
    init_db()
    print("Database initialized successfully!")
else:
    print("ERROR: DATABASE_URL not set. Are you in production environment?")
    sys.exit(1)
'''
    
    with open('init_production_db.py', 'w') as f:
        f.write(init_script)
    
    print("✓ Created init_production_db.py")
    print("  Run this on Render after first deployment to set up database")

def main():
    print("=" * 60)
    print("  16chan Production Configuration Helper")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists('app.py'):
        print("\n❌ ERROR: app.py not found!")
        print("   Please run this script from the 16chan directory")
        return
    
    print("\nThis script will:")
    print("1. Add PostgreSQL support to app.py")
    print("2. Add PostgreSQL support to decay_worker.py")
    print("3. Create database initialization script")
    print("\nOriginal files will be backed up with .backup extension")
    
    response = input("\nContinue? (y/n): ")
    if response.lower() != 'y':
        print("Aborted.")
        return
    
    try:
        add_postgres_support_to_app()
        add_postgres_support_to_worker()
        create_init_script()
        
        print("\n" + "=" * 60)
        print("  ✓ Production configuration complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Review the generated *_production.py files")
        print("2. Test locally if you have PostgreSQL")
        print("3. Follow RENDER_DEPLOYMENT.md to deploy")
        print("\nFiles created:")
        print("  - app_production.py")
        print("  - decay_worker_production.py")
        print("  - init_production_db.py")
        print("\nBackups created:")
        print("  - app.py.backup")
        print("  - decay_worker.py.backup")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()