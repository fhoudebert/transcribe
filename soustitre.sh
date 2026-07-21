#!/bin/bash
# ============================================================
#  soustitre.sh  —  Transcription audio -> SRT
#  Usage : soustitre.sh <fichier> [base|medium|large] [yes|no]
#    3e argument : yes = traduit vers anglais (defaut)
#                  no  = transcrit dans la langue detectee
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FFMPEG_BIN="$SCRIPT_DIR/build/ffmpeg/bin/ffmpeg"
WHISPER_DIR="$SCRIPT_DIR/build/whisper"
WHISPER_BIN="$WHISPER_DIR/whisper-cli"

INPUT="${1:-}"
MODEL_NAME="${2:-medium}"
TRANSLATE="${3:-yes}"   # yes = -tr (→ anglais)  |  no = langue détectée

MODEL="$WHISPER_DIR/models/ggml-${MODEL_NAME}.bin"

# ── Validations ─────────────────────────────────────────────
if [ -z "$INPUT" ]; then
    echo "Usage : soustitre.sh <fichier> [base|medium|large] [yes|no]"
    exit 1
fi
if [ ! -f "$INPUT" ];   then echo "[ERREUR] Fichier introuvable : $INPUT";   exit 1; fi
if [ ! -x "$FFMPEG_BIN" ]; then echo "[ERREUR] ffmpeg introuvable : $FFMPEG_BIN"; exit 1; fi
if [ ! -x "$WHISPER_BIN" ]; then echo "[ERREUR] whisper-cli introuvable : $WHISPER_BIN"; exit 1; fi
if [ ! -f "$MODEL" ];   then echo "[ERREUR] Modèle introuvable : $MODEL";    exit 1; fi

# ── Chemins de sortie ────────────────────────────────────────
DIR="$(cd "$(dirname "$INPUT")" && pwd)"
BASE_NAME="$(basename "${INPUT%.*}")"
BASE_FULL="$DIR/$BASE_NAME"

WAV_FILE="$BASE_FULL.wav"

if [ "$TRANSLATE" = "yes" ]; then
    SRT_OUT="$BASE_FULL.en.srt"
    LABEL="traduction vers anglais"
else
    SRT_OUT="$BASE_FULL.srt"
    LABEL="transcription langue détectée"
fi

echo "Fichier  : $INPUT"
echo "Modèle   : $MODEL_NAME"
echo "Mode     : $LABEL"

# ── 1. Extraction audio ──────────────────────────────────────
echo ""
echo "=== Extraction audio ==="
"$FFMPEG_BIN" -y \
  -i "$INPUT" \
  -ar 16000 \
  -ac 1 \
  -c:a pcm_s16le \
  "$WAV_FILE"

# ── 2. Whisper ───────────────────────────────────────────────
echo ""
echo "=== Whisper : $LABEL ==="

if [ "$TRANSLATE" = "yes" ]; then
    "$WHISPER_BIN" \
      -m "$MODEL" \
      -f "$WAV_FILE" \
      -tr \
      -osrt \
      -of "$DIR/output"
else
    "$WHISPER_BIN" \
      -m "$MODEL" \
      -f "$WAV_FILE" \
      -osrt \
      -of "$DIR/output"
fi

# Whisper génère toujours BASE_NAME.srt
# En mode traduction on le renomme .en.srt
if [ "$TRANSLATE" = "yes" ] && [ -f "$BASE_FULL.srt" ]; then
    mv "$BASE_FULL.srt" "$SRT_OUT"
fi

# ── 3. Nettoyage ─────────────────────────────────────────────
echo ""
echo "=== Nettoyage ==="
#rm -f "$WAV_FILE"

echo ""
echo "Sous-titres générés : $SRT_OUT"
