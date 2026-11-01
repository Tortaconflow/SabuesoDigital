@echo off
title Sabueso Digital 2.0 - CÍDIKS Sales Engine
cd /d "%~dp0"

python launch.py %*
if %ERRORLEVEL% EQU 0 goto END

py -3 launch.py %*
if %ERRORLEVEL% EQU 0 goto END

echo [ERROR] No se pudo encontrar Python instalado en el sistema.
pause

:END
exit /b 0
