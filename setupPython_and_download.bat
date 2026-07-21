@echo off
rem ============================================================================
rem  setupPython_and_download.bat - Installation complete Windows (cle neuve)
rem  Pendant Windows de setupPython_and_download.sh :
rem    1. environnement Python portable + paquets de langues Argos ;
rem    2. composants de downloads.csv (modeles Whisper, dictionnaires) via
rem       download-assistant.exe s'il est present, sinon le telechargeur
rem       Python multiplateforme download_from_csv.py.
rem  Relancable sans risque : les composants deja presents sont conserves.
rem ============================================================================
setlocal
set "SCRIPT_DIR=%~dp0"

echo === Etape 1 : environnement Python + langues ===
call "%SCRIPT_DIR%setup_venv_lang.bat" || exit /b 1

echo.
echo === Etape 2 : telechargement des composants (downloads.csv) ===
if exist "%SCRIPT_DIR%download-assistant.exe" (
    "%SCRIPT_DIR%download-assistant.exe" || exit /b 1
) else (
    "%SCRIPT_DIR%build\python\venv-windows\Scripts\python.exe" ^
        "%SCRIPT_DIR%download_from_csv.py" "%SCRIPT_DIR%downloads.csv" || exit /b 1
)

echo.
echo Installation terminee avec succes.
echo Lancez maintenant compiler_truchement.bat puis truchement.exe
endlocal
