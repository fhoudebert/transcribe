#!/usr/bin/env bash
# ==============================================================================
#  build_tk_xft.sh — recompile libtcl9tk9.0.so (Tk 9.0.4) AVEC Xft
#
#  Pourquoi : le Tk du Python portable (python-build-standalone) est compilé
#  sans Xft sous Linux : il ne voit que les polices bitmap X11 (« fixed »,
#  helvetica 75 dpi…), d'où une interface laide et sans accents lissés.
#  Problème connu en amont (astral-sh/python-build-standalone#740).
#  setup_python.sh remplace donc lib/libtcl9tk9.0.so du Python portable par
#  ce Tk, MÊME VERSION (9.0.4, celle de PBS 20261013), compilé avec Xft :
#  il utilise les polices du système via fontconfig, comme le Tk des
#  distributions.
#
#  Compilé avec zig cc en visant glibc 2.17 (comme PBS) : la bibliothèque
#  fonctionne sur toutes les distributions encore en service. Dépendances
#  ajoutées : libXft.so.2, libfontconfig.so.1, libX11.so.6 (présentes sur tout
#  bureau Linux ; PyInstaller les embarque de toute façon dans les binaires).
#
#  Usage : build_tk_xft.sh [x86_64|aarch64]   (défaut : architecture locale)
#  Résultat : ./<arch>/libtcl9tk9.0.so — une bibliothèque par architecture.
#  zig compile aussi pour l'autre architecture (compilation croisée) : il
#  suffit alors de fournir les bibliothèques X11/Xft/fontconfig/freetype de la
#  cible dans X_LIBDIR (par ex. extraites des paquets .deb arm64).
#
#  Prérequis (Debian/Ubuntu) : make git patchelf libxft-dev libfontconfig-dev
#  libx11-dev (pour les en-têtes), et pip (pour ziglang) ; en compilation
#  croisée vers arm64, aussi binutils-aarch64-linux-gnu (strip).
#  À refaire seulement si PBS_TAG change la version de Tk (install_tk_xft.sh
#  vérifie la version et n'installe ce Tk que si elle correspond), puis
#  reporter la somme affichée dans install_tk_xft.sh.
# ==============================================================================
set -Eeuo pipefail
TK_TAG="core-9-0-4"
ARCH="${1:-$(uname -m)}"
case "$ARCH" in
    x86_64)        ARCH=x86_64 ;;
    aarch64|arm64) ARCH=aarch64 ;;
    *) echo "architecture non prise en charge : $ARCH (x86_64, aarch64)" >&2; exit 2 ;;
esac
HOST="$ARCH-linux-gnu"
X_LIBDIR="${X_LIBDIR:-/usr/lib/$HOST}"     # bibliothèques X11 de la CIBLE
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/$ARCH/libtcl9tk9.0.so"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
cd "$W"

python3 -m pip install -q --target "$W/zig" ziglang
ZIG="$W/zig/ziglang/zig"
mkdir sysinc xlib
for d in X11 fontconfig freetype2 ft2build.h; do ln -s "/usr/include/$d" "sysinc/$d"; done
# Édition de liens : seuls les noms « .so » des bibliothèques d'exécution de
# la cible sont nécessaires (pas de paquet -dev de l'architecture cible).
for l in X11:6 Xft:2 fontconfig:1 freetype:6; do
    ln -s "$X_LIBDIR/lib${l%%:*}.so.${l##*:}" "xlib/lib${l%%:*}.so"
    [ -e "xlib/lib${l%%:*}.so" ] || { echo "absente : $X_LIBDIR/lib${l%%:*}.so.${l##*:}" >&2; exit 1; }
done
# Seuls les en-têtes X11/fontconfig/freetype du système sont vus : la libc
# vient de zig (glibc 2.17 de la cible), pas de /usr/include.
printf '#!/bin/sh\nexec %s cc -target %s.2.17 -idirafter %s/sysinc -idirafter %s/sysinc/freetype2 "$@"\n' "$ZIG" "$HOST" "$W" "$W" > zcc
printf '#!/bin/sh\nexec %s ar "$@"\n' "$ZIG" > zar
printf '#!/bin/sh\nexec %s ranlib "$@"\n' "$ZIG" > zranlib
chmod +x zcc zar zranlib
CROSS=()
[ "$ARCH" = "$(uname -m)" ] || CROSS=(--host="$HOST")

git clone -q --depth 1 --branch "$TK_TAG" https://github.com/tcltk/tcl.git tcl
git clone -q --depth 1 --branch "$TK_TAG" https://github.com/tcltk/tk.git tk

# Tcl : seuls tclConfig.sh et libtclstub.a servent (Tk se lie aux stubs).
(cd tcl/unix && CC="$W/zcc" AR="$W/zar" RANLIB="$W/zranlib" \
    ./configure ${CROSS[@]+"${CROSS[@]}"} --disable-zipfs >/dev/null \
 && make -j"$(nproc)" libtclstub.a >/dev/null)

(cd tk/unix && PKG_CONFIG=/bin/false CC="$W/zcc" AR="$W/zar" RANLIB="$W/zranlib" \
    ./configure ${CROSS[@]+"${CROSS[@]}"} --with-tcl="$W/tcl/unix" \
        --enable-xft --disable-xss --disable-zipfs \
        --x-includes="$W/sysinc" --x-libraries="$W/xlib" >/dev/null \
 && make -j"$(nproc)" libtcl9tk9.0.so >/dev/null)

mkdir -p "$(dirname "$OUT")"
cp tk/unix/libtcl9tk9.0.so "$OUT"
# strip de l'architecture CIBLE (paquet binutils-aarch64-linux-gnu pour une
# compilation croisée vers arm64 ; zig objcopy ne sait pas le faire)
STRIP=strip
[ "$ARCH" = "$(uname -m)" ] || STRIP="$HOST-strip"
"$STRIP" --strip-unneeded "$OUT"
patchelf --remove-rpath "$OUT"
patchelf --set-soname libtcl9tk9.0.so "$OUT"
readelf -d "$OUT" | grep -E "NEEDED|SONAME"
sha256sum "$OUT"
echo "→ reporter la somme dans TK_XFT_SHA256_${ARCH} de install_tk_xft.sh"
