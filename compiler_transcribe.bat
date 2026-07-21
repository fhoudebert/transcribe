@echo off
rem  compiler_transcribe.bat - compile transcribe et deploie a la racine
rem  (binaire transcribe.exe, assets fusionnes, i18n). Toute la logique est dans
rem  compile_app.py (multiplateforme) : stdlib complete embarquee, cf.
rem  commentaires du script (ModuleNotFoundError pickletools sinon).
setlocal
set "SCRIPT_DIR=%~dp0"
set "VPY=%SCRIPT_DIR%build\python\venv-windows\Scripts\python.exe"
if not exist "%VPY%" (
    echo [ERREUR] venv Windows introuvable : lancez d'abord setupPython_and_download.bat
    exit /b 1
)
"%VPY%" "%SCRIPT_DIR%compile_app.py" transcribe || exit /b 1
endlocal
