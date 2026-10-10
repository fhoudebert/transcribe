@echo off
rem ==============================================================
rem  download_url.bat  —  Téléchargement vidéo via yt-dlp
rem  Usage : download_url.bat <url> [dossier_sortie]
rem
rem  Pendant Windows de download_url.sh (voir ce dernier pour la doc).
rem  La GUI récupère le fichier produit via la ligne :
rem    OUTFILE:E:\chemin\vers\fichier.mp4
rem
rem  Options facultatives, transmises par la GUI en variables d'environnement
rem  (les virgules d'un argument casseraient cmd : d'où l'environnement).
rem  Absentes : comportement historique (une piste audio, pas de sous-titres).
rem    TRANSCRIBE_DL_SUBS      langues de sous-titres, separees par des virgules
rem                            -> fichiers "<video>.<langue>.srt" a cote de la
rem                            video (jamais incrustes : un SRT vide ferait
rem                            echouer tout le post-traitement yt-dlp)
rem    TRANSCRIBE_DL_AUTOSUBS  1 = au moins une langue est un sous-titre
rem                            genere automatiquement
rem    TRANSCRIBE_DL_AUDIO     langues audio a fusionner (2 ou plus), dans
rem                            l'ordre des pistes voulu. Conteneur : mp4.
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

rem === Options facultatives (voir l'en-tête) ===============================
rem NB : aucune ligne "call" ne doit contenir de caret (^) : CALL le re-traite.
set "FMT_DEFAULT=bv*[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/bv*+ba/best[ext=mp4]/best"
set "FMT_VIDEO=bv*[ext=mp4][vcodec^=avc1]"
set "FMT=%FMT_DEFAULT%"
set "EXTRA_AUDIO="
set "A_M4A="
set "A_ANY="
set "A_COUNT=0"
if defined TRANSCRIBE_DL_AUDIO (
    for %%L in (%TRANSCRIBE_DL_AUDIO%) do (
        call set "A_M4A=%%A_M4A%%+ba[language=%%L][ext=m4a]"
        call set "A_ANY=%%A_ANY%%+ba[language=%%L]"
        set /a A_COUNT+=1
    )
)
rem Ligne separee (hors bloc) pour que les %...% soient lus apres la boucle.
rem Repli sur la selection historique si aucun format ne correspond.
if %A_COUNT% GEQ 2 set "FMT=%FMT_VIDEO%%A_M4A%/bv*%A_ANY%/%FMT_DEFAULT%"
if %A_COUNT% GEQ 2 set "EXTRA_AUDIO=--audio-multistreams"
if %A_COUNT% GEQ 2 echo Pistes audio : %TRANSCRIBE_DL_AUDIO%

set "SUBLANGS=all,-live_chat"
set "SUBS_FLAGS="
set "AUTOSUBS_FLAG=--no-write-auto-subs"
if defined TRANSCRIBE_DL_SUBS (
    set "SUBLANGS=%TRANSCRIBE_DL_SUBS%"
    set "SUBS_FLAGS=--write-subs --convert-subs srt"
    if "%TRANSCRIBE_DL_AUTOSUBS%"=="1" set "AUTOSUBS_FLAG=--write-auto-subs"
    echo Sous-titres : %TRANSCRIBE_DL_SUBS%
)

rem Options demandees : retelecharger meme si le fichier existe deja (sinon
rem yt-dlp saute la video et garde l'ancienne, sans pistes/sous-titres).
set "FORCE_FLAG="
if %A_COUNT% GEQ 2 set "FORCE_FLAG=--force-overwrites"
if defined TRANSCRIBE_DL_SUBS set "FORCE_FLAG=--force-overwrites"

rem Commande reellement lancee (affichee dans le journal de l'IHM)
echo Commande :
echo   "%YTDLP%" -f "%FMT%" -S "vcodec:h264,lang,quality,res,fps,hdr:12,acodec:aac" --merge-output-format mp4 --remux-video mp4 --restrict-filenames %EXTRA_AUDIO% %SUBS_FLAGS% --sub-langs "%SUBLANGS%" %AUTOSUBS_FLAG% %FORCE_FLAG% --embed-thumbnail --embed-chapters -P "%OUTDIR%" "%URL%"
echo.

"%YTDLP%" ^
    -f "%FMT%" ^
    -S "vcodec:h264,lang,quality,res,fps,hdr:12,acodec:aac" ^
    --merge-output-format mp4 ^
    --remux-video mp4 ^
    --restrict-filenames ^
    %EXTRA_AUDIO% ^
    %SUBS_FLAGS% ^
    --sub-langs "%SUBLANGS%" ^
    %AUTOSUBS_FLAG% ^
    %FORCE_FLAG% ^
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
