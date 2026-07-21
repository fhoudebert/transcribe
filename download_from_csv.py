#!/usr/bin/env python3
"""
download_from_csv.py — Télécharge les composants listés dans downloads.csv
===========================================================================
Équivalent multiplateforme (stdlib uniquement) de download_from_csv.sh :
c'est le chemin utilisé sous WINDOWS (via setupPython_and_download.bat),
et il fonctionne à l'identique sous Linux/macOS.

Format d'une ligne : destination,url[,format[,os[,move]]]
  destination  chemin relatif à la racine de l'application (dossier du CSV)
  format       vide|auto → détection par extension ; zip ; tar.gz|tgz ;
               tar.bz2|tbz2 ; tar.xz|txz ; gz ; 7z|7zip ; no
  os           linux | win | mac | all (défaut) → la ligne n'est traitée
               que si l'OS courant correspond. Surcharge possible via la
               variable d'environnement CSV_OS (ex. CSV_OS=win pour préparer
               une clé Windows depuis Linux ; CSV_OS=all pour tout traiter).
  move         opérations post-extraction, séparées par « ; » :
               motif_glob        → déplace les fichiers correspondants à la
                                   racine de la destination (aplatit les
                                   dossiers enveloppe des archives)
               motif->nouveau_nom→ idem avec renommage (motif unique)
               Les fichiers déplacés reçoivent le bit exécutable (POSIX),
               puis les dossiers vides restants sont supprimés.
Lignes vides et commentaires (#) ignorés. Un fichier déjà présent n'est
pas retéléchargé ; pour les archives (extraites puis supprimées), un
marqueur .installed-<fichier> mémorise l'installation : relancer le
script reprend une installation interrompue sans rien retélécharger.

Usage : python download_from_csv.py [fichier.csv]      (défaut: downloads.csv)
"""

from __future__ import annotations

import glob
import gzip
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

UA = {"User-Agent": "transcribe-install/1.0"}


def current_os() -> str:
    """OS effectif : CSV_OS si défini, sinon la plateforme courante."""
    override = os.environ.get("CSV_OS", "").strip().lower()
    if override:
        return override
    if sys.platform.startswith("win"):
        return "win"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def os_matches(tag: str, cur: str) -> bool:
    t = (tag or "").strip().lower()
    if not t or t in ("all", "any") or cur == "all":
        return True
    if t == "windows":
        t = "win"
    if t in ("macos", "darwin"):
        t = "mac"
    return t == cur


def apply_moves(destdir: str, spec: str) -> None:
    """Applique les opérations « move » : motif[->nouveau_nom] ; …"""
    wrappers: set[str] = set()   # dossiers enveloppe à supprimer à la fin
    for op in filter(None, (o.strip() for o in spec.split(";"))):
        pat, _, newname = op.partition("->")
        pat, newname = pat.strip(), newname.strip()
        matches = glob.glob(os.path.join(destdir, *pat.split("/")))
        if not matches:
            print(f"  [AVERTISSEMENT] move '{pat}' : aucune correspondance")
            continue
        for src in matches:
            # Premier segment du chemin relatif = enveloppe candidate
            rel = os.path.relpath(src, destdir)
            wrappers.add(os.path.join(destdir, rel.split(os.sep)[0]))
            name = newname if (newname and len(matches) == 1) \
                   else os.path.basename(src)
            dst = os.path.join(destdir, name)
            if os.path.abspath(src) != os.path.abspath(dst):
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                elif os.path.exists(dst):
                    os.remove(dst)
                shutil.move(src, dst)
            if os.name == "posix" and os.path.isfile(dst):
                os.chmod(dst, os.stat(dst).st_mode | 0o755)
    # Supprime les dossiers enveloppe (seulement s'ils sont des dossiers :
    # un fichier resté en place à la racine n'est jamais touché)
    for w in wrappers:
        if os.path.isdir(w):
            shutil.rmtree(w, ignore_errors=True)


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
            for info in zf.infolist():
                zf.extract(info, destdir)
                if os.name == "posix":
                    mode = info.external_attr >> 16
                    if mode:
                        os.chmod(os.path.join(destdir, info.filename), mode)
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
    cur_os   = current_os()
    print(f"OS cible : {cur_os}")

    n_ok = n_skip = n_fail = 0
    with open(csv_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            dest, url = parts[0], parts[1] if len(parts) > 1 else ""
            fmt    = parts[2] if len(parts) > 2 else ""
            os_tag = parts[3] if len(parts) > 3 else ""
            moves  = parts[4] if len(parts) > 4 else ""
            if not dest or not url:
                continue
            if not os_matches(os_tag, cur_os):
                continue          # ligne destinée à un autre OS

            destdir = os.path.join(base_dir, *dest.split("/"))
            os.makedirs(destdir, exist_ok=True)
            filename = os.path.basename(url.split("?", 1)[0])
            target = os.path.join(destdir, filename)
            eff_fmt = detect_format(filename, fmt)
            # Les archives sont supprimées après extraction : un marqueur
            # mémorise l'installation pour ne pas retélécharger au prochain
            # lancement. Idem quand « move » renomme le fichier téléchargé.
            marker = (os.path.join(destdir, f".installed-{filename}")
                      if (eff_fmt != "no" or moves) else "")

            if (marker and os.path.exists(marker)) or os.path.exists(target):
                print(f"[skip] Déjà présent : {dest}/{filename}")
                n_skip += 1
                continue

            print(f"[get ] {url}")
            print(f"       → {dest}/")
            try:
                fetch(url, target)
                extract(target, destdir, eff_fmt)
                if moves:
                    apply_moves(destdir, moves)
                if marker:
                    with open(marker, "w", encoding="utf-8") as mk:
                        mk.write(url + "\n")
                n_ok += 1
            except Exception as exc:  # réseau, extraction…
                print(f"  [ÉCHEC] {type(exc).__name__}: {exc}")
                n_fail += 1

    print(f"\nTéléchargements : {n_ok} réussis, {n_skip} déjà présents, "
          f"{n_fail} échecs")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
