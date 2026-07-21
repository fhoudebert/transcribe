@echo off
rem ==============================================================
rem  audio2en.bat  —  Transcription audio -> texte brut (.txt)
rem  Usage : audio2en.bat <fichier> [base|medium|large] [langue]
rem
rem  Pendant Windows d'audio2en.sh (voir ce dernier pour la doc).
rem    langue : code ISO 639-1 passé à whisper via -l
rem             vide = auto-détection whisper
rem ==============================================================
setlocal EnableExtensions
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "FFMPEG_BIN=%SCRIPT_DIR%build\ffmpeg\bin\ffmpeg.exe"
set "WHISPER_DIR=%SCRIPT_DIR%build\whisper"
set "WHISPER_BIN=%WHISPER_DIR%\whisper-cli.exe"

set "INPUT=%~1"
set "MODEL_NAME=%~2"
if "%MODEL_NAME%"=="" set "MODEL_NAME=medium"
set "SRC_LANG=%~3"

set "MODEL=%WHISPER_DIR%\models\ggml-%MODEL_NAME%.bin"

if "%INPUT%"=="" (
    echo Usage : audio2en.bat ^<fichier^> [base^|medium^|large] [langue]
    exit /b 1
)
if not exist "%INPUT%"       ( echo [ERREUR] Fichier introuvable : %INPUT% & exit /b 1 )
if not exist "%FFMPEG_BIN%"  ( echo [ERREUR] ffmpeg introuvable : %FFMPEG_BIN% & exit /b 1 )
if not exist "%WHISPER_BIN%" ( echo [ERREUR] whisper-cli introuvable : %WHISPER_BIN% & exit /b 1 )
if not exist "%MODEL%"       ( echo [ERREUR] Modèle introuvable : %MODEL% & exit /b 1 )

set "BASE_FULL=%~dpn1"
set "TXT_FILE=%BASE_FULL%.txt"
set "WAV_FILE=%BASE_FULL%.__audio2en__.wav"

echo Fichier  : %INPUT%
echo Modèle   : %MODEL_NAME%
if "%SRC_LANG%"=="" ( echo Langue   : auto-détection ) else ( echo Langue   : %SRC_LANG% )

echo.
echo === Conversion audio -^> WAV 16kHz mono ===
"%FFMPEG_BIN%" -y -i "%INPUT%" -ar 16000 -ac 1 -c:a pcm_s16le "%WAV_FILE%"
if errorlevel 1 exit /b 1

echo.
echo === Transcription Whisper (texte brut, sans traduction) ===
if "%SRC_LANG%"=="" (
    "%WHISPER_BIN%" -m "%MODEL%" -f "%WAV_FILE%" -otxt -of "%BASE_FULL%"
) else (
    "%WHISPER_BIN%" -m "%MODEL%" -f "%WAV_FILE%" -l %SRC_LANG% -otxt -of "%BASE_FULL%"
)
set "RC=%ERRORLEVEL%"
del /q "%WAV_FILE%" 2>nul
if not "%RC%"=="0" exit /b %RC%

if not exist "%TXT_FILE%" (
    echo [ERREUR] Fichier texte non généré : %TXT_FILE%
    exit /b 1
)

echo.
echo === Terminé ===
echo Transcription : %TXT_FILE%
endlocal
