@echo off
chcp 65001 >nul
title Subir Actualización a GitHub - CC Subs Pro
cd /d "%~dp0"

echo =======================================================
echo     CC SUBS PRO - SUBIR ACTUALIZACIÓN A GITHUB
echo =======================================================
echo.
echo Este script guardará tus últimos cambios (presets nuevos,
echo fuentes agregadas, etc.) y los subirá a tu repositorio:
echo https://github.com/luisjoseb14-droid/valuxd
echo.
echo De esta forma, tus amigos solo tendrán que pulsar el botón
echo 'Actualizar' dentro de CC Subs Pro para recibir la nueva letra.
echo.
echo -------------------------------------------------------
set /p "DESC=Describe los cambios (ej: Nuevo preset Juan): "
if "%DESC%"=="" set "DESC=Actualización de presets y mejoras en CC Subs Pro"

echo.
echo [*] Incrementando número de versión en version.json...
python core\updater.py --bump "%DESC%"

echo.
echo [*] Agregando archivos a Git...
git add -A

echo.
echo [*] Creando commit...
git commit -m "%DESC%"

echo.
echo [*] Subiendo a GitHub (rama main)...
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =======================================================
    echo   ¡ÉXITO! Los cambios ya están disponibles en GitHub.
    echo   Tus amigos ya pueden pulsar 'Actualizar' en la app.
    echo =======================================================
) else (
    echo.
    echo [!] Hubo un error al subir a GitHub. Revisa si necesitas
    echo     autenticar tu cuenta de GitHub o si tienes conexión.
)

echo.
pause
