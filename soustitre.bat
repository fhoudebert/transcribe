@echo off
rem ============================================================
rem  soustitre.bat  —  Transcription audio -> SRT
rem  Usage : soustitre.bat <fichier> [base|medium|large] [yes|no] [src_lang|auto]
rem
rem  Pendant Windows de soustitre.sh (voir ce dernier pour la doc).
rem    3e argument : yes = traduit vers anglais (défaut)
rem                  no  = transcrit dans la langue source
rem    4e argument : langue de l'audio passée à whisper via -l
rem                  auto (défaut) = auto-détection whisper
rem ============================================================
setlocal EnableExtensions
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "FFMPEG_BIN=%SCRIPT_DIR%build\ffmpeg\bin\ffmpeg.exe"
set "WHISPER_DIR=%SCRIPT_DIR%build\whisper"
set "WHISPER_BIN=%WHISPER_DIR%\whisper-cli.exe"

set "INPUT=%~1"
set "MODEL_NAME=%~2"
if "%MODEL_NAME%"=="" set "MODEL_NAME=medium"
set "TRANSLATE=%~3"
if "%TRANSLATE%"=="" set "TRANSLATE=yes"
set "SRC_LANG=%~4"
if "%SRC_LANG%"=="" set "SRC_LANG=auto"

set "MODEL=%WHISPER_DIR%\models\ggml-%MODEL_NAME%.bin"

if "%INPUT%"=="" (
    echo Usage : soustitre.bat ^<fichier^> [base^|medium^|large] [yes^|no] [src_lang^|auto]
    exit /b 1
)
if not exist "%INPUT%"       ( echo [ERREUR] Fichier introuvable : %INPUT% & exit /b 1 )
if not exist "%FFMPEG_BIN%"  ( echo [ERREUR] ffmpeg introuvable : %FFMPEG_BIN% & exit /b 1 )
if not exist "%WHISPER_BIN%" ( echo [ERREUR] whisper-cli introuvable : %WHISPER_BIN% & exit /b 1 )
if not exist "%MODEL%"       ( echo [ERREUR] Modèle introuvable : %MODEL% & exit /b 1 )

set "BASE_FULL=%~dpn1"
set "WAV_FILE=%BASE_FULL%.wav"

if /i "%TRANSLATE%"=="yes" (
    set "SRT_OUT=%BASE_FULL%.en.srt"
    set "LABEL=traduction vers anglais"
) else (
    set "SRT_OUT=%BASE_FULL%.srt"
    set "LABEL=transcription langue source"
)

echo Fichier  : %INPUT%
echo Modèle   : %MODEL_NAME%
echo Mode     : %LABEL%
echo Lang src : %SRC_LANG%

echo.
echo === Extraction audio ===
"%FFMPEG_BIN%" -y -i "%INPUT%" -ar 16000 -ac 1 -c:a pcm_s16le "%WAV_FILE%"
if errorlevel 1 exit /b 1

echo.
echo === Whisper : %LABEL% ===
set "ARGS=-m "%MODEL%" -f "%WAV_FILE%" -osrt -of "%BASE_FULL%""
if not "%SRC_LANG%"=="auto" set "ARGS=%ARGS% -l %SRC_LANG%"
if /i "%TRANSLATE%"=="yes"  set "ARGS=%ARGS% -tr"
"%WHISPER_BIN%" %ARGS%
set "RC=%ERRORLEVEL%"
del /q "%WAV_FILE%" 2>nul
if not "%RC%"=="0" exit /b %RC%

rem whisper écrit %BASE_FULL%.srt ; en mode traduction, renomme en .en.srt
if /i "%TRANSLATE%"=="yes" (
    if exist "%BASE_FULL%.srt" (
        move /y "%BASE_FULL%.srt" "%SRT_OUT%" >nul
    )
)

if not exist "%SRT_OUT%" (
    echo [ERREUR] SRT non généré : %SRT_OUT%
    exit /b 1
)

echo.
echo === Terminé ===
echo Sous-titres : %SRT_OUT%
endlocal
