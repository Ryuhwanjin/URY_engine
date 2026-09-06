@echo off
title URY Engine v0.6.3 - Windows Automated Environment Test
cd /d "%~dp0"

echo =========================================================
echo  URY Engine v0.6.3 Windows Automated Environment Test
echo =========================================================
echo.

set "PY_CMD="

if exist "%~dp0python\python.exe" (
    set "PY_CMD=%~dp0python\python.exe"
    goto FOUND_PY
)

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PY_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
    goto FOUND_PY
)
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
    goto FOUND_PY
)
if exist "%LocalAppData%\Programs\Python\Python310\python.exe" (
    set "PY_CMD=%LocalAppData%\Programs\Python\Python310\python.exe"
    goto FOUND_PY
)

if exist "C:\Program Files\Python312\python.exe" (
    set "PY_CMD=C:\Program Files\Python312\python.exe"
    goto FOUND_PY
)
if exist "C:\Program Files\Python311\python.exe" (
    set "PY_CMD=C:\Program Files\Python311\python.exe"
    goto FOUND_PY
)
if exist "C:\Program Files\Python310\python.exe" (
    set "PY_CMD=C:\Program Files\Python310\python.exe"
    goto FOUND_PY
)

for /f "delims=" %%i in ('where python 2^>nul') do (
    echo %%i | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        set "PY_CMD=%%i"
        goto FOUND_PY
    )
)

:NO_PY
echo.
echo [] ̽(Python) PC ġǾ  ʽϴ!
pause
exit /b 1

:FOUND_PY
echo [ȳ] ̽  Ȯ: "%PY_CMD%"
echo [ȳ]  10 ٽ  ڵ  Ʈ մϴ...
echo.

"%PY_CMD%" "%~dp0system\code\test_win_environment.py"

echo.
echo  ڵ ׽Ʈ ϷǾϴ.
pause
