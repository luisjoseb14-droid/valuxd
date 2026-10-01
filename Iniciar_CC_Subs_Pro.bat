@echo off
cd /d "%~dp0"
title CC Subs Pro

where py >nul 2>&1
if %errorlevel% equ 0 (
    start "" py -3 gui.py
    exit /b 0
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    start "" python gui.py
    exit /b 0
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" gui.py
    exit /b 0
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" gui.py
    exit /b 0
)

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" gui.py
    exit /b 0
)

color 0C
echo =======================================================
echo  [!] No se encontro la instalacion de Python.
echo  Por favor ejecuta primero 'Instalar_CC_Subs_Pro.bat'
echo =======================================================
echo.
pause
exit /b 1
