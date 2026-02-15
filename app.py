"""
16chan Anonymous imageboard
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import hashlib
import time
import uuid
from functools import wraps
import os
import requests
from datetime import datetime
import  random
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
import sqlite3

load_dotenv()
# Database configuration - PostgreSQL detection
DATABASE_URL = os.environ.get('DATABASE_URL', '')
IS_POSTGRES = bool(DATABASE_URL and 'postgres' in DATABASE_URL)

# SQL placeholder (%s for PostgreSQL, ? for SQLite)
placeholder = '%s' if IS_POSTGRES else '?'

print(f"[INFO] Using {'PostgreSQL (production)' if IS_POSTGRES else 'SQLite (development)'} database")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
DATABASE = 'db.sqlite'
placeholder = "%s" if IS_POSTGRES else "{placeholder}"
# ImageKit Configuration
IMAGEKIT_PRIVATE_KEY = os.environ.get('IMAGEKIT_PRIVATE_KEY', '')
IMAGEKIT_PUBLIC_KEY = os.environ.get('IMAGEKIT_PUBLIC_KEY', '')
IMAGEKIT_URL_ENDPOINT = os.environ.get('IMAGEKIT_URL_ENDPOINT', '')

# Security: Set this in Render Env Vars
DECAY_SECRET = os.environ.get("DECAY_SECRET")

def calculate_decay():
	# Cooldown check: Only run if it hasn't run in the last 10 minutes
	now = int(time.time())
	if backend_status.get('last_decay') and (now - backend_status['last_decay']) < 600:
		return

	debug_print("Starting optimized decay cycle...")
	conn = get_db()
	if not conn: return

	try:
		cursor = conn.cursor()
		thirty_days_ago = now - (30 * 24 * 60 * 60)

		# Use %s for psycopg (Postgres) or {placeholder} for sqlite3
		p = "%s" if IS_POSTGRES else "{placeholder}"

		# 1. DELETE OLD & CALCULATE SCORES (The Vectorized Way)
		# This one query does all your math for all posts at once
		cursor.execute(f'''
			UPDATE posts
			SET
				decay_score = MAX(0, (bury_score * 1.5) + ((( {p} - created_at) / 3600.0) * 0.3) - (reply_count * 0.1)),
				is_deleted = CASE
					WHEN created_at < {p} THEN 1
					WHEN ((bury_score * 1.5) + ((( {p} - created_at) / 3600.0) * 0.3) - (reply_count * 0.1)) > 10.0 THEN 1
					ELSE is_deleted
				END
			WHERE is_deleted = 0 AND is_sticky = 0
		''', (now, thirty_days_ago, now, now))

		# 2. DEACTIVATE EMPTY BOARDS
		cursor.execute(f'''
			UPDATE boards SET is_active = 0
			WHERE id IN (
				SELECT b.id FROM boards b
				LEFT JOIN posts p ON p.board_id = b.id AND p.parent_id IS NULL AND p.is_deleted = 0
				GROUP BY b.id HAVING COUNT(p.id) = 0
			)
		''')

		conn.commit()
		backend_status['last_decay'] = now
		debug_print("Decay cycle complete")
	except Exception as e:
		debug_print(f"Decay error: {e}")
	finally:
		conn.close()
# Backend Status
backend_status = {
	'database': '🟢',  # Green
	'imagekit': '🟡',  # Yellow (not configured)
	'decay_worker': '🟢',  # Red (not started)
	'last_decay': None,
	'uptime_start': int(time.time())
}

# Country code to name mapping for flagcdn.com
COUNTRY_CODES = {
	'US': 'us', 'GB': 'gb', 'CA': 'ca', 'AU': 'au', 'DE': 'de', 'FR': 'fr',
	'JP': 'jp', 'KR': 'kr', 'CN': 'cn', 'BR': 'br', 'MX': 'mx', 'ES': 'es',
	'IT': 'it', 'RU': 'ru', 'IN': 'in', 'NL': 'nl', 'SE': 'se', 'NO': 'no',
	'FI': 'fi', 'DK': 'dk', 'PL': 'pl', 'PT': 'pt', 'GR': 'gr', 'TR': 'tr',
	'AR': 'ar', 'CL': 'cl', 'ZA': 'za', 'EG': 'eg', 'NG': 'ng', 'KE': 'ke',
	'IE': 'ie', 'BE': 'be', 'CH': 'ch', 'AT': 'at', 'CZ': 'cz', 'HU': 'hu',
	'RO': 'ro', 'UA': 'ua', 'IL': 'il', 'SA': 'sa', 'AE': 'ae', 'SG': 'sg',
	'MY': 'my', 'TH': 'th', 'VN': 'vn', 'PH': 'ph', 'ID': 'id', 'NZ': 'nz',
	'XX': 'xx'  # Unknown/VPN
}

def get_country_from_ip(ip_address):
	"""Get country code from IP address using free IP API"""
	try:
		# Use ip-api.com (free, no key needed, 45 requests/minute)
		if ip_address == '127.0.0.1' or ip_address.startswith('192.168'):
			# Local IP, return random for testing
			return random.choice(list(COUNTRY_CODES.keys()))

		response = requests.get(f'http://ip-api.com/json/{ip_address}', timeout=2)
		if response.status_code == 200:
			data = response.json()
			country_code = data.get('countryCode', 'XX')
			debug_print(f"IP {ip_address} -> {country_code}")
			return country_code
	except Exception as e:
		debug_print(f"IP lookup failed: {e}")

	return 'XX'

def get_flag_url(country_code):
	"""Get flag image URL from flagcdn.com"""
	code = COUNTRY_CODES.get(country_code, 'xx').lower()
	if code == 'xx':
		# Return pirate flag for unknown
		return 'https://flagcdn.com/w40/xx.png'  # This won't exist, we'll use CSS fallback
	return f'https://flagcdn.com/w40/{code}.png'

def debug_print(msg):
	timestamp = datetime.now().strftime('%H:%M:%S')
	print(f"[{timestamp}] {msg}")

# ===== DATABASE =====

def get_db():
	"""Get database connection with PostgreSQL support"""
	try:
		if IS_POSTGRES:
			import psycopg
			conn = psycopg.connect(DATABASE_URL)
			conn.row_factory = psycopg.rows.dict_row
			backend_status['database'] = '🟢'
			return conn
		else:
			import sqlite3
			conn = sqlite3.connect(DATABASE, timeout=30.0)
			conn.row_factory = sqlite3.Row
			backend_status['database'] = '🟢'
			return conn
	except Exception as e:
		debug_print(f"Database connection error: {e}")
		backend_status['database'] = '🔴'
		return None

def init_db():
	debug_print("Initializing PostgreSQL V3 database")
	conn = get_db()
	if not conn:
		return

	with conn.cursor() as cursor:
		# Sessions
		cursor.execute(f'''
			CREATE TABLE IF NOT EXISTS sessions (
				id TEXT PRIMARY KEY,
				created_at BIGINT,
				country TEXT DEFAULT 'XX',
				post_count INTEGER DEFAULT 0,
				last_post_at BIGINT,
				is_banned INTEGER DEFAULT 0,
				reputation INTEGER DEFAULT 0
			)
		''')

		# Boards
		# Note: SERIAL handles the autoincrement in Postgres
		cursor.execute(f'''
			CREATE TABLE IF NOT EXISTS boards (
				id SERIAL PRIMARY KEY,
				slug TEXT UNIQUE,
				name TEXT,
				description TEXT,
				created_at BIGINT,
				creator_session_id TEXT,
				is_active INTEGER DEFAULT 1,
				post_count INTEGER DEFAULT 0,
				unique_posters INTEGER DEFAULT 0,
				activity_score REAL DEFAULT 0,
				election_active INTEGER DEFAULT 0,
				election_ends_at BIGINT
			)
		''')

		# Posts
		cursor.execute(f'''
			CREATE TABLE IF NOT EXISTS posts (
				id SERIAL PRIMARY KEY,
				board_id INTEGER,
				parent_id INTEGER DEFAULT NULL,
				session_id TEXT,
				content TEXT,
				image_url TEXT,
				image_thumbnail TEXT,
				created_at BIGINT,
				bury_score INTEGER DEFAULT 0,
				decay_score REAL DEFAULT 0,
				is_deleted INTEGER DEFAULT 0,
				is_sticky INTEGER DEFAULT 0,
				reply_count INTEGER DEFAULT 0
			)
		''')

		# Votes
		cursor.execute(f'''
			CREATE TABLE IF NOT EXISTS votes (
				id SERIAL PRIMARY KEY,
				post_id INTEGER,
				session_id TEXT,
				value INTEGER,
				UNIQUE(post_id, session_id)
			)
		''')

		# Moderators
		cursor.execute(f'''
			CREATE TABLE IF NOT EXISTS moderators (
				id SERIAL PRIMARY KEY,
				board_id INTEGER,
				session_id TEXT,
				role TEXT,
				appointed_at BIGINT,
				is_elected INTEGER DEFAULT 0,
				term_ends_at BIGINT
			)
		''')

		# Elections
		cursor.execute(f'''
			CREATE TABLE IF NOT EXISTS elections (
				id SERIAL PRIMARY KEY,
				board_id INTEGER,
				started_at BIGINT,
				ends_at BIGINT,
				is_active INTEGER DEFAULT 1,
				winner_session_id TEXT
			)
		''')

		# Election candidates
		cursor.execute(f'''
			CREATE TABLE IF NOT EXISTS election_candidates (
				id SERIAL PRIMARY KEY,
				election_id INTEGER,
				session_id TEXT,
				statement TEXT,
				votes INTEGER DEFAULT 0
			)
		''')

		# Stats
		cursor.execute(f'''
			CREATE TABLE IF NOT EXISTS stats (
				id SERIAL PRIMARY KEY,
				timestamp BIGINT,
				total_posts INTEGER,
				total_boards INTEGER,
				total_users INTEGER,
				posts_last_24h INTEGER,
				images_uploaded INTEGER
			)
		''')

		conn.commit()
	conn.close()
	debug_print("V3 Database initialized")

# ===== IMAGEKIT =====

def check_imagekit_status():
	"""Check if ImageKit is configured"""
	if IMAGEKIT_PRIVATE_KEY and IMAGEKIT_PUBLIC_KEY and IMAGEKIT_URL_ENDPOINT:
		backend_status['imagekit'] = '🟢'
		return True
	else:
		backend_status['imagekit'] = '🟡'
		return False

def get_imagekit_auth():
	"""Generate ImageKit authentication for client-side upload"""
	if not check_imagekit_status():
		return None

	try:
		import hmac
		import hashlib

		# Generate authentication parameters
		token = str(uuid.uuid4())
		expire = int(time.time()) + 2400  # 40 minutes from now

		# Create signature using HMAC-SHA1
		# Signature = HMAC(privateKey, token + expire)
		message = token + str(expire)
		signature = hmac.new(
			IMAGEKIT_PRIVATE_KEY.encode('utf-8'),
			message.encode('utf-8'),
			hashlib.sha1
		).hexdigest()

		debug_print(f"ImageKit auth generated: token={token[:8]}..., expire={expire}")

		return {
			'token': token,
			'expire': expire,
			'signature': signature,
			'publicKey': IMAGEKIT_PUBLIC_KEY,
			'urlEndpoint': IMAGEKIT_URL_ENDPOINT
		}
	except Exception as e:
		debug_print(f"ImageKit auth error: {e}")
		backend_status['imagekit'] = '🔴'
		return None

# ===== SESSION =====

def get_or_create_session():
	if 'session_id' not in session:
		session_id = str(uuid.uuid4())
		session['session_id'] = session_id

		# Get real country from IP
		ip_address = request.remote_addr
		country = get_country_from_ip(ip_address)

		conn = get_db()
		if conn:
			cursor = conn.cursor()
			try:
				cursor.execute(f'''
					INSERT INTO sessions (id, created_at, country, post_count, last_post_at, reputation)
					VALUES ({placeholder}, {placeholder}, {placeholder}, 0, 0, 0)
				''', (session_id, int(time.time()), country))
				conn.commit()
				debug_print(f"New session: {session_id[:8]} from {country} ({ip_address})")
			except:
				pass
			finally:
				conn.close()

	return session['session_id']

def get_session_info(session_id):
	"""Get session country and reputation"""
	conn = get_db()
	if not conn:
		return 'XX', 0

	cursor = conn.cursor()
	cursor.execute(f'SELECT country, reputation FROM sessions WHERE id = {placeholder}', (session_id,))
	row = cursor.fetchone()
	conn.close()

	if row:
		return row['country'], row['reputation']
	return 'XX', 0

def get_poster_id(session_id, board_id):
	hash_input = f"{session_id}{board_id}SALT_V3"
	return hashlib.sha256(hash_input.encode()).hexdigest()[:8]

# ===== ELECTIONS =====

def start_election(board_id):
	"""Start a moderator election for a board"""
	debug_print(f"Starting election for board {board_id}")
	conn = get_db()
	if not conn:
		return False

	cursor = conn.cursor()

	now = int(time.time())
	ends_at = now + (7 * 24 * 3600)  # 7 days

	try:
		# Create election
		cursor.execute(f'''
			INSERT INTO elections (board_id, started_at, ends_at, is_active)
			VALUES ({placeholder}, {placeholder}, {placeholder}, 1)
		''', (board_id, now, ends_at))

		election_id = cursor.fetchone()['id']

		# Update board
		cursor.execute(f'''
			UPDATE boards SET election_active = 1, election_ends_at = {placeholder}
			WHERE id = {placeholder}
		''', (ends_at, board_id))

		conn.commit()
		debug_print(f"Election {election_id} created for board {board_id}")
		return True
	except Exception as e:
		debug_print(f"Election start error: {e}")
		conn.rollback()
		return False
	finally:
		conn.close()

def nominate_for_election(election_id, session_id, statement):
	"""Nominate self for moderator election"""
	conn = get_db()
	if not conn:
		return False

	cursor = conn.cursor()

	try:
		# Check if already nominated
		cursor.execute(f'''
			SELECT id FROM election_candidates
			WHERE election_id = {placeholder} AND session_id = {placeholder}
		''', (election_id, session_id))

		if cursor.fetchone():
			conn.close()
			return False

		# Add candidate
		cursor.execute(f'''
			INSERT INTO election_candidates (election_id, session_id, statement, votes)
			VALUES ({placeholder}, {placeholder}, {placeholder}, 0)
		''', (election_id, session_id, statement))

		conn.commit()
		debug_print(f"New candidate for election {election_id}")
		return True
	except Exception as e:
		debug_print(f"Nomination error: {e}")
		conn.rollback()
		return False
	finally:
		conn.close()

def vote_in_election(candidate_id, voter_session_id):
	"""Vote for a candidate"""
	conn = get_db()
	if not conn:
		return False

	cursor = conn.cursor()

	try:
		# Get election_id
		cursor.execute(f'''
			SELECT election_id FROM election_candidates WHERE id = {placeholder}
		''', (candidate_id,))
		row = cursor.fetchone()
		if not row:
			conn.close()
			return False

		election_id = row['election_id']

		# Check if already voted (use votes table)
		cursor.execute(f'''
			SELECT id FROM votes
			WHERE post_id = {placeholder} AND session_id = {placeholder}
		''', (-election_id, voter_session_id))  # Negative ID for elections

		if cursor.fetchone():
			conn.close()
			return False

		# Record vote
		cursor.execute(f'''
			INSERT INTO votes (post_id, session_id, value)
			VALUES ({placeholder}, {placeholder}, 1)
		''', (-election_id, voter_session_id))

		# Increment vote count
		cursor.execute(f'''
			UPDATE election_candidates SET votes = votes + 1 WHERE id = {placeholder}
		''', (candidate_id,))

		conn.commit()
		debug_print(f"Vote cast for candidate {candidate_id}")
		return True
	except Exception as e:
		debug_print(f"Voting error: {e}")
		conn.rollback()
		return False
	finally:
		conn.close()

def end_election(election_id):
	"""End election and appoint winner"""
	debug_print(f"Ending election {election_id}")
	conn = get_db()
	if not conn:
		return

	cursor = conn.cursor()

	try:
		# Get winner
		cursor.execute(f'''
			SELECT ec.session_id, ec.votes, e.board_id
			FROM election_candidates ec
			JOIN elections e ON e.id = ec.election_id
			WHERE ec.election_id = {placeholder}
			ORDER BY ec.votes DESC
			LIMIT 1
		''', (election_id,))

		winner = cursor.fetchone()

		if winner and winner['votes'] > 0:
			# Record winner
			cursor.execute(f'''
				UPDATE elections SET winner_session_id = {placeholder}, is_active = 0
				WHERE id = {placeholder}
			''', (winner['session_id'], election_id))

			# Appoint as moderator
			term_ends = int(time.time()) + (30 * 24 * 3600)  # 30 days
			cursor.execute(f'''
				INSERT INTO moderators (board_id, session_id, role, appointed_at, is_elected, term_ends_at)
				VALUES ({placeholder}, {placeholder}, 'elected', {placeholder}, 1, {placeholder})
			''', (winner['board_id'], winner['session_id'], int(time.time()), term_ends))

			# Update board
			cursor.execute(f'''
				UPDATE boards SET election_active = 0, election_ends_at = NULL
				WHERE id = {placeholder}
			''', (winner['board_id'],))

			debug_print(f"Election won by {winner['session_id'][:8]} with {winner['votes']} votes")

		conn.commit()
	except Exception as e:
		debug_print(f"End election error: {e}")
		conn.rollback()
	finally:
		conn.close()

# ===== STATS =====

def calculate_trending():
	conn = get_db()
	if not conn:
		return

	cursor = conn.cursor()
	now = int(time.time())
	day_ago = now - 86400

	cursor.execute(f'''
		SELECT b.id,
			COUNT(DISTINCT CASE WHEN p.created_at > %s THEN p.id END) as posts_24h,
			COUNT(DISTINCT CASE WHEN p.created_at > %s THEN p.session_id END) as unique_posters
		FROM boards b
		LEFT JOIN posts p ON p.board_id = b.id AND p.is_deleted = 0
		WHERE b.is_active = 1
		GROUP BY b.id
	''', (day_ago, day_ago))

	boards = cursor.fetchall()

	for board in boards:
		activity_score = (board['posts_24h'] * 2) + (board['unique_posters'] * 5)
		cursor.execute(f'''
			UPDATE boards
			SET activity_score = {placeholder}, post_count = {placeholder}, unique_posters = {placeholder}
			WHERE id = {placeholder}
		''', (activity_score, board['posts_24h'], board['unique_posters'], board['id']))

	conn.commit()
	conn.close()

def get_global_stats():
	conn = get_db()
	if not conn:
		return {}

	cursor = conn.cursor()
	now = int(time.time())
	day_ago = now - 86400

	cursor.execute(f'SELECT COUNT(*) as count FROM posts WHERE is_deleted = 0')
	total_posts = cursor.fetchone()['count']

	cursor.execute(f'SELECT COUNT(*) as count FROM boards WHERE is_active = 1')
	total_boards = cursor.fetchone()['count']

	cursor.execute(f'''
	SELECT COUNT(DISTINCT session_id) as count
	FROM posts WHERE created_at > {placeholder}
''', (day_ago,))
	active_users = cursor.fetchone()['count']

	cursor.execute(f'''
		SELECT COUNT(*) as count FROM posts
		WHERE created_at > {placeholder} AND is_deleted = 0
	''', (day_ago,))
	posts_24h = cursor.fetchone()['count']

	cursor.execute(f'''
		SELECT COUNT(*) as count FROM posts
		WHERE image_url IS NOT NULL AND is_deleted = 0
	''')
	images = cursor.fetchone()['count']

	conn.close()

	uptime = int(time.time()) - backend_status['uptime_start']

	return {
		'total_posts': total_posts,
		'total_boards': total_boards,
		'active_users': active_users,
		'posts_24h': posts_24h,
		'images': images,
		'uptime': uptime
	}

# ===== TEXT PROCESSING =====

def process_post_content(content):
	lines = content.split('\n')
	processed = []

	for line in lines:
		line = line.strip()
		if not line:
			processed.append('<br>')
			continue

		if line.startswith('>'):
			processed.append(f'<span class="greentext">{line}</span><br>')
		elif line.startswith('>>'):
			processed.append(f'<a href="#post-{line[2:]}" class="quotelink">{line}</a><br>')
		else:
			processed.append(f'{line}<br>')

	return ''.join(processed)

# ===== TEMPLATE FILTERS =====

@app.template_filter('format_time')
def format_time(timestamp):
	if not timestamp:
		return "Unknown"

	now = int(time.time())
	diff = now - timestamp

	if diff < 60:
		return "just now"
	elif diff < 3600:
		return f"{diff//60}m ago"
	elif diff < 86400:
		return f"{diff//3600}h ago"
	elif diff < 604800:
		return f"{diff//86400}d ago"
	else:
		dt = datetime.fromtimestamp(timestamp)
		return dt.strftime('%m/%d/%y')

@app.template_filter('format_uptime')
def format_uptime(seconds):
	days = seconds // 86400
	hours = (seconds % 86400) // 3600
	mins = (seconds % 3600) // 60

	if days > 0:
		return f"{days}d {hours}h"
	elif hours > 0:
		return f"{hours}h {mins}m"
	else:
		return f"{mins}m"

@app.template_filter('country_flag')
def country_flag_filter(country_code):
	"""Get flag URL from flagcdn.com"""
	return get_flag_url(country_code)

@app.template_filter('process_content')
def process_content_filter(content):
	return process_post_content(content)

# ===== RATE LIMITING =====

def check_rate_limit(session_id, action_type):
	conn = get_db()
	if not conn:
		return False, 0

	cursor = conn.cursor()
	cursor.execute(f'SELECT created_at, last_post_at, is_banned FROM sessions WHERE id = {placeholder}', (session_id,))
	row = cursor.fetchone()
	conn.close()

	if not row or row['is_banned']:
		return False, 999999

	now = int(time.time())
	session_age = now - row['created_at']
	last_post = row['last_post_at']

	limits = {
		'board': (7 * 24 * 3600'account age'),
		'thread': (120, 'cooldown'),
		'reply': (60, 'cooldown')
	}

	if action_type in limits:
		limit, check_type = limits[action_type]

		if check_type == 'account age':
			if session_age < limit:
				return False, limit - session_age
		elif check_type == 'cooldown':
			if last_post and (now - last_post) < limit:
				return False, limit - (now - last_post)

	return True, 0

def update_post_timestamp(session_id):
	conn = get_db()
	if conn:
		cursor = conn.cursor()
		cursor.execute(f'''
			UPDATE sessions
			SET last_post_at = {placeholder}, post_count = post_count + 1
			WHERE id = {placeholder}
		''', (int(time.time()), session_id))
		conn.commit()
		conn.close()

# ===== ROUTES =====

@app.route('/')
def index():
	session_id = get_or_create_session()
	calculate_trending()

	conn = get_db()
	if not conn:
		return render_template('error.html', error="Database unavailable")

	cursor = conn.cursor()
	cursor.execute(f'''
		SELECT b.*,
			   COUNT(DISTINCT p.id) as thread_count
		FROM boards b
		LEFT JOIN posts p ON p.board_id = b.id AND p.parent_id IS NULL AND p.is_deleted = 0
		WHERE b.is_active = 1
		GROUP BY b.id
		ORDER BY b.activity_score DESC, b.created_at DESC
		LIMIT 50
	''')
	boards = cursor.fetchall()
	conn.close()

	stats = get_global_stats()

	return render_template('index.html', boards=boards, stats=stats, backend_status=backend_status)

@app.route('/status')
def status():
	"""Backend status page"""
	stats = get_global_stats()
	return render_template('status.html', backend_status=backend_status, stats=stats)

@app.route('/board/new', methods=['GET', 'POST'])
def new_board():
	session_id = get_or_create_session()
	stats = get_global_stats()

	if request.method == 'POST':
		slug = request.form.get('slug', '').strip().lower()
		name = request.form.get('name', '').strip()
		description = request.form.get('description', '').strip()

		if not slug or not name:
			return render_template('new_board.html', error="Slug and name required",
								 stats=stats, backend_status=backend_status)

		if not slug.isalnum() or len(slug) > 10:
			return render_template('new_board.html', error="Invalid slug",
								 stats=stats, backend_status=backend_status)

		can_create, cooldown = check_rate_limit(session_id, 'board')
		if not can_create:
			days = cooldown / (24 * 3600)
			return render_template('new_board.html',
								 error=f"Wait {days:.1f} more days",
								 stats=stats, backend_status=backend_status)

		conn = get_db()
		if not conn:
			return render_template('new_board.html', error="Database error",
								 stats=stats, backend_status=backend_status)

		cursor = conn.cursor()

		try:
			cursor.execute(f'''
	INSERT INTO boards (slug, name, description, created_at, creator_session_id)
	VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
	RETURNING id
''', (slug, name, description, int(time.time()), session_id))

			board_id = cursor.fetchone()['id']

			cursor.execute(f'''
	INSERT INTO moderators (board_id, session_id, role, appointed_at, is_elected, term_ends_at)
	VALUES ({placeholder}, {placeholder}, 'creator', {placeholder}, 0, NULL)
''', (board_id, session_id, int(time.time())))

			conn.commit()
			conn.close()

			return redirect(url_for('view_board', slug=slug))
		except sqlite3.IntegrityError:
			conn.close()
			return render_template('new_board.html', error="Board exists",
								 stats=stats, backend_status=backend_status)

	return render_template('new_board.html', stats=stats, backend_status=backend_status)

@app.route('/<slug>/')
def view_board(slug):
	session_id = get_or_create_session()

	calculate_decay()

	conn = get_db()
	if not conn:
		return "Database error", 500

	cursor = conn.cursor()

	cursor.execute(f'SELECT * FROM boards WHERE slug = {placeholder} AND is_active = 1', (slug,))
	board = cursor.fetchone()

	if not board:
		conn.close()
		return "Board not found", 404

	# Check if mod
	cursor.execute(f'''
		SELECT role FROM moderators WHERE board_id = {placeholder} AND session_id = {placeholder}
	''', (board['id'], session_id))
	is_mod = cursor.fetchone() is not None

	# Get active election
	election = None
	if board['election_active']:
		cursor.execute(f'''
			SELECT e.*,
				   (SELECT COUNT(*) FROM election_candidates WHERE election_id = e.id) as candidate_count
			FROM elections e
			WHERE e.board_id = {placeholder} AND e.is_active = 1
			ORDER BY e.id DESC
			LIMIT 1
		''', (board['id'],))
		election = cursor.fetchone()

	# Get threads
	cursor.execute(f'''
		SELECT p.*,
			   COUNT(DISTINCT r.id) as reply_count,
			   MAX(r.created_at) as last_reply
		FROM posts p
		LEFT JOIN posts r ON r.parent_id = p.id AND r.is_deleted = 0
		WHERE p.board_id = {placeholder} AND p.parent_id IS NULL AND p.is_deleted = 0
		GROUP BY p.id
		ORDER BY p.is_sticky DESC, p.created_at DESC
		LIMIT 100
	''', (board['id'],))
	threads = cursor.fetchall()

	conn.close()

	threads_with_info = []
	for thread in threads:
		thread_dict = dict(thread)
		thread_dict['poster_id'] = get_poster_id(thread['session_id'], board['id'])
		country, rep = get_session_info(thread['session_id'])
		thread_dict['country'] = country
		thread_dict['reputation'] = rep
		thread_dict['is_op'] = thread['session_id'] == session_id
		threads_with_info.append(thread_dict)

	stats = get_global_stats()
	imagekit_auth = get_imagekit_auth()

	return render_template('board.html',
						 board=board,
						 threads=threads_with_info,
						 is_mod=is_mod,
						 election=election,
						 stats=stats,
						 backend_status=backend_status,
						 imagekit_auth=imagekit_auth)

@app.route('/<slug>/thread/<int:thread_id>')
def view_thread(slug, thread_id):
	session_id = get_or_create_session()

	conn = get_db()
	if not conn:
		return "Database error", 500

	cursor = conn.cursor()

	cursor.execute(f'SELECT * FROM boards WHERE slug = {placeholder}', (slug,))
	board = cursor.fetchone()

	if not board:
		conn.close()
		return "Board not found", 404

	cursor.execute(f'''
		SELECT role FROM moderators WHERE board_id = {placeholder} AND session_id = {placeholder}
	''', (board['id'], session_id))
	is_mod = cursor.fetchone() is not None

	cursor.execute(f'''
		SELECT * FROM posts
		WHERE id = {placeholder} AND board_id = {placeholder} AND parent_id IS NULL AND is_deleted = 0
	''', (thread_id, board['id']))
	thread = cursor.fetchone()

	if not thread:
		conn.close()
		return "Thread not found", 404

	cursor.execute(f'''
		SELECT * FROM posts
		WHERE parent_id = {placeholder} AND is_deleted = 0
		ORDER BY created_at ASC
	''', (thread_id,))
	replies = cursor.fetchall()

	conn.close()

	thread_dict = dict(thread)
	thread_dict['poster_id'] = get_poster_id(thread['session_id'], board['id'])
	country, rep = get_session_info(thread['session_id'])
	thread_dict['country'] = country
	thread_dict['reputation'] = rep
	thread_dict['is_op'] = thread['session_id'] == session_id

	replies_with_info = []
	for reply in replies:
		reply_dict = dict(reply)
		reply_dict['poster_id'] = get_poster_id(reply['session_id'], board['id'])
		country, rep = get_session_info(reply['session_id'])
		reply_dict['country'] = country
		reply_dict['reputation'] = rep
		reply_dict['is_op'] = reply['session_id'] == session_id
		replies_with_info.append(reply_dict)

	stats = get_global_stats()
	imagekit_auth = get_imagekit_auth()

	return render_template('thread.html',
						 board=board,
						 thread=thread_dict,
						 replies=replies_with_info,
						 is_mod=is_mod,
						 stats=stats,
						 backend_status=backend_status,
						 imagekit_auth=imagekit_auth)

@app.route('/<slug>/post', methods=['POST'])
def new_thread(slug):
	session_id = get_or_create_session()

	content = request.form.get('content', '').strip()
	image_url = request.form.get('image_url', '').strip()
	image_thumbnail = request.form.get('image_thumbnail', '').strip()

	if not content or len(content) > 10000:
		return redirect(url_for('view_board', slug=slug))

	can_post, cooldown = check_rate_limit(session_id, 'thread')
	if not can_post:
		return redirect(url_for('view_board', slug=slug))

	conn = get_db()
	if not conn:
		return "Database error", 500

	cursor = conn.cursor()

	cursor.execute(f'SELECT id FROM boards WHERE slug = {placeholder} AND is_active = 1', (slug,))
	board = cursor.fetchone()

	if not board:
		conn.close()
		return "Board not found", 404

	cursor.execute(f'''
	INSERT INTO posts (board_id, parent_id, session_id, content, image_url, image_thumbnail, created_at)
	VALUES ({placeholder}, NULL, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
	RETURNING id
''', (board['id'], session_id, content, image_url or None, image_thumbnail or None, int(time.time())))

	thread_id = cursor.fetchone()['id']
	conn.commit()
	conn.close()

	update_post_timestamp(session_id)

	return redirect(url_for('view_thread', slug=slug, thread_id=thread_id))

@app.route('/<slug>/thread/<int:thread_id>/reply', methods=['POST'])
def reply_to_thread(slug, thread_id):
	session_id = get_or_create_session()

	content = request.form.get('content', '').strip()
	image_url = request.form.get('image_url', '').strip()
	image_thumbnail = request.form.get('image_thumbnail', '').strip()

	if not content or len(content) > 10000:
		return redirect(url_for('view_thread', slug=slug, thread_id=thread_id))

	can_post, cooldown = check_rate_limit(session_id, 'reply')
	if not can_post:
		return redirect(url_for('view_thread', slug=slug, thread_id=thread_id))

	conn = get_db()
	if not conn:
		return "Database error", 500

	cursor = conn.cursor()

	cursor.execute(f'SELECT id FROM boards WHERE slug = {placeholder}', (slug,))
	board = cursor.fetchone()

	if not board:
		conn.close()
		return "Board not found", 404

	cursor.execute(f'''
	INSERT INTO posts (board_id, parent_id, session_id, content, image_url, image_thumbnail, created_at)
	VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
''', (board['id'], thread_id, session_id, content, image_url or None, image_thumbnail or None, int(time.time())))

	cursor.execute(f'''
	UPDATE posts SET reply_count = reply_count + 1 WHERE id = {placeholder}
''', (thread_id,))

	conn.commit()
	conn.close()

	update_post_timestamp(session_id)

	return redirect(url_for('view_thread', slug=slug, thread_id=thread_id))

@app.route('/api/bury/<int:post_id>', methods=['POST'])
def bury_post(post_id):
	session_id = get_or_create_session()

	conn = get_db()
	if not conn:
		return jsonify({'success': False, 'error': 'Database error'})

	cursor = conn.cursor()

	cursor.execute(f'''
		SELECT * FROM votes WHERE post_id = {placeholder} AND session_id = {placeholder}
	''', (post_id, session_id))

	if cursor.fetchone():
		conn.close()
		return jsonify({'success': False, 'error': 'Already buried'})

	cursor.execute(f'''
		INSERT INTO votes (post_id, session_id, value)
		VALUES ({placeholder}, {placeholder}, 1)
	''', (post_id, session_id))

	cursor.execute(f'''
		UPDATE posts SET bury_score = bury_score + 1 WHERE id = {placeholder}
	''', (post_id,))

	cursor.execute(f'SELECT bury_score FROM posts WHERE id = {placeholder}', (post_id,))
	new_score = cursor.fetchone()['bury_score']

	conn.commit()
	conn.close()

	return jsonify({'success': True, 'bury_score': new_score})

@app.route('/mod/<slug>/delete/<int:post_id>', methods=['POST'])
def mod_delete(slug, post_id):
	session_id = get_or_create_session()

	conn = get_db()
	if not conn:
		return "Database error", 500

	cursor = conn.cursor()

	cursor.execute(f'SELECT id FROM boards WHERE slug = {placeholder}', (slug,))
	board = cursor.fetchone()

	if not board:
		conn.close()
		return "Board not found", 404

	cursor.execute(f'''
		SELECT role FROM moderators WHERE board_id = {placeholder} AND session_id = {placeholder}
	''', (board['id'], session_id))

	if not cursor.fetchone():
		conn.close()
		return "Unauthorized", 403

	cursor.execute(f'''
		UPDATE posts SET is_deleted = 1 WHERE id = {placeholder} AND board_id = {placeholder}
	''', (post_id, board['id']))

	conn.commit()
	conn.close()

	return redirect(url_for('view_board', slug=slug))

# ===== ELECTION ROUTES =====

@app.route('/<slug>/election')
def view_election(slug):
	session_id = get_or_create_session()

	conn = get_db()
	if not conn:
		return "Database error", 500

	cursor = conn.cursor()

	cursor.execute(f'SELECT * FROM boards WHERE slug = {placeholder}', (slug,))
	board = cursor.fetchone()

	if not board or not board['election_active']:
		conn.close()
		return redirect(url_for('view_board', slug=slug))

	cursor.execute(f'''
		SELECT * FROM elections
		WHERE board_id = {placeholder} AND is_active = 1
		ORDER BY id DESC LIMIT 1
	''', (board['id'],))
	election = cursor.fetchone()

	if not election:
		conn.close()
		return redirect(url_for('view_board', slug=slug))

	cursor.execute(f'''
		SELECT * FROM election_candidates
		WHERE election_id = {placeholder}
		ORDER BY votes DESC
	''', (election['id'],))
	candidates = cursor.fetchall()

	# Check if user has voted
	cursor.execute(f'''
		SELECT id FROM votes
		WHERE post_id = {placeholder} AND session_id = {placeholder}
	''', (-election['id'], session_id))
	has_voted = cursor.fetchone() is not None

	# Check if user is candidate
	cursor.execute(f'''
		SELECT id FROM election_candidates
		WHERE election_id = {placeholder} AND session_id = {placeholder}
	''', (election['id'], session_id))
	is_candidate = cursor.fetchone() is not None

	conn.close()

	candidates_with_info = []
	for candidate in candidates:
		cand_dict = dict(candidate)
		cand_dict['poster_id'] = get_poster_id(candidate['session_id'], board['id'])
		country, rep = get_session_info(candidate['session_id'])
		cand_dict['country'] = country
		cand_dict['reputation'] = rep
		candidates_widsssth_info.append(cand_dict)

	stats = get_global_stats()

	return render_template('election.html',
						 board=board,
						 election=election,
						 candidates=candidates_with_info,
						 has_voted=has_voted,
						 is_candidate=is_candidate,
						 stats=stats,
						 backend_status=backend_status)

@app.route('/<slug>/election/nominate', methods=['POST'])
def nominate_election(slug):
	session_id = get_or_create_session()

	statement = request.form.get('statement', '').strip()

	if not statement or len(statement) > 500:
		return redirect(url_for('view_election', slug=slug))

	conn = get_db()
	if not conn:
		return "Database error", 500

	cursor = conn.cursor()

	cursor.execute(f'SELECT id FROM boards WHERE slug = {placeholder} AND election_active = 1', (slug,))
	board = cursor.fetchone()

	if not board:
		conn.close()
		return redirect(url_for('view_board', slug=slug))

	cursor.execute(f'''
		SELECT id FROM elections
		WHERE board_id = {placeholder} AND is_active = 1
		ORDER BY id DESC LIMIT 1
	''', (board['id'],))
	election = cursor.fetchone()

	if not election:
		conn.close()
		return redirect(url_for('view_board', slug=slug))

	conn.close()

	if nominate_for_election(election['id'], session_id, statement):
		return redirect(url_for('view_election', slug=slug))
	else:
		return redirect(url_for('view_election', slug=slug))

@app.route('/api/election/vote/<int:candidate_id>', methods=['POST'])
def vote_election(candidate_id):
	session_id = get_or_create_session()

	if vote_in_election(candidate_id, session_id):
		return jsonify({'success': True})
	else:
		return jsonify({'success': False, 'error': 'Cannot vote'})

@app.route('/mod/<slug>/start-election', methods=['POST'])
def start_board_election(slug):
	session_id = get_or_create_session()

	conn = get_db()
	if not conn:
		return "Database error", 500

	cursor = conn.cursor()

	cursor.execute(f'SELECT id, election_active FROM boards WHERE slug = {placeholder}', (slug,))
	board = cursor.fetchone()

	if not board:
		conn.close()
		return "Board not found", 404

	if board['election_active']:
		conn.close()
		return redirect(url_for('view_board', slug=slug))

	cursor.execute(f'''
		SELECT role FROM moderators WHERE board_id = {placeholder} AND session_id = {placeholder}
	''', (board['id'], session_id))

	if not cursor.fetchone():
		conn.close()
		return "Unauthorized", 403

	conn.close()

	if start_election(board['id']):
		return redirect(url_for('view_election', slug=slug))
	else:
		return redirect(url_for('view_board', slug=slug))

# ===== WORKER HEALTH CHECK =====

@app.route('/api/worker-heartbeat', methods=['POST'])
def worker_heartbeat():
	"""Endpoint for decay worker to report status"""
	backend_status['decay_worker'] = '🟢'
	backend_status['last_decay'] = int(time.time())
	return jsonify({'success': True})

# ===== INITIALIZATION =====
debug_print("Starting 16chan initialization...")
init_db()
check_imagekit_status()
if __name__ == '__main__':
	debug_print("Server starting on http://127.0.0.1:5000")
	app.run(debug=True, port=5000)
