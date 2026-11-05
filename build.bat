@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Please install 64-bit Python 3.11 or newer and add it to PATH.
  exit /b 1
)
python -c "import sys; sys.exit(0 if sys.maxsize > 2**32 else 1)"
if errorlevel 1 (
  echo 64-bit Python is required.
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" python -m venv .venv
python -m pip --python .venv install -r requirements.txt
if errorlevel 1 exit /b 1
set "PY=.venv\Scripts\python.exe"
"%PY%" -m unittest discover -v
if errorlevel 1 exit /b 1
"%PY%" tools\prepare_icon.py
if errorlevel 1 exit /b 1
rem Prevent unrelated tools on PATH from contributing incompatible ICU DLLs.
set "PATH=%SystemRoot%\System32;%SystemRoot%;%CD%\.venv\Scripts"
"%PY%" -m PyInstaller --noconfirm --clean --windowed --noupx --onefile --name Lexivane --icon assets\app.ico --add-data "assets:assets" --distpath dist main.py
if errorlevel 1 exit /b 1
echo Ready: dist\Lexivane.exe
endlocal
