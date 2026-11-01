@echo off
rem ============================================================================
rem  setup_venv_lang.bat - conserve pour compatibilite, renvoie vers
rem  setup_python.bat : Python portable complet (python-build-standalone
rem  3.12.15) dans build\python\venv-windows, sans Python installe sur la
rem  machine (remplace l'ancien venv cree avec le Python du systeme).
rem ============================================================================
call "%~dp0setup_python.bat" %*
exit /b %errorlevel%
