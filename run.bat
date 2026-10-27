@echo off
setlocal
cd /d "%~dp0"
title VideoPixel - pornire

rem ---- 1. Python ----
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if defined PY goto :havepy
echo Python nu este instalat. Il instalez cu winget...
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo Gata. INCHIDE aceasta fereastra si porneste din nou run.bat
pause
exit /b 1

:havepy
rem ---- 2. VLC (64 biti) ----
if exist "%ProgramFiles%\VideoLAN\VLC\libvlc.dll" goto :havevlc
echo VLC (64 biti) nu a fost gasit. Il instalez cu winget...
winget install -e --id VideoLAN.VLC --accept-package-agreements --accept-source-agreements
if exist "%ProgramFiles%\VideoLAN\VLC\libvlc.dll" goto :havevlc
echo.
echo Nu am reusit sa instalez VLC automat. Instaleaza-l manual (versiunea 64-bit) de la videolan.org
echo apoi porneste din nou run.bat
pause
exit /b 1

:havevlc
rem ---- 3. Mediu Python + dependente ----
if exist ".venv\Scripts\pythonw.exe" goto :run
echo Prima pornire: instalez dependentele (dureaza 1-2 minute)...
%PY% -m venv .venv || goto :err
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :err

:run
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:err
echo.
echo Eroare la instalarea dependentelor. Verifica conexiunea la internet si incearca din nou.
rmdir /s /q .venv 2>nul
pause
exit /b 1
