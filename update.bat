@echo off
REM Holt neue Dateien und aktualisiert die Python-Bausteine.
cd /d "%~dp0"
echo ValuePulse wird aktualisiert ...

where git >nul 2>&1
if not errorlevel 1 (
  git rev-parse --is-inside-work-tree >nul 2>&1
  if not errorlevel 1 (
    git fetch origin >nul 2>&1
    if errorlevel 1 (
      echo Hinweis: Der Abgleich mit dem Server war gerade nicht moeglich.
    ) else (
      git status -sb | find "behind" >nul
      if not errorlevel 1 (
        git pull --ff-only
        if errorlevel 1 echo Hinweis: Neue Dateien konnten nicht automatisch uebernommen werden.
      ) else (
        echo Keine neuen Dateien auf dem Server.
      )
    )
  )
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
