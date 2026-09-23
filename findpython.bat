@echo off
REM Sucht ein echtes Python. Die Windows-Store-Verknuepfung zaehlt nicht.
set "VP_PYTHON="

where py >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
    set "VP_PYTHON=%%P"
  )
  if defined VP_PYTHON (
    "%VP_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
    if not errorlevel 1 exit /b 0
    echo.
    echo Python wurde gefunden, ist aber zu alt: %VP_PYTHON%
    echo Bitte Python 3.11 oder neuer installieren.
    echo https://www.python.org/downloads/
    echo Beim Installieren "Add python.exe to PATH" ankreuzen.
    echo.
    set "VP_PYTHON="
    exit /b 1
  )
)

call :consider python
if not errorlevel 1 exit /b 0
call :consider python3
if not errorlevel 1 exit /b 0

set "VP_PF86=%ProgramFiles(x86)%"
for %%V in (313 312 311) do (
  call :consider "%LocalAppData%\Programs\Python\Python%%V\python.exe"
  if not errorlevel 1 exit /b 0
  call :consider "%ProgramFiles%\Python%%V\python.exe"
  if not errorlevel 1 exit /b 0
  call :consider "%VP_PF86%\Python%%V\python.exe"
  if not errorlevel 1 exit /b 0
)

echo.
echo Python fehlt oder Windows bietet nur die Store-Verknuepfung an.
echo Die Meldung "Python wurde nicht gefunden" kommt von dieser Verknuepfung, nicht von ValuePulse.
echo.
echo So behebst du das:
echo 1. Python 3.11 oder neuer installieren:
echo    https://www.python.org/downloads/
echo    Beim Installieren "Add python.exe to PATH" ankreuzen.
echo 2. Die Store-Verknuepfung ausschalten:
echo    Einstellungen ^> Apps ^> Erweiterte App-Einstellungen ^> App-Ausfuehrungsaliase
echo    python.exe und python3.exe auf Aus stellen.
echo 3. Dieses Fenster schliessen und run.bat erneut starten.
echo.
set "VP_PYTHON="
exit /b 1

:consider
set "CANDIDATE=%~1"
if "%CANDIDATE%"=="" exit /b 1
echo %CANDIDATE% | find /I "WindowsApps" >nul
if not errorlevel 1 exit /b 1
if exist "%CANDIDATE%" (
  "%CANDIDATE%" -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
  if errorlevel 1 exit /b 1
  set "VP_PYTHON=%CANDIDATE%"
  exit /b 0
)
where "%CANDIDATE%" >nul 2>&1
if errorlevel 1 exit /b 1
for /f "delims=" %%P in ('where "%CANDIDATE%"') do (
  echo %%P | find /I "WindowsApps" >nul
  if errorlevel 1 (
    "%%P" -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
    if not errorlevel 1 (
      set "VP_PYTHON=%%P"
      goto :considered
    )
  )
)
exit /b 1

:considered
exit /b 0
