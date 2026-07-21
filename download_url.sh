#!/usr/bin/env bash
# ==============================================================
#  download_url.sh  —  Téléchargement vidéo via yt-dlp
#  Usage : download_url.sh <url> [dossier_sortie]
#
#  Arborescence attendue (relative au script) :
#    build/yt-dlp/yt-dlp
#
#  La GUI récupère le fichier produit via la ligne :
#    OUTFILE:/chemin/vers/fichier.mp4
# ==============================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YTDLP="$SCRIPT_DIR/build/yt-dlp/yt-dlp"

log() { printf '[%(%F %T)T] %s\n' -1 "$*"; }

URL="${1:-}"
OUTDIR="${2:-$SCRIPT_DIR}"

if [ -z "$URL" ]; then
    echo "Usage : download_url.sh <url> [dossier_sortie]"
    exit 1
fi

if [ ! -x "$YTDLP" ]; then
    echo "[ERREUR] yt-dlp introuvable : $YTDLP"
    echo "Téléchargez-le depuis : https://github.com/yt-dlp/yt-dlp/releases"
    exit 1
fi

log INFO "Début téléchargement"
echo "URL    : $URL"
echo "Dossier: $OUTDIR"
echo ""

# Fichier temporaire pour récupérer le chemin produit par yt-dlp
OUTFILE_TMP="$(mktemp)"
trap 'rm -f "$OUTFILE_TMP"' EXIT

"$YTDLP" \
    -f "bv*[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/bv*+ba/best[ext=mp4]/best" \
    -S "vcodec:h264,lang,quality,res,fps,hdr:12,acodec:aac" \
    --merge-output-format mp4 \
    --remux-video mp4 \
    --restrict-filenames \
    --no-write-auto-subs \
    --embed-thumbnail \
    -o "%(title).80s [%(id)s].%(ext)s" \
    --restrict-filenames \
    --embed-chapters \
    --xattrs \
    --newline \
    --progress \
    --print-to-file "after_move:%(filepath)s" "$OUTFILE_TMP" \
    -P "$OUTDIR" \
    "$URL"

log INFO "Fin téléchargement"

# Émettre le chemin du fichier produit (lu par la GUI)
if [ -s "$OUTFILE_TMP" ]; then
    RESULT="$(head -1 "$OUTFILE_TMP")"
    echo ""
    echo "OUTFILE:$RESULT"
else
    echo ""
    echo "[INFO] Fichier téléchargé dans : $OUTDIR"
fi
