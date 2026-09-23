@echo off
REM Startet ValuePulse per Doppelklick unter Windows.
cd /d "%~dp0"
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

where python >nul 2>&1
if errorlevel 1 (
  echo.
  echo Python fehlt.
  echo Bitte installiere Python 3.11 oder neuer:
  echo https://www.python.org/downloads/
  echo Beim Installieren "Add python.exe to PATH" ankreuzen.
  echo Danach diese Datei erneut starten.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Einrichtung beim ersten Start ...
  python -m venv .venv
  if errorlevel 1 (
    echo Die Einrichtung ist fehlgeschlagen.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"

".venv\Scripts\python.exe" -c "import streamlit, pandas, requests, dotenv" >nul 2>&1
if errorlevel 1 (
  echo Bausteine werden installiert. Das kann ein bis zwei Minuten dauern ...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Die Installation ist fehlgeschlagen.
    pause
    exit /b 1
  )
)

if not exist ".env" if exist ".env.example" (
  copy /Y ".env.example" ".env" >nul
  echo Hinweis: .env wurde angelegt. Ohne API-Schluessel startet der Demo-Modus.
)

echo ValuePulse oeffnet sich im Browser. Dieses Fenster offen lassen.
".venv\Scripts\python.exe" -m streamlit run valuepulse/app.py --server.port 8501
pause
