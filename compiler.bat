@echo off
rem  compiler.bat - compile transcribe puis truchement (Windows)
setlocal
set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%compiler_transcribe.bat" || exit /b 1
call "%SCRIPT_DIR%compiler_truchement.bat" || exit /b 1
echo compilation terminee
endlocal
