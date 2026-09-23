@echo off
REM Sucht ein echtes Python 3.11 oder neuer. Die Store-Verknuepfung zaehlt nicht.
REM Prozent-Variablen nicht in demselben Klammerblock setzen und lesen:
REM sonst ist der Pfad leer und ein neues Python wirkt faelschlich zu alt.
set "VP_PYTHON="
set "VP_OLD_PYTHON="

where py >nul 2>&1
if errorlevel 1 goto :nopy
call :try_py 3.14
if not errorlevel 1 goto :found
call :try_py 3.13
if not errorlevel 1 goto :found
call :try_py 3.12
if not errorlevel 1 goto :found
call :try_py 3.11
if not errorlevel 1 goto :found
call :try_py 3
if not errorlevel 1 goto :found

:nopy
call :consider python
if not errorlevel 1 goto :found
call :consider python3
if not errorlevel 1 goto :found

set "VP_PF86=%ProgramFiles(x86)%"
for %%V in (314 313 312 311) do (
  call :consider_version %%V
  if not errorlevel 1 goto :found
)

echo.
if defined VP_OLD_PYTHON (
  echo Python wurde gefunden, ist aber zu alt:
  echo %VP_OLD_PYTHON%
) else (
  echo Python fehlt oder Windows bietet nur die Store-Verknuepfung an.
  echo Die Meldung "Python wurde nicht gefunden" kommt von dieser Verknuepfung, nicht von ValuePulse.
)
echo.
echo So behebst du das:
echo 1. Python 3.11 oder neuer installieren. Python 3.13 ist passend.
echo    https://www.python.org/downloads/
echo    Beim Installieren "Add python.exe to PATH" ankreuzen.
echo 2. Die Store-Verknuepfung ausschalten:
echo    Einstellungen ^> Apps ^> Erweiterte App-Einstellungen ^> App-Ausfuehrungsaliase
echo    python.exe und python3.exe auf Aus stellen.
echo 3. Dieses Fenster schliessen und run.bat erneut starten.
echo.
set "VP_PYTHON="
exit /b 1

:found
exit /b 0

:try_py
set "VP_PYTHON="
for /f "delims=" %%P in ('py -%1 -c "import sys; print(sys.executable)" 2^>nul') do set "VP_PYTHON=%%P"
if not defined VP_PYTHON exit /b 1
call :accept
if errorlevel 1 exit /b 1
exit /b 0

:consider_version
call :consider "%LocalAppData%\Programs\Python\Python%1\python.exe"
if not errorlevel 1 exit /b 0
call :consider "%ProgramFiles%\Python%1\python.exe"
if not errorlevel 1 exit /b 0
call :consider "%VP_PF86%\Python%1\python.exe"
if not errorlevel 1 exit /b 0
exit /b 1

:consider
set "VP_PYTHON="
set "CANDIDATE=%~1"
if "%CANDIDATE%"=="" exit /b 1
echo "%CANDIDATE%" | find /I "WindowsApps" >nul
if not errorlevel 1 exit /b 1
if exist "%CANDIDATE%" goto :consider_file
where "%CANDIDATE%" >nul 2>&1
if errorlevel 1 exit /b 1
for /f "delims=" %%P in ('where "%CANDIDATE%"') do (
  call :consider_one "%%P"
  if not errorlevel 1 goto :consider_ok
)
exit /b 1

:consider_ok
exit /b 0

:consider_file
set "VP_PYTHON=%CANDIDATE%"
call :accept
if errorlevel 1 exit /b 1
exit /b 0

:consider_one
echo "%~1" | find /I "WindowsApps" >nul
if not errorlevel 1 exit /b 1
set "VP_PYTHON=%~1"
call :accept
if errorlevel 1 exit /b 1
exit /b 0

:accept
if not defined VP_PYTHON exit /b 1
echo "%VP_PYTHON%" | find /I "WindowsApps" >nul
if not errorlevel 1 exit /b 1
"%VP_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
if errorlevel 1 goto :too_old
exit /b 0

:too_old
if not defined VP_OLD_PYTHON set "VP_OLD_PYTHON=%VP_PYTHON%"
set "VP_PYTHON="
exit /b 1
