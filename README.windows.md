# Installation et compilation sous Windows

La clé (exFAT recommandé) est **bi-OS** : les deux systèmes cohabitent.

| Partagé entre Linux et Windows | Propre à chaque OS |
|---|---|
| paquets Argos (`build/argos-data/`), modèles Whisper, dictionnaires (`build/dic/`), `assets/`, `i18n/` | venv : `build/python/venv` (Linux) / `build\python\venv-windows` (Windows) ; binaires : `truchement` / `truchement.exe` |

## Prérequis (une fois par machine Windows servant au setup/compilation)

Installer **Python 3.12** depuis <https://www.python.org/downloads/> en
laissant cochés le lanceur `py` et tcl/tk. Les machines qui ne font
qu'*utiliser* `truchement.exe` compilé n'ont pas besoin de Python : le
binaire embarque son interpréteur et la stdlib complète.

**Sur toute machine utilisant transcribe** (même sans Python) : le
runtime **Visual C++ x64** de Microsoft doit être présent —
`whisper-cli.exe` et ses DLL (`ggml*.dll`) dépendent de `MSVCP140.dll`,
`VCRUNTIME140*.dll` et `VCOMP140.dll`. S'il manque, whisper échoue avec
le code 3221225781 (0xC0000135, « DLL introuvable »). Installation en un
clic : <https://aka.ms/vc/17/release/vc_redist.x64.exe> (souvent déjà
présent, apporté par d'autres logiciels).

## 1. Setup — `setupPython_and_download.bat`

Double-clic (ou depuis un terminal) à la racine de la clé :
crée `build\python\venv-windows` en mode `--copies` (aucun lien symbolique,
compatible exFAT), installe les dépendances, installe les paquets de
langues Argos **directement sur la clé** (partagés avec Linux : si le setup
Linux les a déjà téléchargés, cette étape ne refait rien), puis télécharge
modèles Whisper et dictionnaires (`downloads.csv`) via
`download-assistant.exe` s'il est présent, sinon `download_from_csv.py`.
Relançable sans risque après interruption.

## 2. Compilation — `compiler_truchement.bat`

Compile avec PyInstaller via `compile_app.py` (stdlib complète embarquée —
indispensable car argostranslate est chargé depuis le venv à l'exécution),
puis dépose à la racine : `truchement.exe`, `assets\` fusionnés, `i18n\`
(préférence de langue `.locale` préservée). `compiler_transcribe.bat` et
`compiler.bat` existent aussi.

Note icône : sous Windows, PyInstaller exige un `.ico` (ou Pillow installé
pour convertir le `.png`) ; à défaut l'option est simplement omise.

## 3. Test

```bat
truchement.exe
```
Traduire un texte (ex. français → indonésien) ; premier lancement : le
préchauffage tourne en arrière-plan, la barre d'état affiche « Moteur de
traduction prêt ». L'onglet Définition doit lister les dictionnaires de
`build\dic\`. En cas de souci, le bouton *Diagnostic* de l'application
indique précisément le venv et les chemins inspectés (il vise
`venv-windows` sous Windows).
