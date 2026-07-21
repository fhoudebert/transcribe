@echo off
rem ==============================================================
rem  download_url.bat  —  Téléchargement vidéo via yt-dlp
rem  Usage : download_url.bat <url> [dossier_sortie]
rem
rem  Pendant Windows de download_url.sh (voir ce dernier pour la doc).
rem  La GUI récupère le fichier produit via la ligne :
rem    OUTFILE:E:\chemin\vers\fichier.mp4
rem ==============================================================
setlocal EnableExtensions
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "YTDLP=%SCRIPT_DIR%build\yt-dlp\yt-dlp.exe"

set "URL=%~1"
set "OUTDIR=%~2"
if "%OUTDIR%"=="" set "OUTDIR=%SCRIPT_DIR%"

if "%URL%"=="" (
    echo Usage : download_url.bat ^<url^> [dossier_sortie]
    exit /b 1
)
if not exist "%YTDLP%" (
    echo [ERREUR] yt-dlp introuvable : %YTDLP%
    echo Téléchargez-le depuis : https://github.com/yt-dlp/yt-dlp/releases
    exit /b 1
)

echo URL    : %URL%
echo Dossier: %OUTDIR%
echo.

rem Fichier temporaire pour récupérer le chemin produit par yt-dlp
set "OUTFILE_TMP=%TEMP%\transcribe_dl_%RANDOM%%RANDOM%.txt"

"%YTDLP%" ^
    -f "bv*[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/bv*+ba/best[ext=mp4]/best" ^
    -S "vcodec:h264,lang,quality,res,fps,hdr:12,acodec:aac" ^
    --merge-output-format mp4 ^
    --remux-video mp4 ^
    --restrict-filenames ^
    --no-write-auto-subs ^
    --embed-thumbnail ^
    --embed-chapters ^
    --newline ^
    --progress ^
    -o "%%(title).80s [%%(id)s].%%(ext)s" ^
    --print-to-file "after_move:%%(filepath)s" "%OUTFILE_TMP%" ^
    -P "%OUTDIR%" ^
    "%URL%"
if errorlevel 1 (
    del /q "%OUTFILE_TMP%" 2>nul
    exit /b 1
)

set "RESULT="
if exist "%OUTFILE_TMP%" (
    set /p RESULT=<"%OUTFILE_TMP%"
    del /q "%OUTFILE_TMP%" 2>nul
)

echo.
if defined RESULT (
    echo OUTFILE:%RESULT%
) else (
    echo [INFO] Fichier téléchargé dans : %OUTDIR%
)
endlocal
