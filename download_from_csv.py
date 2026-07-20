#!/usr/bin/env python3
"""
download_from_csv.py — Télécharge les composants listés dans downloads.csv
===========================================================================
Équivalent multiplateforme (stdlib uniquement) de download_from_csv.sh :
c'est le chemin utilisé sous WINDOWS (via setupPython_and_download.bat),
et il fonctionne à l'identique sous Linux/macOS.

Format d'une ligne : destination,url[,format]
  destination  chemin relatif à la racine de l'application (dossier du CSV)
  format       vide|auto → détection par extension ; zip ; tar.gz|tgz ;
               tar.bz2|tbz2 ; tar.xz|txz ; gz ; 7z|7zip ; no
Lignes vides et commentaires (#) ignorés. Un fichier déjà présent n'est
pas retéléchargé : relancer le script reprend une installation interrompue.

Usage : python download_from_csv.py [fichier.csv]      (défaut: downloads.csv)
"""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

UA = {"User-Agent": "transcribe-install/1.0"}


def detect_format(filename: str, fmt: str) -> str:
    if fmt and fmt != "auto":
        return fmt
    lower = filename.lower()
    for suffix, f in (
        (".zip", "zip"), (".7z", "7z"),
        (".tar.gz", "tar.gz"), (".tgz", "tar.gz"),
        (".tar.bz2", "tar.bz2"), (".tbz2", "tar.bz2"),
        (".tar.xz", "tar.xz"), (".txz", "tar.xz"),
        (".gz", "gz"),
    ):
        if lower.endswith(suffix):
            return f
    return "no"


def extract(archive: str, destdir: str, fmt: str) -> None:
    if fmt == "no":
        return
    if fmt == "zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(destdir)
        os.remove(archive)
    elif fmt in ("tar.gz", "tar.bz2", "tar.xz"):
        with tarfile.open(archive) as tf:
            tf.extractall(destdir)
        os.remove(archive)
    elif fmt == "gz":
        out = archive[:-3] if archive.lower().endswith(".gz") else archive + ".out"
        with gzip.open(archive, "rb") as src, open(out, "wb") as dst:
            shutil.copyfileobj(src, dst)
        os.remove(archive)
    elif fmt in ("7z", "7zip"):
        exe = shutil.which("7z") or shutil.which("7za")
        if exe:
            subprocess.run([exe, "x", "-y", f"-o{destdir}", archive],
                           check=True, stdout=subprocess.DEVNULL)
            os.remove(archive)
        else:
            print(f"  [AVERTISSEMENT] 7z non disponible, archive conservée : {archive}")
    else:
        print(f"  [AVERTISSEMENT] Format inconnu '{fmt}', archive conservée : {archive}")


def fetch(url: str, target: str) -> None:
    part = target + ".part"
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req) as resp, open(part, "wb") as out:
            shutil.copyfileobj(resp, out, length=1 << 20)
        os.replace(part, target)
    except BaseException:
        if os.path.exists(part):
            os.remove(part)
        raise


def main(argv: list[str]) -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = argv[1] if len(argv) > 1 else os.path.join(script_dir, "downloads.csv")
    if not os.path.isfile(csv_path):
        print(f"[ERREUR] Fichier introuvable : {csv_path}")
        return 1

    # Les destinations sont relatives à la racine de l'application, c'est-à-
    # dire au dossier du CSV (même convention que download-assistant et que
    # le repli shell Linux).
    base_dir = os.path.dirname(os.path.abspath(csv_path))

    n_ok = n_skip = n_fail = 0
    with open(csv_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            dest, url = parts[0], parts[1] if len(parts) > 1 else ""
            fmt = parts[2] if len(parts) > 2 else ""
            if not dest or not url:
                continue

            destdir = os.path.join(base_dir, *dest.split("/"))
            os.makedirs(destdir, exist_ok=True)
            filename = os.path.basename(url.split("?", 1)[0])
            target = os.path.join(destdir, filename)

            if os.path.exists(target):
                print(f"[skip] Déjà présent : {dest}/{filename}")
                n_skip += 1
                continue

            print(f"[get ] {url}")
            print(f"       → {dest}/")
            try:
                fetch(url, target)
                extract(target, destdir, detect_format(filename, fmt))
                n_ok += 1
            except Exception as exc:  # réseau, extraction…
                print(f"  [ÉCHEC] {type(exc).__name__}: {exc}")
                n_fail += 1

    print(f"\nTéléchargements : {n_ok} réussis, {n_skip} déjà présents, "
          f"{n_fail} échecs")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
