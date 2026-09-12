@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" steam_picker.py --serve %*
) else (
  python steam_picker.py --serve %*
)
pause
