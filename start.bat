@echo off
REM 16chan V1 Startup Script for Windows
REM Launches both the web server and decay worker

echo ==========================================
echo   16chan V1 - Anonymous Imageboard
echo ==========================================
echo.

REM Check if Python is installed
echo [1/3] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from python.org
    pause
    exit /b 1
)
echo Python OK

REM Check if requirements are installed
echo.
echo [2/3] Checking dependencies...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
) else (
    echo Dependencies OK
)

echo.
echo [3/3] Starting 16chan...
echo Server will be available at: http://127.0.0.1:5000
echo.

REM Start Flask in background using START command
echo Starting web server...
start "16chan Web Server" /MIN python app.py

REM Wait for server to start
timeout /t 2 /nobreak >nul

echo Starting decay worker...
start "16chan Decay Worker" /MIN python decay_worker.py

echo.
echo ==========================================
echo   16chan is now running!
echo ==========================================
echo.
echo Web Server:    http://127.0.0.1:5000
echo.
echo Two console windows have been opened:
echo   - 16chan Web Server
echo   - 16chan Decay Worker
echo.
echo To stop 16chan:
echo   - Close both console windows
echo   - Or press Ctrl+C in each window
echo.
echo This window can be closed safely.
echo.
pause