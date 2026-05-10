@echo off
pip install tkinterdnd2 --quiet --disable-pip-version-check 2>nul
python "%~dp0app.py"
pause
