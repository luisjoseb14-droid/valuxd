@echo off
chcp 65001 >nul
title CC Subs Pro - Instalador para Windows
color 0B

echo =======================================================
echo          CC SUBS PRO - INSTALADOR AUTOMATICO
echo   Estilizador de Subtitulos para CapCut (Doctores)
echo =======================================================
echo.

:: 0. Detectar si se esta ejecutando dentro de un ZIP sin extraer
if not exist "%~dp0core" (
    color 0C
    echo.
    echo [!] ATENCION: Abriste el instalador dentro del archivo .ZIP sin descomprimir.
    echo.
    echo Para instalarlo correctamente:
    echo   1. Cierra esta ventana.
    echo   2. Haz clic derecho sobre el archivo ZIP.
    echo   3. Elige 'Extraer todo...' y dale a Extraer.
    echo   4. Entra en la carpeta extraida y ejecuta 'Instalar_CC_Subs_Pro.bat'.
    echo.
    pause
    exit /b 1
)

:: 1. Verificar si Python esta disponible
echo [*] Verificando entorno de Python...

set "PYTHON_CMD="
set "PYTHONW_CMD="

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    set "PYTHONW_CMD=pythonw"
    goto :python_ready
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py"
    set "PYTHONW_CMD=pyw"
    goto :python_ready
)

:: Buscar en rutas habituales de instalacion
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    set "PYTHONW_CMD=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
    goto :python_ready
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    set "PYTHONW_CMD=%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
    goto :python_ready
)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    set "PYTHONW_CMD=%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe"
    goto :python_ready
)

:: Python no encontrado -> Instalar automaticamente en segundo plano
color 0E
echo.
echo [i] Python no esta presente en este equipo.
echo [*] Instalando Python automaticamente en segundo plano...
echo     (No requiere permisos de administrador, espera unos segundos...)
echo.

if exist "%~dp0installer\python_setup.exe" goto :run_python_installer

:: Si no esta empaquetado, descargarlo
echo [*] Descargando instalador de Python...
curl.exe -L -o "%TEMP%\python_setup.exe" "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
if %errorlevel% neq 0 (
    color 0C
    echo [!] Error al descargar Python. Verifica tu conexion a internet.
    pause
    exit /b 1
)
set "INSTALLER_PATH=%TEMP%\python_setup.exe"
goto :exec_python_install

:run_python_installer
set "INSTALLER_PATH=%~dp0installer\python_setup.exe"

:exec_python_install
echo [*] Ejecutando instalacion silenciosa de Python...
"%INSTALLER_PATH%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1

:: Esperar brevemente a que Windows registre los ejecutables
timeout /t 6 /nobreak >nul

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    set "PYTHONW_CMD=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
    color 0B
    echo [OK] Python instalado y configurado correctamente!
    echo.
    goto :python_ready
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    set "PYTHONW_CMD=pythonw"
    color 0B
    echo [OK] Python detectado correctamente!
    echo.
    goto :python_ready
)

color 0C
echo [!] No se pudo verificar la instalacion automatica.
echo     Por favor ejecuta manualmente el instalador incluido:
echo     %INSTALLER_PATH%
echo.
pause
exit /b 1

:python_ready
color 0B
echo [OK] Motor Python activo: %PYTHON_CMD%
echo.

:: 2. Instalar fuentes y assets de doctores
echo [*] Instalando fuentes de los 4 doctores y assets de CapCut...
"%PYTHON_CMD%" -m core.font_installer
echo.

:: 3. Configurar lanzador Iniciar_CC_Subs_Pro.bat
echo [*] Configurando lanzadores...
(
echo @echo off
echo cd /d "%%~dp0"
echo title CC Subs Pro
echo set "PY_CMD="
echo where pythonw ^>nul 2^>^&1 ^&^& set "PY_CMD=pythonw"
echo if not defined PY_CMD if exist "%%LOCALAPPDATA%%\Programs\Python\Python312\pythonw.exe" set "PY_CMD=%%LOCALAPPDATA%%\Programs\Python\Python312\pythonw.exe"
echo if not defined PY_CMD if exist "%%LOCALAPPDATA%%\Programs\Python\Python311\pythonw.exe" set "PY_CMD=%%LOCALAPPDATA%%\Programs\Python\Python311\pythonw.exe"
echo if not defined PY_CMD if exist "%%LOCALAPPDATA%%\Programs\Python\Python310\pythonw.exe" set "PY_CMD=%%LOCALAPPDATA%%\Programs\Python\Python310\pythonw.exe"
echo if not defined PY_CMD set "PY_CMD=python"
echo start "" "%%PY_CMD%%" gui.py
) > "%~dp0Iniciar_CC_Subs_Pro.bat"

copy /y "%~dp0Iniciar_CC_Subs_Pro.bat" "%~dp0run_gui.bat" >nul
echo [OK] Lanzadores configurados exitosamente.
echo.

:: 4. Crear Acceso Directo en el Escritorio mediante PowerShell
echo [*] Creando acceso directo en el Escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desktop = [Environment]::GetFolderPath('Desktop'); $shortcut = $ws.CreateShortcut(\"$desktop\CC Subs Pro.lnk\"); $shortcut.TargetPath = '%~dp0Iniciar_CC_Subs_Pro.bat'; $shortcut.WorkingDirectory = '%~dp0'; $shortcut.Description = 'CC Subs Pro - Estilizador de Subtitulos CapCut'; $shortcut.Save()"

if exist "%USERPROFILE%\Desktop\CC Subs Pro.lnk" (
    echo [OK] Acceso directo 'CC Subs Pro' creado en el Escritorio.
) else (
    echo [i] Puedes abrir el programa desde 'Iniciar_CC_Subs_Pro.bat'.
)

echo.
echo =======================================================
color 0A
echo        INSTALACION COMPLETADA EXITOSAMENTE
echo.
echo   1. Python listo y configurado.
echo   2. Las 9 fuentes de los doctores estan listas.
echo   3. Sonidos y efectos de CapCut configurados.
echo   4. Acceso directo 'CC Subs Pro' en tu Escritorio.
echo =======================================================
echo.
echo Presiona cualquier tecla para abrir CC Subs Pro ahora...
pause >nul

start "" "%~dp0Iniciar_CC_Subs_Pro.bat"
exit /b 0
