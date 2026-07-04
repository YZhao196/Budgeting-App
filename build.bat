@echo off
REM ---------------------------------------------------------------------------
REM  Rebuild the standalone Windows executable  ->  dist\Budget.exe
REM
REM  One-time setup (installs the build-only tools):
REM      python -m pip install -r requirements-build.txt
REM
REM  Then just run:  build.bat
REM ---------------------------------------------------------------------------
python -m PyInstaller --noconfirm --windowed --onefile --name Budget --icon app.ico main.py
echo.
echo Done. The app is at  dist\Budget.exe  (double-click to run; no Python needed).
