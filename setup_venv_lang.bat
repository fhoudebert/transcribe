@echo off
rem ============================================================================
rem  setup_venv_lang.bat - Environnement Python portable Windows + langues
rem
rem  Pendant Windows de setup_venv_lang.sh :
rem    - venv cree dans build\python\venv-windows (le venv Linux, dans
rem      build\python\venv, cohabite sur la meme cle : les extensions
rem      compilees .so / .pyd ne sont pas interchangeables) ;
rem    - paquets de langues Argos installes dans build\argos-data\packages,
rem      PARTAGES avec Linux (donnees independantes de l'OS) ;
rem    - mode --copies : aucun lien symbolique, compatible exFAT.
rem
rem  Prerequis : Python 3.12 installe depuis python.org (avec le lanceur
rem  "py" et tkinter, coches par defaut par l'installateur).
rem ============================================================================
setlocal
set "SCRIPT_DIR=%~dp0"
set "VENV=%SCRIPT_DIR%build\python\venv-windows"

echo [1/4] Recherche de Python...
rem Preference : Python 3.12, la version avec laquelle le gel de
rem requirements.txt a ete produit et valide. Un Python plus recent peut
rem manquer de roues precompilees pour certaines versions figees.
set "PYCMD="
py -3.12 --version >nul 2>nul && set "PYCMD=py -3.12"
if not defined PYCMD (
    py -3 --version >nul 2>nul && (
        set "PYCMD=py -3"
        echo [AVERTISSEMENT] Python 3.12 introuvable, utilisation de :
        py -3 --version
        echo                 En cas d'echec pip, installez Python 3.12 :
        echo                 https://www.python.org/downloads/
    )
)
if not defined PYCMD (
    where python >nul 2>nul || (
        echo [ERREUR] Python introuvable. Installez Python 3.12 depuis
        echo          https://www.python.org/downloads/ ^(cocher "py launcher"^)
        exit /b 1
    )
    set "PYCMD=python"
)
%PYCMD% --version

echo [2/4] Creation du virtualenv --copies dans %VENV% ...
if exist "%VENV%" rmdir /s /q "%VENV%"
%PYCMD% -m venv --copies "%VENV%" || exit /b 1
call "%VENV%\Scripts\activate.bat" || exit /b 1
python -m pip install --upgrade pip || exit /b 1

echo [3/4] Installation des dependances Python...
if exist "%SCRIPT_DIR%build\python\requirements.txt" (
    pip install -r "%SCRIPT_DIR%build\python\requirements.txt" || exit /b 1
) else if exist "%SCRIPT_DIR%requirements.txt" (
    pip install -r "%SCRIPT_DIR%requirements.txt" || exit /b 1
) else (
    echo [AVERTISSEMENT] aucun requirements.txt trouve
)

echo [4/4] Paquets de langues Argos Translate ^(volumineux, patience...^)
echo        vers %SCRIPT_DIR%build\argos-data\packages ^(partages avec Linux^)
if not exist "%SCRIPT_DIR%build\argos-data\packages" mkdir "%SCRIPT_DIR%build\argos-data\packages"
set "ARGOS_PACKAGES_DIR=%SCRIPT_DIR%build\argos-data\packages"
set "ARGOS_TRANSLATE_PACKAGE_DIR=%SCRIPT_DIR%build\argos-data\packages"
argospm list | findstr /C:"translate" >nul
if errorlevel 1 (
    argospm update || exit /b 1
    argospm install translate || exit /b 1
) else (
    echo        paquets deja presents, rien a faire.
)

echo.
echo Environnement pret.
echo Activation manuelle : %VENV%\Scripts\activate.bat
endlocal
