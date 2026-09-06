@echo off
title URY Engine v0.6.5 - Windows Academic Studio
cd /d "%~dp0"

echo =========================================================
echo  URY Engine v0.6.5 (Windows Academic Studio)
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
echo.
echo [̽ ġ ȳ]:
echo 1.    ̽ ٿε  ϴ.
echo 2. ġ   ȭ Ʒ [Add python.exe to PATH] üũڽ ݵ üũϼ!
echo 3. [Install Now] ŬϽø 30  ġ Ϸ˴ϴ.
echo.
start https://www.python.org/downloads/
echo ƹ Ű ø â ˴ϴ.
pause
exit /b 1

:FOUND_PY
echo [ȳ]  ̽ : "%PY_CMD%"
echo [ȳ] URY Engine GUI Ʃ մϴ...
echo.

"%PY_CMD%" "%~dp0system\code\settings_gui.py"

if %errorlevel% neq 0 (
    echo.
    echo [˸] α׷    ߻Ͽϴ. ( ڵ: %errorlevel%)
    pause
    exit /b %errorlevel%
)

echo.
echo α׷  Ǿϴ.
