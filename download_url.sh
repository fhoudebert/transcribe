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
#
#  Options facultatives, transmises par la GUI en variables d'environnement
#  (absentes : comportement historique, une seule piste audio, pas de
#  sous-titres) :
#    TRANSCRIBE_DL_SUBS      langues de sous-titres, séparées par des virgules
#                            → fichiers « <video>.<langue>.srt » à côté de la
#                            vidéo (jamais incrustés : un SRT vide ferait
#                            échouer tout le post-traitement yt-dlp)
#    TRANSCRIBE_DL_AUTOSUBS  1 = au moins une de ces langues est un sous-titre
#                            généré automatiquement
#    TRANSCRIBE_DL_AUDIO     langues audio à fusionner (2 ou plus), séparées
#                            par des virgules, dans l'ordre des pistes voulu.
#                            Le conteneur reste mp4.
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

# ── Options facultatives (voir l'en-tête) ─────────────────────────────────────
FMT='bv*[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/bv*+ba/best[ext=mp4]/best'
EXTRA=()

# Un code de langue est inséré dans un sélecteur yt-dlp : on refuse tout
# caractère inattendu plutôt que de le transmettre.
valid_langs() {  # valid_langs "fr,de" → écrit les codes valides, un par ligne
    local l
    IFS=',' read -r -a _L <<< "$1"
    for l in "${_L[@]}"; do
        if [[ "$l" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
            printf '%s\n' "$l"
        else
            echo "[AVERTISSEMENT] code de langue ignoré : $l" >&2
        fi
    done
}

AUDIO_LANGS=()
if [ -n "${TRANSCRIBE_DL_AUDIO:-}" ]; then
    while IFS= read -r l; do AUDIO_LANGS+=("$l"); done \
        < <(valid_langs "$TRANSCRIBE_DL_AUDIO")
fi
if [ "${#AUDIO_LANGS[@]}" -ge 2 ]; then
    A_M4A=""; A_ANY=""
    for l in "${AUDIO_LANGS[@]}"; do
        A_M4A+="+ba[language=$l][ext=m4a]"
        A_ANY+="+ba[language=$l]"
    done
    # Repli sur la sélection historique si aucun format ne correspond
    FMT="bv*[ext=mp4][vcodec^=avc1]${A_M4A}/bv*${A_ANY}/${FMT}"
    EXTRA+=(--audio-multistreams)
    echo "Pistes audio : ${AUDIO_LANGS[*]}"
fi

SUBS_LANGS=()
if [ -n "${TRANSCRIBE_DL_SUBS:-}" ]; then
    while IFS= read -r l; do SUBS_LANGS+=("$l"); done \
        < <(valid_langs "$TRANSCRIBE_DL_SUBS")
fi
if [ "${#SUBS_LANGS[@]}" -ge 1 ]; then
    SUBS_CSV="$(IFS=,; echo "${SUBS_LANGS[*]}")"
    EXTRA+=(--write-subs --sub-langs "$SUBS_CSV" --convert-subs srt)
    if [ "${TRANSCRIBE_DL_AUTOSUBS:-}" = "1" ]; then
        EXTRA+=(--write-auto-subs)
    else
        EXTRA+=(--no-write-auto-subs)
    fi
    echo "Sous-titres : $SUBS_CSV"
else
    EXTRA+=(--no-write-auto-subs)
fi

# --xattrs (URL d'origine dans les attributs étendus) : seulement si le
# dossier de destination les supporte — sinon (clé USB exFAT/FAT/NTFS,
# partage réseau…) yt-dlp échoue en fin de traitement avec « This filesystem
# doesn't support extended attributes » alors que la vidéo est complète.
# Options demandées : on retélécharge même si le fichier existe déjà, sinon
# yt-dlp saute la vidéo (« already been downloaded ») et garde l'ancienne
# version — sans les pistes audio / sous-titres demandés.
if [ "${#AUDIO_LANGS[@]}" -ge 2 ] || [ "${#SUBS_LANGS[@]}" -ge 1 ]; then
    EXTRA+=(--force-overwrites)
fi

XATTR_FLAG=()
_xt="$OUTDIR/.xattr_test.$$"
if command -v setfattr >/dev/null 2>&1 && : > "$_xt" 2>/dev/null \
   && setfattr -n user.test -v 1 "$_xt" 2>/dev/null; then
    XATTR_FLAG=(--xattrs)
fi
rm -f "$_xt" 2>/dev/null

CMD=( "$YTDLP" \
    -f "$FMT" \
    -S "vcodec:h264,lang,quality,res,fps,hdr:12,acodec:aac" \
    --merge-output-format mp4 \
    --remux-video mp4 \
    --restrict-filenames \
    ${EXTRA[@]+"${EXTRA[@]}"} \
    --embed-thumbnail \
    -o "%(title).80s [%(id)s].%(ext)s" \
    --restrict-filenames \
    --embed-chapters \
    ${XATTR_FLAG[@]+"${XATTR_FLAG[@]}"} \
    --newline \
    --progress \
    --print-to-file "after_move:%(filepath)s" "$OUTFILE_TMP" \
    -P "$OUTDIR" \
    "$URL" )

# Commande réellement lancée (affichée dans le journal de l'IHM)
echo "Commande :"
printf '  %q' "${CMD[@]}"; echo
echo ""
"${CMD[@]}"

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
