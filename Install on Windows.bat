@echo off
rem Double-click this file to install Nudge on Windows.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 install.py %*
  goto :done
)
where python >nul 2>nul
if %errorlevel%==0 (
  python install.py %*
  goto :done
)

echo.
echo Nudge needs the free Python from python.org.
echo Opening the download page. Install it, then double-click this file again.
start "" "https://www.python.org/downloads/"

:done
echo.
pause
