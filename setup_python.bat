@echo off
rem ============================================================================
rem  setup_python.bat - Python portable de transcribe / truchement (Windows)
rem
rem  Pendant Windows de setup_python.sh : installe un CPython COMPLET et
rem  DEPLACABLE (python-build-standalone, build "stripped", Python 3.12.15)
rem  dans build\python\windows, puis les paquets de requirements.txt
rem  DIRECTEMENT dedans (pas de venv) et les paquets de langues Argos dans
rem  build\argos-data\packages (partages avec Linux).
rem  Aucun Python installe sur l'ordinateur n'est necessaire ni utilise.
rem  Le Python Linux (build/python/linux) cohabite sur la meme cle.
rem  Necessite Windows 10 1803 ou plus recent (curl.exe et tar.exe integres).
rem
rem  Les lanceurs que pip pose dans Scripts\ (argospm.exe, pyinstaller.exe...)
rem  contiennent un chemin ABSOLU : on passe toujours par python.exe -m / -c.
rem
rem  Relancable sans risque.
rem    --force    reinstalle Python
rem    --no-lang  n'installe pas les paquets de langues Argos
rem ============================================================================
setlocal EnableExtensions
set "PBS_TAG=20261013"
set "PY_VERSION=3.12.15"
set "ASSET=cpython-%PY_VERSION%+%PBS_TAG%-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
set "SHA256=7a2aef48e5ee569e310b29b32681debbc5d888e92790d85331a47736c6b06aad"
set "URL=https://github.com/astral-sh/python-build-standalone/releases/download/%PBS_TAG%/%ASSET%"

set "ROOT=%~dp0"
set "DEST=%ROOT%build\python\windows"
set "PY=%DEST%\python.exe"
set "ARGOS_DATA_DIR=%ROOT%build\argos-data\packages"

set "FORCE="
set "NOLANG="
:args
if "%~1"=="" goto args_done
if /i "%~1"=="--force" (set "FORCE=1" & shift & goto args)
if /i "%~1"=="--no-lang" (set "NOLANG=1" & shift & goto args)
echo option inconnue : %~1 ^(--force, --no-lang^)
exit /b 2
:args_done

rem Isolation : ni le site utilisateur ni un PYTHONPATH herite.
set "PYTHONPATH="
set "PYTHONHOME="
set "PYTHONNOUSERSITE=1"
set "PIP_USER=0"

rem Un Python n'est conserve qu'avec le marqueur ".complete" d'une
rem installation terminee : une installation interrompue est refaite.
if defined FORCE if exist "%DEST%" rmdir /s /q "%DEST%"
if exist "%DEST%\.complete" goto have_python
if exist "%DEST%" (
    echo [1/4] Python incomplet trouve, reinstallation
    rmdir /s /q "%DEST%"
)

rem Telechargement et extraction SUR LA CLE (pas dans %%TEMP%%, souvent sur
rem C:) : l'etape finale est alors un renommage, pas une copie.
if not exist "%ROOT%build\python" mkdir "%ROOT%build\python"
set "TMPD=%ROOT%build\python\tmp-%RANDOM%"
mkdir "%TMPD%" || goto fail
echo [1/4] Telechargement de Python %PY_VERSION%
curl.exe -fL --retry 3 -o "%TMPD%\py.tar.gz" "%URL%" || goto fail_dl
set "GOT="
for /f "skip=1 delims=" %%H in ('certutil -hashfile "%TMPD%\py.tar.gz" SHA256') do if not defined GOT set "GOT=%%H"
set "GOT=%GOT: =%"
if /i not "%GOT%"=="%SHA256%" (
    echo somme de controle incorrecte, telechargement refuse
    goto fail_dl
)
echo        extraction...
tar.exe -xzf "%TMPD%\py.tar.gz" -C "%TMPD%" || goto fail_dl
move "%TMPD%\python" "%DEST%" >nul || goto fail_dl
rmdir /s /q "%TMPD%" 2>nul
rem la bibliotheque standard, tkinter et pip doivent etre complets
"%PY%" -c "import encodings, ssl, sqlite3, tkinter, pip._internal.cli.main" || goto fail_broken
echo ok> "%DEST%\.complete"
goto installed

:have_python
echo [1/4] Python deja present :
"%PY%" --version

:installed
set "REQ="
if exist "%ROOT%build\python\requirements.txt" (
    set "REQ=%ROOT%build\python\requirements.txt"
) else if exist "%ROOT%requirements.txt" (
    set "REQ=%ROOT%requirements.txt"
)
if not defined REQ goto no_req
rem hors bloc ( ) : un chemin contenant une parenthese n'y casse rien
echo [2/4] Installation des paquets (%REQ%) - torch est volumineux, patience
"%PY%" -m pip install --disable-pip-version-check --no-warn-script-location -q -r "%REQ%" || goto fail
goto langs
:no_req
echo [2/4] [AVERTISSEMENT] aucun requirements.txt trouve

:langs
if defined NOLANG (
    echo [3/4] Paquets de langues ignores ^(--no-lang^)
    goto check
)
echo [3/4] Paquets de langues Argos Translate vers %ARGOS_DATA_DIR%
if not exist "%ARGOS_DATA_DIR%" mkdir "%ARGOS_DATA_DIR%"
set "ARGOS_PACKAGES_DIR=%ARGOS_DATA_DIR%"
set "ARGOS_TRANSLATE_PACKAGE_DIR=%ARGOS_DATA_DIR%"
set "ARGOSPM=import sys; from argostranslate.argospm import main; sys.argv[0] = 'argospm'; sys.exit(main())"
"%PY%" -c "%ARGOSPM%" list | findstr /C:"translate" >nul
if errorlevel 1 (
    echo        volumineux, patience...
    "%PY%" -c "%ARGOSPM%" update || goto fail
    "%PY%" -c "%ARGOSPM%" install translate || goto fail
) else (
    echo        paquets deja presents, rien a faire.
)

:check
echo [4/4] Verification
"%PY%" -c "import sys, tkinter, argostranslate.translate, ctranslate2, fitz, requests; print('Python', sys.version.split()[0], '- Tk', tkinter.TkVersion, '- ctranslate2', ctranslate2.__version__)" || goto fail
if exist "%ROOT%build\python\venv-windows" echo L'ancien venv build\python\venv-windows n'est plus utilise : il peut etre supprime.
echo Python portable pret : build\python\windows
endlocal
exit /b 0

:fail_broken
echo Le Python extrait est incomplet ^(fichiers manquants sur la cle ?^).
echo Un antivirus ou une cle pleine en sont les causes habituelles ; relancez setup_python.bat.
if exist "%DEST%" rmdir /s /q "%DEST%"
goto fail
:fail_dl
rmdir /s /q "%TMPD%" 2>nul
:fail
echo Echec de l'installation.
endlocal
exit /b 1
