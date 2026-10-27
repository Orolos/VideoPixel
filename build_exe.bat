@echo off
setlocal
cd /d "%~dp0"
title VideoPixel - creare .exe
echo ================================================
echo   VideoPixel - creare program (.exe) de impartit
echo ================================================
echo.

rem ---- 1. Python ----
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if defined PY goto :havepy
echo Python nu este instalat. Il instalez cu winget...
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo Gata. INCHIDE aceasta fereastra si porneste din nou build_exe.bat
pause
exit /b 1

:havepy
rem ---- 2. VLC 64 biti (se include in pachet, ca sa mearga pe orice PC) ----
set "VLCDIR=%ProgramFiles%\VideoLAN\VLC"
if exist "%VLCDIR%\libvlc.dll" goto :havevlc
echo VLC (64 biti) nu a fost gasit. Il instalez cu winget...
winget install -e --id VideoLAN.VLC --accept-package-agreements --accept-source-agreements
if exist "%VLCDIR%\libvlc.dll" goto :havevlc
echo.
echo Nu am reusit sa instalez VLC. Instaleaza-l manual (64-bit) de la videolan.org si ruleaza din nou.
pause
exit /b 1

:havevlc
rem ---- 3. Mediu de build ----
if exist ".buildenv\Scripts\python.exe" goto :havevenv
echo [1/4] Creez mediul de build...
%PY% -m venv .buildenv || goto :err
:havevenv
echo [2/4] Instalez dependentele si PyInstaller (prima data dureaza cateva minute)...
".buildenv\Scripts\python.exe" -m pip install --upgrade pip >nul
".buildenv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller || goto :err

rem ---- 4. Construieste programul ----
echo [3/4] Construiesc VideoPixel.exe...
if exist dist\VideoPixel rmdir /s /q dist\VideoPixel
if exist build rmdir /s /q build
".buildenv\Scripts\python.exe" -m PyInstaller --noconfirm --clean VideoPixel.spec || goto :err

echo [4/4] Adaug VLC in pachet...
mkdir "dist\VideoPixel\vlc" 2>nul
copy /y "%VLCDIR%\libvlc.dll" "dist\VideoPixel\vlc\" >nul || goto :err
copy /y "%VLCDIR%\libvlccore.dll" "dist\VideoPixel\vlc\" >nul || goto :err
xcopy /e /i /y /q "%VLCDIR%\plugins" "dist\VideoPixel\vlc\plugins" >nul || goto :err
if exist "%VLCDIR%\COPYING.txt" copy /y "%VLCDIR%\COPYING.txt" "dist\VideoPixel\vlc\" >nul

rem ---- 5. Arhiva .zip portabila ----
if exist dist\VideoPixel-portabil.zip del /q dist\VideoPixel-portabil.zip
powershell -NoProfile -Command "Compress-Archive -Path 'dist\VideoPixel' -DestinationPath 'dist\VideoPixel-portabil.zip' -Force"

rem ---- 6. Instalator (optional, daca exista Inno Setup) ----
set "ISCC="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if defined ISCC goto :haveiscc
echo Inno Setup nu este instalat. Incerc sa-l instalez pentru a crea instalatorul...
winget install -e --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
:haveiscc
if not defined ISCC goto :noinstaller
echo Creez instalatorul...
"%ISCC%" /Q installer.iss
goto :done
:noinstaller
echo (Instalatorul nu s-a creat: Inno Setup lipseste. Arhiva .zip portabila e gata.)

:done
rem ---- 7. Sume de control (SHA-256), ca destinatarii sa poata verifica fisierele ----
powershell -NoProfile -Command "Get-ChildItem dist\*.exe,dist\*.zip | Get-FileHash -Algorithm SHA256 | ForEach-Object { $_.Hash.ToLower() + '  ' + (Split-Path $_.Path -Leaf) } | Set-Content -Encoding ascii dist\SHA256SUMS.txt"

echo.
echo ================================================
echo   GATA!  Fisiere de impartit, in folderul dist:
echo     - VideoPixel-Setup.exe     (instalator, daca s-a creat)
echo     - VideoPixel-portabil.zip  (dezarhivezi si pornesti VideoPixel.exe)
echo     - SHA256SUMS.txt           (sume de control pentru verificare)
echo ================================================
explorer dist
pause
exit /b 0

:err
echo.
echo EROARE la creare. Verifica conexiunea la internet si incearca din nou.
pause
exit /b 1
