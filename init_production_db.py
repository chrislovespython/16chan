"""
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
