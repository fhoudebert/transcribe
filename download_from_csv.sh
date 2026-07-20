#!/bin/bash
# ==============================================================================
#  download_from_csv.sh — Télécharge les composants listés dans downloads.csv
#
#  Repli 100 % shell du binaire download-assistant : mêmes fichier et format.
#
#  Format d'une ligne : destination,url[,format]
#    destination  chemin relatif à la racine de l'application (ex. build/dic)
#    url          URL à télécharger
#    format       vide|auto → détection par extension ; zip ; tar.gz|tgz ;
#                 tar.bz2|tbz2 ; tar.xz|txz ; gz ; 7z|7zip ; no (pas d'extraction)
#
#  Lignes vides et lignes commençant par # ignorées.
#  Un fichier déjà présent à destination n'est PAS retéléchargé (reprise
#  d'installation interrompue : relancez simplement le script).
#
#  Usage : download_from_csv.sh [fichier.csv]        (défaut : downloads.csv)
# ==============================================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSV="${1:-$SCRIPT_DIR/downloads.csv}"

if [ ! -f "$CSV" ]; then
    echo "[ERREUR] Fichier introuvable : $CSV"
    exit 1
fi

# Les destinations du CSV sont relatives à la racine de l'application,
# c'est-à-dire au dossier où se trouve le CSV (identique au comportement
# de download-assistant).
BASE_DIR="$(cd "$(dirname "$CSV")" && pwd)"

# ── Outil de téléchargement ───────────────────────────────────────────────────
if command -v curl >/dev/null 2>&1; then
    fetch() { curl -fL --retry 3 -o "$1" "$2"; }
elif command -v wget >/dev/null 2>&1; then
    fetch() { wget -O "$1" "$2"; }
else
    echo "[ERREUR] Ni curl ni wget disponibles."
    exit 1
fi

# ── Extraction ────────────────────────────────────────────────────────────────
extract() {   # extract <archive> <destdir> <format>
    local archive="$1" dest="$2" fmt="$3"

    if [ -z "$fmt" ] || [ "$fmt" = "auto" ]; then
        case "$archive" in
            *.zip)              fmt="zip" ;;
            *.7z)               fmt="7z" ;;
            *.tar.gz|*.tgz)     fmt="tar.gz" ;;
            *.tar.bz2|*.tbz2)   fmt="tar.bz2" ;;
            *.tar.xz|*.txz)     fmt="tar.xz" ;;
            *.gz)               fmt="gz" ;;
            *)                  fmt="no" ;;
        esac
    fi

    case "$fmt" in
        no) return 0 ;;
        zip)
            if command -v unzip >/dev/null 2>&1; then
                unzip -o -q "$archive" -d "$dest"
            else
                python3 -c "import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
                    "$archive" "$dest"
            fi
            rm -f "$archive" ;;
        tar.gz|tgz)   tar -xzf "$archive" -C "$dest" && rm -f "$archive" ;;
        tar.bz2|tbz2) tar -xjf "$archive" -C "$dest" && rm -f "$archive" ;;
        tar.xz|txz)   tar -xJf "$archive" -C "$dest" && rm -f "$archive" ;;
        gz)           gunzip -f "$archive" ;;
        7z|7zip)
            if command -v 7z >/dev/null 2>&1; then
                7z x -y -o"$dest" "$archive" >/dev/null && rm -f "$archive"
            else
                echo "  [AVERTISSEMENT] 7z non disponible, archive conservée : $archive"
            fi ;;
        *)
            echo "  [AVERTISSEMENT] Format inconnu '$fmt', archive conservée : $archive" ;;
    esac
}

# ── Boucle principale ─────────────────────────────────────────────────────────
n_ok=0; n_skip=0; n_fail=0

while IFS= read -r line || [ -n "$line" ]; do
    # Nettoyage : retours chariot Windows, espaces/tabulations de fin
    line="${line%$'\r'}"
    line="$(printf '%s' "$line" | sed 's/[[:space:]]*$//')"
    case "$line" in ''|\#*) continue ;; esac

    dest="$(printf '%s' "$line" | cut -d, -f1)"
    url="$(printf '%s'  "$line" | cut -d, -f2)"
    fmt="$(printf '%s'  "$line" | cut -d, -f3)"
    [ -n "$dest" ] && [ -n "$url" ] || continue

    destdir="$BASE_DIR/$dest"
    mkdir -p "$destdir"

    filename="$(basename "${url%%\?*}")"
    target="$destdir/$filename"

    if [ -f "$target" ]; then
        echo "⏭  Déjà présent : $dest/$filename"
        n_skip=$((n_skip + 1))
        continue
    fi

    echo "⬇️  $url"
    echo "    → $dest/"
    if fetch "$target.part" "$url"; then
        mv "$target.part" "$target"
        extract "$target" "$destdir" "$fmt"
        n_ok=$((n_ok + 1))
    else
        rm -f "$target.part"
        echo "  [ÉCHEC] $url"
        n_fail=$((n_fail + 1))
    fi
done < "$CSV"

echo ""
echo "📊 Téléchargements : $n_ok réussis, $n_skip déjà présents, $n_fail échecs"
[ "$n_fail" -eq 0 ]
