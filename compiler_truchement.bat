@echo off
rem  compiler_truchement.bat - compile truchement et deploie a la racine
rem  (binaire truchement.exe, assets fusionnes, i18n). Toute la logique est dans
rem  compile_app.py (multiplateforme) : stdlib complete embarquee, cf.
rem  commentaires du script (ModuleNotFoundError pickletools sinon).
setlocal
set "SCRIPT_DIR=%~dp0"
rem Python portable de la cle (setup_python.bat) ; ancien venv en repli.
set "VPY=%SCRIPT_DIR%build\python\windows\python.exe"
if not exist "%VPY%" set "VPY=%SCRIPT_DIR%build\python\venv-windows\Scripts\python.exe"
if not exist "%VPY%" (
    echo [ERREUR] Python portable introuvable : lancez d'abord setup_python.bat
    exit /b 1
)
"%VPY%" "%SCRIPT_DIR%compile_app.py" truchement || exit /b 1
endlocal
