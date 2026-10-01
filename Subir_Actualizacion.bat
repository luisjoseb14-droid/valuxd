@echo off
setlocal
title Subir Actualizacion a GitHub - CC Subs Pro
cd /d "%~dp0"

echo =======================================================
echo     CC SUBS PRO - SUBIR ACTUALIZACION A GITHUB
echo =======================================================
echo.
echo Repositorio: https://github.com/luisjoseb14-droid/valuxd
echo.
set /p "DESC=Describe los cambios (ej: Nuevo preset Juan): "
if "%DESC%"=="" set "DESC=Actualizacion de presets y mejoras"

echo.
echo [*] Guardando archivos y version en Git...
python core\updater.py --bump "%DESC%"
git add -A
git commit -m "%DESC%" >nul 2>&1

echo.
echo [*] Subiendo a GitHub...
git push -u origin main

if errorlevel 1 goto :fallo

echo.
echo =======================================================
echo   EXITO: Los cambios se subieron correctamente a GitHub!
echo   Tus amigos ya pueden pulsar 'Actualizar' en la app.
echo =======================================================
goto :fin

:fallo
echo.
echo =======================================================
echo   [!] NO SE PUDO SUBIR A GITHUB
echo =======================================================
echo Posibles causas:
echo 1. Falta autorizar tu cuenta de GitHub en la ventana emergente.
echo 2. No hay conexion a internet.
echo =======================================================

:fin
echo.
pause
