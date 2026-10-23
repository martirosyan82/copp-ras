@echo off
echo Starting Database Migration Process...
set FLASK_APP=run.py

echo.
echo Step 1: Checking if migrations folder exists...
if not exist "migrations" (
    echo "migrations" folder not found. Initializing Flask-Migrate...
    .\venv\Scripts\flask.exe --app run db init
    echo Creating initial schema from existing DB...
    .\venv\Scripts\flask.exe --app run db stamp head
)

echo.
echo Step 2: Generating migration script for new changes...
set /p MIGN="Enter a short description for this migration (e.g. 'added phone to user'): "
.\venv\Scripts\flask.exe --app run db migrate -m "%MIGN%"

echo.
echo Step 3: Applying changes to the database...
.\venv\Scripts\flask.exe --app run db upgrade

echo.
echo Database migration completed!
pause
