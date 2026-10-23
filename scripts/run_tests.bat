@echo off
echo Running automated tests...
.\venv\Scripts\python.exe -m pytest tests -v
pause
