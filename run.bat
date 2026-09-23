@echo off
REM Startet ValuePulse im Hintergrund und oeffnet das dunkle Dashboard.
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

".venv\Scripts\python.exe" -c "import socket; socket.create_connection(('127.0.0.1',8501),1)" >nul 2>&1
if not errorlevel 1 (
  start "" http://localhost:8501
  echo ValuePulse laeuft bereits. Das Dashboard oeffnet sich im Darkmode.
  exit /b 0
)

start "ValuePulse" /MIN ".venv\Scripts\python.exe" -m streamlit run valuepulse/app.py --server.port 8501 --server.headless true --theme.base dark --browser.gatherUsageStats false
echo Warte auf den Start ...
timeout /t 4 /nobreak >nul
start "" http://localhost:8501
echo ValuePulse laeuft im Hintergrund. Das Dashboard oeffnet sich im Darkmode.
echo Zum Beenden das minimierte Fenster ValuePulse schliessen.
exit /b 0
