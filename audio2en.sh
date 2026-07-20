#!/bin/bash
# ==============================================================
#  audio2en.sh  —  Transcription audio → texte brut (.txt)
#  Usage : audio2en.sh <fichier> [base|medium|large] [langue]
#
#    langue : code ISO 639-1 passé à whisper via -l
#             ex: fr, en, de, es, zh…
#             Défaut : auto-détection (omis = whisper détecte)
#
#  Pas de -tr : la langue source est conservée telle quelle.
#  Le MP3 est accepté directement par whisper-cli.
#
#  Arborescence attendue (relative au script) :
#    build/ffmpeg/bin/ffmpeg
#    build/whisper/whisper-cli
#    build/whisper/models/ggml-<model>.bin
# ==============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FFMPEG_BIN="$SCRIPT_DIR/build/ffmpeg/bin/ffmpeg"
WHISPER_DIR="$SCRIPT_DIR/build/whisper"
WHISPER_BIN="$WHISPER_DIR/whisper-cli"

INPUT="${1:-}"
MODEL_NAME="${2:-medium}"
LANG="${3:-}"           # vide = auto-détection whisper

MODEL="$WHISPER_DIR/models/ggml-${MODEL_NAME}.bin"

# ── Validations ────────────────────────────────────────────────
if [ -z "$INPUT" ]; then
    echo "Usage : audio2en.sh <fichier> [base|medium|large] [langue]"
    exit 1
fi
if [ ! -f "$INPUT" ];      then echo "[ERREUR] Fichier introuvable : $INPUT";    exit 1; fi
if [ ! -x "$WHISPER_BIN" ]; then echo "[ERREUR] whisper-cli introuvable : $WHISPER_BIN"; exit 1; fi
if [ ! -f "$MODEL" ];      then echo "[ERREUR] Modèle introuvable : $MODEL";     exit 1; fi

# ── Chemins de sortie ──────────────────────────────────────────
DIR="$(cd "$(dirname "$INPUT")" && pwd)"
BASE_NAME="$(basename "${INPUT%.*}")"
BASE_FULL="$DIR/$BASE_NAME"
TXT_FILE="$BASE_FULL.txt"

if [ -n "$LANG" ]; then
    echo "Fichier  : $INPUT"
    echo "Modèle   : $MODEL_NAME"
    echo "Langue   : $LANG  (-l $LANG)"
    LANG_ARGS=(-l "$LANG")
else
    echo "Fichier  : $INPUT"
    echo "Modèle   : $MODEL_NAME"
    echo "Langue   : auto-détection"
    LANG_ARGS=()
fi

# ── Conversion WAV 16 kHz mono ─────────────────────────────────
# whisper-cli accepte le MP3 directement mais une conversion
# explicite en WAV 16kHz mono garantit la meilleure précision.
WAV_FILE="$BASE_FULL.__audio2en__.wav"

echo ""
echo "=== Conversion audio → WAV 16kHz mono ==="
"$FFMPEG_BIN" -y \
    -i "$INPUT" \
    -ar 16000 \
    -ac 1 \
    -c:a pcm_s16le \
    "$WAV_FILE"

# ── Transcription Whisper → .txt ───────────────────────────────
echo ""
echo "=== Transcription Whisper (texte brut, sans traduction) ==="
"$WHISPER_BIN" \
    -m "$MODEL" \
    -f "$WAV_FILE" \
    "${LANG_ARGS[@]}" \
    -otxt \
    -of "$BASE_FULL"
# Pas de -tr → langue source conservée

# ── Nettoyage ─────────────────────────────────────────────────
rm -f "$WAV_FILE"

if [ ! -f "$TXT_FILE" ]; then
    echo "[ERREUR] Fichier texte non généré : $TXT_FILE"
    exit 1
fi

echo ""
echo "=== Terminé ==="
echo "Transcription : $TXT_FILE"
