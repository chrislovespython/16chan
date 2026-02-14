"""
16chan V3 Decay Worker with Heartbeat
"""

import sqlite3
import time
import requests
from datetime import datetime

DATABASE = 'db.sqlite'
DECAY_INTERVAL = 300  # 5 minutes
HEARTBEAT_URL = 'http://127.0.0.1:5000/api/worker-heartbeat'

def debug_print(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[DECAY {timestamp}] {msg}")

def get_db():
    try:
        conn = sqlite3.connect(DATABASE, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        debug_print(f"Database error: {e}")
        return None

def send_heartbeat():
    """Send heartbeat to main app"""
    try:
        requests.post(HEARTBEAT_URL, timeout=2)
        debug_print("Heartbeat sent")
    except:
        pass  # Silently fail if app not running

def calculate_decay():
    debug_print("Starting decay cycle...")
    
    conn = get_db()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        now = int(time.time())
        
        cursor.execute('''
            SELECT p.id, p.bury_score, p.created_at, p.parent_id, p.is_sticky,
                   COUNT(DISTINCT r.id) as reply_count
            FROM posts p
            LEFT JOIN posts r ON r.parent_id = p.id AND r.is_deleted = 0
            WHERE p.is_deleted = 0
            GROUP BY p.id
        ''')
        
        posts = cursor.fetchall()
        debug_print(f"Analyzing {len(posts)} posts")
        
        deleted = 0
        
        for post in posts:
            if post['is_sticky']:
                continue
            
            age_hours = max(0, (now - post['created_at']) / 3600.0)
            
            if age_hours > 720:  # 30 days
                cursor.execute('UPDATE posts SET is_deleted = 1 WHERE id = ?', (post['id'],))
                deleted += 1
                continue
            
            decay_score = (post['bury_score'] * 1.5) + (age_hours * 0.3) - (post['reply_count'] * 0.1)
            decay_score = max(0, decay_score)
            
            cursor.execute('UPDATE posts SET decay_score = ? WHERE id = ?', (decay_score, post['id']))
            
            if decay_score > 10.0:
                cursor.execute('UPDATE posts SET is_deleted = 1 WHERE id = ?', (post['id'],))
                deleted += 1
        
        conn.commit()
        debug_print(f"Deleted {deleted} posts")
        
        # Deactivate empty boards
        cursor.execute('''
            SELECT b.id, b.slug, COUNT(DISTINCT p.id) as threads
            FROM boards b
            LEFT JOIN posts p ON p.board_id = b.id AND p.parent_id IS NULL AND p.is_deleted = 0
            WHERE b.is_active = 1
            GROUP BY b.id
        ''')
        
        boards = cursor.fetchall()
        for board in boards:
            if board['threads'] == 0:
                cursor.execute('UPDATE boards SET is_active = 0 WHERE id = ?', (board['id'],))
                debug_print(f"Deactivated board /{board['slug']}/")
        
        conn.commit()
        
    except Exception as e:
        debug_print(f"Error: {e}")
    finally:
        if conn:
            conn.close()
    
    debug_print("Decay cycle complete")
    send_heartbeat()

def run():
    debug_print("=" * 60)
    debug_print("16chan V3 Decay Worker Started")
    debug_print("=" * 60)
    
    calculate_decay()
    
    while True:
        try:
            time.sleep(DECAY_INTERVAL)
            calculate_decay()
        except KeyboardInterrupt:
            debug_print("Worker stopped")
            break
        except Exception as e:
            debug_print(f"Fatal error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    run()