@echo off
REM Holt die Hauptversion main. Eine ZIP ohne Git wird direkt geladen.
REM Die Datei startet sich aus dem Temp-Ordner neu, damit das Entpacken
REM das laufende Skript nicht zerlegt.
if "%VP_FROM_TEMP%"=="1" goto :work

cd /d "%~dp0"
mkdir "%TEMP%\vp-update" 2>nul
copy /Y "%~f0" "%TEMP%\vp-update\update.bat" >nul
copy /Y "%~dp0findpython.bat" "%TEMP%\vp-update\findpython.bat" >nul
set "VP_FROM_TEMP=1"
call "%TEMP%\vp-update\update.bat" "%CD%"
set "VP_FROM_TEMP="
if errorlevel 1 exit /b 1
exit /b 0

:work
cd /d "%~1"
set "VP_ROOT=%~1"
echo ValuePulse wird aktualisiert ...
echo Geholt wird die Hauptversion main.

if not exist "%VP_ROOT%\.git" goto :zip
where git >nul 2>&1
if errorlevel 1 goto :zip

git fetch origin main
if errorlevel 1 goto :fetchfail
git show-ref --verify --quiet refs/heads/main
if errorlevel 1 goto :newmain
git checkout main
if errorlevel 1 goto :checkoutfail
goto :pull

:newmain
git checkout -b main --track origin/main
if errorlevel 1 goto :checkoutfail

:pull
git pull --ff-only origin main
if errorlevel 1 goto :pullfail
goto :deps

:zip
echo Kein Git-Ordner. Die Hauptversion main wird als ZIP geladen.
echo Eigene Schluessel und die Datenbank bleiben erhalten.
set "VP_ZIP=%TEMP%\valuepulse-main.zip"
set "VP_UNPACK=%TEMP%\valuepulse-main-unpack"
if exist "%VP_UNPACK%" rmdir /s /q "%VP_UNPACK%"
mkdir "%VP_UNPACK%"
if defined VALUEPULSE_MAIN_ZIP goto :zip_local
curl.exe -fsSL -o "%VP_ZIP%" https://github.com/Dobolino/ValuePulse/archive/refs/heads/main.zip
if errorlevel 1 goto :zipfail
goto :unzip

:zip_local
copy /Y "%VALUEPULSE_MAIN_ZIP%" "%VP_ZIP%" >nul
if errorlevel 1 goto :zipfail

:unzip
tar -xf "%VP_ZIP%" -C "%VP_UNPACK%"
if errorlevel 1 goto :zipfail
set "VP_SRC="
for /d %%D in ("%VP_UNPACK%\*") do set "VP_SRC=%%D"
if not defined VP_SRC goto :zipfail
if not exist "%VP_SRC%\run.bat" goto :zipfail
robocopy "%VP_SRC%" "%VP_ROOT%" /E /NFL /NDL /NJH /NJS /XD .git .venv __pycache__ .pytest_cache /XF .env valuepulse.sqlite3 *.sqlite3 *.sqlite3.bak .valuepulse.pid
if errorlevel 8 goto :zipfail
goto :deps

:fetchfail
echo Die Hauptversion main konnte nicht vom Server geholt werden.
goto :fail

:checkoutfail
echo Wechsel auf main ist fehlgeschlagen. Bitte ValuePulse schliessen und es erneut versuchen.
goto :fail

:pullfail
echo main konnte nicht uebernommen werden.
goto :fail

:zipfail
echo Die Hauptversion main konnte nicht heruntergeladen werden.
echo Bitte diese Datei im Browser laden, entpacken und run.bat starten:
echo https://github.com/Dobolino/ValuePulse/archive/refs/heads/main.zip
goto :fail

:fail
if "%VALUEPULSE_UPDATE_FILES_ONLY%"=="1" exit /b 1
pause
exit /b 1

:deps
if "%VALUEPULSE_UPDATE_FILES_ONLY%"=="1" goto :success
call "%VP_ROOT%\findpython.bat"
if errorlevel 1 goto :pythonfail

if exist "%VP_ROOT%\.venv" if not exist "%VP_ROOT%\.venv\Scripts\python.exe" rmdir /s /q "%VP_ROOT%\.venv"

if exist "%VP_ROOT%\.venv\Scripts\python.exe" goto :pip
"%VP_PYTHON%" -m venv "%VP_ROOT%\.venv"
if errorlevel 1 goto :pipfail

:pip

call "%VP_ROOT%\.venv\Scripts\activate.bat"
"%VP_ROOT%\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :pipfail
"%VP_ROOT%\.venv\Scripts\python.exe" -m pip install -r "%VP_ROOT%\requirements.txt"
if errorlevel 1 goto :pipfail

:success
echo ValuePulse wurde erfolgreich aktualisiert!
if "%VALUEPULSE_UPDATE_FILES_ONLY%"=="1" exit /b 0
pause
exit /b 0

:pythonfail
echo Die Dateien von main sind geholt. Python muss noch installiert werden, danach run.bat starten.
goto :fail

:pipfail
echo Die Aktualisierung ist fehlgeschlagen.
goto :fail
