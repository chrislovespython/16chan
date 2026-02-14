# 16chan

A minimalist, grayscale imageboard/forum built with Flask and SQLite. The project includes a web app, background decay worker, SQLite persistence, simple templates, a test suite, and a quickstart guide. This README documents the architecture, setup, and operations.

## Features
- Boards and threads with replies
- SQLite-backed persistence (db.sqlite auto-created)
- Background “decay” worker for thread/board lifecycle maintenance
- Grayscale UI via a single stylesheet
- Simple Jinja2 templates (server-rendered)
- Test suite bootstrap
- One-command startup script

## Repository Structure
```
16chan/
├── app.py               # Main Flask application (1000+ lines target)
├── decay_worker.py      # Background decay process
├── test.py              # Test suite entry
├── start.sh             # Automated startup script
├── requirements.txt     # Python dependencies
├── README.md            # Full documentation (this file)
├��─ QUICKSTART.md        # Condensed quick start
├── db.sqlite            # SQLite database (auto-created at runtime)
├── templates/
│   ├── base.html        # Base template
│   ├── boards.html      # Board list
│   ├── board.html       # Single board view
│   ├── thread.html      # Thread view with replies
│   └── new_board.html   # Create board form
└── static/
    └── style.css        # Grayscale stylesheet
```

## Requirements
- Python 3.10+
- pip 22+
- (Optional) bash to run `start.sh` on non-Windows; on Windows use PowerShell/CMD equivalents

## Installation
1. Clone or copy this folder to your machine. Confirm path:
   - c:/Users/assko/16chan
2. Create and activate a virtual environment (recommended):
   - Windows PowerShell
     - `python -m venv .venv`
     - `.venv\Scripts\Activate.ps1`
   - macOS/Linux
     - `python3 -m venv .venv`
     - `source .venv/bin/activate`
3. Install dependencies:
   - `pip install -r requirements.txt`

Note: If `requirements.txt` is empty, populate it with at least:
- Flask
- Jinja2 (usually brought by Flask)
- waitress or gunicorn (for production serving; optional)
- pytest (for tests; optional)

Example minimal requirements.txt:
```
Flask>=3.0
waitress>=2.1 ; platform_system == "Windows"
pytest>=8.0
```

## Configuration
Environment variables can be defined in a local `.env` file (already present) or the host environment.
- FLASK_ENV: development | production (influence debug and reloader)
- SECRET_KEY: Flask secret key (session/CSRF if used)
- DATABASE_URL: Optional override; defaults to `sqlite:///db.sqlite`
- DECAY_INTERVAL_SECONDS: Background worker tick interval (e.g., 60)
- DECAY_POLICY: Strategy for pruning/archiving threads (e.g., `ttl`, `activity`)

## Database
- SQLite file `db.sqlite` is created automatically on first run.
- Migrations are not required for a basic schema; for complex changes consider Alembic.
- Backups: The DB is a single file; copy while the app is stopped for a consistent backup.

## Running the App
- Development (typical):
  - `python app.py`
- With the start script (if implemented):
  - `bash start.sh` (macOS/Linux)
  - On Windows: execute analogous steps from the script manually or adapt to `.ps1`.
- Production (example using waitress on Windows):
  - `waitress-serve --port=8000 app:app`

The web UI should be available at http://127.0.0.1:5000/ (or the port you configured).

## Background Decay Worker
- Implemented in `decay_worker.py`, typically started either:
  - As a separate process managed by the startup script, or
  - As a thread within `app.py` on app launch (depending on your design choice).
- Purpose: enforce lifecycle rules (e.g., archive or delete inactive threads, cap max threads per board, TTL-based pruning, etc.).
- Configure via environment variables listed above.

## Templates and Static Assets
- Jinja2 templates in `templates/` render server-side views. `base.html` defines the shell (HTML head, nav, footer) extended by page-specific templates.
- `static/style.css` enforces a grayscale, accessible theme. Keep it minimal and override via utility classes as needed.

## Suggested Routes (for implementation)
- GET `/` -> redirect to `/boards`
- GET `/boards` -> list all boards
- GET `/boards/new` -> render new board form
- POST `/boards` -> create a new board
- GET `/b/<board_id>` -> board page with threads
- POST `/b/<board_id>/threads` -> create a thread
- GET `/t/<thread_id>` -> thread detail with replies
- POST `/t/<thread_id>/reply` -> add reply
- Static served from `/static/`

## Security and Safety Notes
- Validate inputs and sanitize HTML where necessary to avoid XSS.
- Consider rate limiting for thread/reply creation.
- Use SECRET_KEY and, if using forms, CSRF protection (Flask-WTF) in production.
- If enabling file uploads (images), validate type/size and store outside the repo.

## Testing
- `pytest -q` or `python -m pytest -q` from repository root.
- `test.py` can bootstrap or integrate with pytest; keep it minimal and delegate to tests/ if you add more files.

## Development Workflow
- Create feature branches, write tests, and keep commits small.
- Run formatters/linters (e.g., black, isort, flake8) if you add them to requirements.
- Keep `app.py` cohesive but consider refactoring into a package once it grows (e.g., `app/` with blueprints, models, services).

## Deployment
- Production WSGI server recommended (gunicorn on Linux/macOS, waitress on Windows).
- Configure environment variables and use `DATABASE_URL` pointing to a writable location.
- Serve static files via a reverse proxy (nginx) in production.

## Troubleshooting
- Port already in use: change Flask port or stop the conflicting process.
- Database locked: ensure single-writer patterns or use WAL mode for SQLite.
- Unicode errors in Windows console: prefer running through a virtual environment and modern terminal.

## License
Insert your preferred license here (e.g., MIT). Add a LICENSE file at repo root.

## Acknowledgements
- Flask and Jinja2 teams and contributors.
- SQLite developers and maintainers.
