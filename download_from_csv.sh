#!/bin/bash
# ==============================================================================
#  download_from_csv.sh — Télécharge les composants listés dans downloads.csv
#
#  Repli 100 % shell du binaire download-assistant : mêmes fichier et format.
#
#  Format d'une ligne : destination,url[,format[,os[,move]]]
#    destination  chemin relatif à la racine de l'application (ex. build/dic)
#    url          URL à télécharger
#    format       vide|auto → détection par extension ; zip ; tar.gz|tgz ;
#                 tar.bz2|tbz2 ; tar.xz|txz ; gz ; 7z|7zip ; no (pas d'extraction)
#    os           linux | win | mac | all (défaut) : la ligne n'est traitée que
#                 si l'OS courant correspond. Surcharge : CSV_OS=win ./download…
#                 pour préparer une clé Windows depuis Linux (CSV_OS=all : tout).
#    move         opérations post-extraction séparées par « ; » :
#                   motif_glob         → déplace les correspondances à la racine
#                                        de la destination (aplatit l'enveloppe)
#                   motif->nouveau_nom → idem avec renommage (motif unique)
#                 Les fichiers déplacés reçoivent chmod +x, puis les dossiers
#                 vides restants sont supprimés.
#
#  Lignes vides et lignes commençant par # ignorées.
#  Un fichier déjà présent à destination n'est PAS retéléchargé ; pour les
#  archives (extraites puis supprimées), un marqueur .installed-<fichier>
#  mémorise l'installation (reprise d'installation : relancez simplement).
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

# ── OS cible (surcharge possible : CSV_OS=win|linux|mac|all) ──────────────────
CUR_OS="${CSV_OS:-}"
if [ -z "$CUR_OS" ]; then
    case "$(uname -s)" in
        Linux*)                 CUR_OS="linux" ;;
        Darwin*)                CUR_OS="mac"   ;;
        MINGW*|MSYS*|CYGWIN*)   CUR_OS="win"   ;;
        *)                      CUR_OS="linux" ;;
    esac
fi
echo "OS cible : $CUR_OS"

os_matches() {   # os_matches <tag>
    local t
    t="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
    case "$t" in
        ""|all|any)        return 0 ;;
        windows)           t="win" ;;
        macos|darwin)      t="mac" ;;
    esac
    [ "$CUR_OS" = "all" ] && return 0
    [ "$t" = "$CUR_OS" ]
}

apply_moves() {  # apply_moves <destdir> <movespec>
    local dest="$1" spec="$2" op pat new src dst rel
    [ -n "$spec" ] || return 0
    local ops=() wrappers=()
    IFS=';' read -r -a ops <<< "$spec"
    shopt -s nullglob
    for op in "${ops[@]}"; do
        op="$(printf '%s' "$op" | sed 's/^ *//; s/ *$//')"
        [ -n "$op" ] || continue
        pat="${op%%->*}"
        new=""
        [ "$op" != "$pat" ] && new="${op#*->}"
        pat="$(printf '%s' "$pat" | sed 's/ *$//')"
        new="$(printf '%s' "$new" | sed 's/^ *//')"
        local matches=( $dest/$pat )
        if [ ${#matches[@]} -eq 0 ]; then
            echo "  [AVERTISSEMENT] move '$pat' : aucune correspondance"
            continue
        fi
        for src in "${matches[@]}"; do
            # Premier segment du chemin relatif = enveloppe candidate
            rel="${src#"$dest"/}"
            wrappers+=( "$dest/${rel%%/*}" )
            if [ -n "$new" ] && [ ${#matches[@]} -eq 1 ]; then
                dst="$dest/$new"
            else
                dst="$dest/$(basename "$src")"
            fi
            if [ "$src" != "$dst" ]; then
                rm -rf "$dst"
                mv "$src" "$dst"
            fi
            if [ -f "$dst" ]; then
                chmod +x "$dst" 2>/dev/null || true
            fi
        done
    done
    shopt -u nullglob
    # Supprime les dossiers enveloppe (seulement s'ils sont des dossiers :
    # un fichier resté en place à la racine n'est jamais touché)
    local w
    for w in "${wrappers[@]}"; do
        if [ -d "$w" ]; then rm -rf "$w"; fi
    done
}

detect_format() {   # detect_format <fichier> <format_csv>  →  echo format effectif
    local f="$1" fmt="$2"
    if [ -z "$fmt" ] || [ "$fmt" = "auto" ]; then
        case "$f" in
            *.zip)              fmt="zip" ;;
            *.7z)               fmt="7z" ;;
            *.tar.gz|*.tgz)     fmt="tar.gz" ;;
            *.tar.bz2|*.tbz2)   fmt="tar.bz2" ;;
            *.tar.xz|*.txz)     fmt="tar.xz" ;;
            *.gz)               fmt="gz" ;;
            *)                  fmt="no" ;;
        esac
    fi
    printf '%s' "$fmt"
}

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
extract() {   # extract <archive> <destdir> <format_effectif>
    local archive="$1" dest="$2" fmt="$3"

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
    os_tag="$(printf '%s' "$line" | cut -d, -f4)"
    moves="$(printf '%s'  "$line" | cut -d, -f5)"
    [ -n "$dest" ] && [ -n "$url" ] || continue
    os_matches "$os_tag" || continue     # ligne destinée à un autre OS

    destdir="$BASE_DIR/$dest"
    mkdir -p "$destdir"

    filename="$(basename "${url%%\?*}")"
    target="$destdir/$filename"
    eff_fmt="$(detect_format "$filename" "$fmt")"
    # Les archives sont supprimées après extraction : un marqueur mémorise
    # l'installation (idem quand « move » renomme le fichier téléchargé).
    marker=""
    if [ "$eff_fmt" != "no" ] || [ -n "$moves" ]; then
        marker="$destdir/.installed-$filename"
    fi

    if { [ -n "$marker" ] && [ -f "$marker" ]; } || [ -f "$target" ]; then
        echo "⏭  Déjà présent : $dest/$filename"
        n_skip=$((n_skip + 1))
        continue
    fi

    echo "⬇️  $url"
    echo "    → $dest/"
    if fetch "$target.part" "$url"; then
        mv "$target.part" "$target"
        extract "$target" "$destdir" "$eff_fmt"
        if [ -n "$moves" ];  then apply_moves "$destdir" "$moves"; fi
        if [ -n "$marker" ]; then printf '%s\n' "$url" > "$marker"; fi
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
