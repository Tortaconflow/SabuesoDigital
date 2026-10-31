@echo off
title Sabueso Digital 2.0 - CÍDIKS Sales Engine
cd /d "%~dp0"

echo ============================================================
echo   SABUESO DIGITAL 2.0 -- CIDIKS SALES ENGINE
echo ============================================================

:: Verificar si el servidor ya esta activo en el puerto 5000
netstat -ano | findstr "127.0.0.1:5000" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo El servidor ya esta ejecutandose en segundo plano.
    goto OPEN_BROWSER
)

echo Iniciando servidor local Flask...
start /b python app.py > app.log 2>&1

:: Esperar a que el servidor responda
setlocal enabledelayedexpansion
set RETRIES=0
:WAIT_LOOP
timeout /t 1 /nobreak >nul
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5000/api/status' -TimeoutSec 1; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Servidor listo y activo.
    goto OPEN_BROWSER
)

set /a RETRIES+=1
if !RETRIES! LEQ 8 goto WAIT_LOOP

echo Advertencia: El servidor tardo mas de lo esperado en responder.
:OPEN_BROWSER
echo Abriendo navegador en http://127.0.0.1:5000/ ...
start http://127.0.0.1:5000/
exit /b 0
