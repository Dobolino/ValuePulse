@echo off
REM Holt neue Dateien und aktualisiert die Python-Bausteine.
cd /d "%~dp0"
echo ValuePulse wird aktualisiert ...
echo Geholt wird die Hauptversion main.

where git >nul 2>&1
if errorlevel 1 (
  echo Git fehlt. Die Version von main kann so nicht geholt werden.
  pause
  exit /b 1
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo Dieser Ordner ist kein Git-Projekt. Die Version von main kann so nicht geholt werden.
  pause
  exit /b 1
)

git fetch origin main
if errorlevel 1 (
  echo Die Hauptversion main konnte nicht vom Server geholt werden.
  pause
  exit /b 1
)

git show-ref --verify --quiet refs/heads/main
if errorlevel 1 (
  git checkout -b main --track origin/main
) else (
  git checkout main
)
if errorlevel 1 (
  echo Wechsel auf main ist fehlgeschlagen. Bitte ValuePulse schliessen und es erneut versuchen.
  pause
  exit /b 1
)

git pull --ff-only origin main
if errorlevel 1 (
  echo main konnte nicht uebernommen werden.
  pause
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  echo Python fehlt. Die Aktualisierung ist fehlgeschlagen.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 (
    echo Die Aktualisierung ist fehlgeschlagen.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Die Aktualisierung ist fehlgeschlagen.
  pause
  exit /b 1
)

echo ValuePulse wurde erfolgreich aktualisiert!
pause
exit /b 0
