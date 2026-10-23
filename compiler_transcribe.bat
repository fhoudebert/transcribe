@echo off
rem  compiler_transcribe.bat - compile transcribe et deploie a la racine
rem  (binaire transcribe.exe, assets fusionnes, i18n). Toute la logique est dans
rem  compile_app.py (multiplateforme et unique recette) :
rem  la stdlib n'est PAS embarquee (transcribe n'appelle le Python portable qu'en
rem  sous-processus) et ses paquets tiers sont exclus du binaire.
setlocal
set "SCRIPT_DIR=%~dp0"
rem Python portable de la cle (setup_python.bat) ; ancien venv en repli.
set "VPY=%SCRIPT_DIR%build\python\windows\python.exe"
if not exist "%VPY%" set "VPY=%SCRIPT_DIR%build\python\venv-windows\Scripts\python.exe"
if not exist "%VPY%" (
    echo [ERREUR] Python portable introuvable : lancez d'abord setup_python.bat
    exit /b 1
)
"%VPY%" "%SCRIPT_DIR%compile_app.py" transcribe || exit /b 1
endlocal
