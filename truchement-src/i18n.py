"""
i18n.py — Catalogue de chaînes de l'interface
===============================================
Toutes les chaînes localisées (en, fr, de, es) sont regroupées
dans I18N.  detect_ui_lang() détecte la locale système.

Pour ajouter une langue :
    1. Ajouter une entrée I18N["xx"] = { … }  (copier "en" comme base)
    2. L'entrée apparaîtra automatiquement dans le menu Interface.
"""

from __future__ import annotations

import locale

# ═══════════════════════════════════════════════════════════════════════════════
# CATALOGUE
# ═══════════════════════════════════════════════════════════════════════════════

I18N: dict[str, dict[str, str]] = {
    "en": {
        "via_pivot": "· via English",
        "engine_ready": "Translation engine ready.",
        "title": "Dictionary",
        "subtitle": "Translate texts and define words",
        "source_lang": "Source Language",
        "target_lang": "Target Language",
        "source_text": "Source Text",
        "target_text": "Translation",
        "translate_btn": "Translate  →",
        "clear_btn": "Clear",
        "swap_btn": "⇄  Swap Languages",
        "translating": "Translating…",
        "translating_elapsed": "Translating… {sec}s",
        "translating_slow": "Still working… loading the model can take a while on first use ({sec}s)",
        "translating_timeout_soon": "This is taking unusually long ({sec}s) — please keep waiting",
        "no_text": "Please enter text to translate.",
        "error_title": "Error",
        "error_pkg": (
            "argostranslate is not installed or no packages loaded.\n\n"
            "Install with: pip install argostranslate"
        ),
        "error_trans": "Translation failed:\n{err}",
        "error_no_pkg": (
            "No translation package for {src} → {tgt}.\n\n"
            "Install it via argospm or the GUI."
        ),
        "select_langs": "Please select both source and target languages.",
        "copied": "Translation copied to clipboard.",
        "copy_btn": "⎘ Copy",
        "char_count": "{n} chars",
        "ui_lang": "Interface",
        "tab1": "Text 1",
        "tab2": "Text 2",
        "tab3": "File",
        "tab4": "Definition",
        # ── onglet Fichier
        "file_tab_title": "File Translation",
        "file_pick_btn": "📂  Choose file…",
        "file_dir_label": "Folder:",
        "file_translate_btn": "Translate file  →",
        "file_translating": "Translating file…",
        "file_translating_elapsed": "Translating file… {sec}s",
        "file_translating_slow": "Still working… large files or first-time model loading can take a while ({sec}s)",
        "file_translating_timeout_soon": "This is taking unusually long ({sec}s) — please keep waiting",
        "file_no_file": "Please choose a file to translate.",
        "file_label": "Source file",
        "file_none": "No file selected",
        "file_out_label": "Output file",
        "file_success": "File translated: {path}",
        "file_open_btn": "📁  Open folder",
        "file_formats": "Supported: .txt  .html  .srt  .docx  .pdf",
        # ── serveur llama.cpp local (⚙, Texte 2)
        "llm_title": "Local llama.cpp server",
        "llm_hint": "Used by the Book tab and, when its “Local server” box is ticked, by Text 2 (passes and block size are those of the Book tab).",
        "llm_close": "Close",
        "llm_check": "Local server",
        "llm_translating": "Translating with the local server…",
        "llm_translating_elapsed": "Translating with the local server… {sec}s",
        "llm_error": "Local server: {err}",
        # ── onglet Livre
        "book_pause_btn": "⏸  Pause",
        "book_pausing": "Pause requested — finishing the current block…",
        "book_paused": "⏸ Paused at {pct} % — resume at any time, even after restarting the computer.",
        "book_resume_btn": "Resume translation  →",
        "book_job_paused": "⏸ Translation paused: {pct} % ({done}/{total} blocks) · started {created} · last activity {updated}",
        "book_job_interrupted": "⏸ Translation interrupted (computer shut down?): {pct} % ({done}/{total} blocks) · started {created} · last activity {updated}",
        "book_job_error": "✖ Translation stopped on an error at {pct} % ({done}/{total} blocks) — check the server, then resume",
        "book_job_running": "▶ This book is being translated in another window",
        "book_job_done": "✔ Already translated ({updated}): {out}",
        "book_partial": "preview: {name}",
        "book_close_running": "A book translation is running.\n\nYes: pause it (at the end of the current block), then close.\nNo: stop it now (the current block will be redone on resume).\nCancel: don't close.",
        "tab5": "Book",
        "book_title": "Book translation",
        "book_formats": "EPUB → EPUB · PDF → Markdown · TXT → TXT — local llama.cpp server, multi-pass, resumable",
        "book_pick_btn": "📂  Choose a book…",
        "book_none": "No book selected",
        "book_server": "llama.cpp server",
        "book_test_btn": "Test",
        "book_testing": "Testing…",
        "book_server_ok": "✔ {model} · context {ctx}",
        "book_server_ko": "✖ unreachable: {err}",
        "book_langs": "Languages",
        "book_passes": "Passes",
        "book_passes_1": "1 — translation",
        "book_passes_2": "2 — + bilingual revision",
        "book_passes_3": "3 — + final proofreading",
        "book_chunk": "Block size (chars)",
        "book_model": "Model (optional)",
        "book_glossary": "Glossary",
        "book_glossary_hint": "optional · one “term = translation” per line",
        "book_translate_btn": "Translate book  →",
        "book_trial_btn": "Trial ({n} blocks)",
        "book_stop_btn": "■  Stop",
        "book_open_btn": "📁  Open folder",
        "book_progress": "{done}/{total} blocks · {pct} % · elapsed {elapsed} · remaining ~{eta}",
        "book_no_file": "Please choose a book (EPUB, PDF or TXT).",
        "book_no_script": "traduire-livre.py was not found next to the application.",
        "book_running": "A book translation is already running.",
        "book_done": "Book translated: {path}",
        "book_stopped": "Stopped — run again to resume where it left off.",
        "book_failed": "Book translation interrupted (code {rc}) — see the log. Run again to resume.",
        "error_file_pkg": (
            "argostranslatefiles is not installed.\n\n"
            "Install with: pip install argostranslatefiles"
        ),
        "error_file_trans": "File translation failed:\n{err}",
        # ── popup / bouton Définir
        "define_btn": "📖 Define",
        "define_title": "Definition",
        "define_no_dic": (
            "No dictionary available for '{lang}'.\n\n"
            "Expected: build/dic/{code}-{code}.db\n"
            "(FTS5 table: entries_fts(lemma, definition))"
        ),
        "define_not_found": "No definition found for \u201c{word}\u201d.",
        "define_select": "Select a word first, then click Define.",
        "define_error": "Dictionary error:\n{err}",
        "define_from": "Dictionary: {lang}",
        # ── onglet Définition
        "def_tab_title": "Full-text Dictionary Search",
        "def_lang_label": "Dictionary",
        "def_search_btn": "Containing",
        "def_btn_prefix": "Starting with",
        "def_btn_exact":  "Definition",
        "def_searching": "Searching…",
        "def_results_n": "{n} result(s) for \u00ab{word}\u00bb",
        "def_no_results": "No results for \u00ab{word}\u00bb.",
        "def_no_dic_tab": (
            "No dictionary for '{lang}'.\n"
            "Expected: build/dic/{code}-{code}.db"
        ),
        "def_db_error": "Database error:\n{err}",
        "def_hint": "Type a word, then click Containing, Starting with or Definition.",
        "def_close": "✕  Close",
        "def_refresh": "↺",
        "about_description": "Truchement allows you to translate texts and files and to look up definitions in monolingual dictionaries.",
    },
    "fr": {
        "via_pivot": "· via l'anglais",
        "engine_ready": "Moteur de traduction prêt.",
        "title": "Truchement",
        "subtitle": "Traduire des textes et définir des mots",
        "source_lang": "Langue source",
        "target_lang": "Langue cible",
        "source_text": "Texte source",
        "target_text": "Traduction",
        "translate_btn": "Traduire  →",
        "clear_btn": "Effacer",
        "swap_btn": "⇄  Inverser",
        "translating": "Traduction…",
        "translating_elapsed": "Traduction… {sec}s",
        "translating_slow": "Toujours en cours… le premier chargement du modèle peut prendre du temps ({sec}s)",
        "translating_timeout_soon": "C'est inhabituellement long ({sec}s) — merci de patienter",
        "no_text": "Veuillez saisir un texte.",
        "error_title": "Erreur",
        "error_pkg": (
            "argostranslate n'est pas installé ou aucun paquet chargé.\n\n"
            "Installez via : pip install argostranslate"
        ),
        "error_trans": "Échec :\n{err}",
        "error_no_pkg": (
            "Aucun paquet pour {src} → {tgt}.\n\n"
            "Installez-le via argospm ou l'interface."
        ),
        "select_langs": "Sélectionnez les langues source et cible.",
        "copied": "Traduction copiée.",
        "copy_btn": "⎘ Copier",
        "char_count": "{n} car.",
        "ui_lang": "Interface",
        "tab1": "Texte 1",
        "tab2": "Texte 2",
        "tab3": "Fichier",
        "tab4": "Définition",
        "file_tab_title": "Traduction de fichier",
        "file_pick_btn": "📂  Choisir un fichier…",
        "file_dir_label": "Dossier :",
        "file_translate_btn": "Traduire le fichier  →",
        "file_translating": "Traduction du fichier…",
        "file_translating_elapsed": "Traduction du fichier… {sec}s",
        "file_translating_slow": "Toujours en cours… les fichiers volumineux ou le premier chargement du modèle peuvent prendre du temps ({sec}s)",
        "file_translating_timeout_soon": "C'est inhabituellement long ({sec}s) — merci de patienter",
        "file_no_file": "Veuillez choisir un fichier.",
        "file_label": "Fichier source",
        "file_none": "Aucun fichier sélectionné",
        "file_out_label": "Fichier de sortie",
        "file_success": "Fichier traduit : {path}",
        "file_open_btn": "📁  Ouvrir le dossier",
        "file_formats": "Formats : .txt  .html  .srt  .docx  .pdf",
        # ── serveur llama.cpp local (⚙, Texte 2)
        "llm_title": "Serveur llama.cpp local",
        "llm_hint": "Utilisé par l'onglet Livre et, si sa case « Serveur local » est cochée, par Texte 2 (passes et taille des blocs : celles de l'onglet Livre).",
        "llm_close": "Fermer",
        "llm_check": "Serveur local",
        "llm_translating": "Traduction par le serveur local…",
        "llm_translating_elapsed": "Traduction par le serveur local… {sec}s",
        "llm_error": "Serveur local : {err}",
        # ── onglet Livre
        "book_pause_btn": "⏸  Pause",
        "book_pausing": "Pause demandée — fin du bloc en cours…",
        "book_paused": "⏸ En pause à {pct} % — reprise possible à tout moment, même après un redémarrage de l'ordinateur.",
        "book_resume_btn": "Reprendre la traduction  →",
        "book_job_paused": "⏸ Traduction en pause : {pct} % ({done}/{total} blocs) · commencée le {created} · dernière activité {updated}",
        "book_job_interrupted": "⏸ Traduction interrompue (arrêt de l'ordinateur ?) : {pct} % ({done}/{total} blocs) · commencée le {created} · dernière activité {updated}",
        "book_job_error": "✖ Traduction arrêtée sur une erreur à {pct} % ({done}/{total} blocs) — vérifiez le serveur puis reprenez",
        "book_job_running": "▶ Ce livre est en cours de traduction dans une autre fenêtre",
        "book_job_done": "✔ Déjà traduit ({updated}) : {out}",
        "book_partial": "aperçu : {name}",
        "book_close_running": "Une traduction de livre est en cours.\n\nOui : la mettre en pause (à la fin du bloc en cours) puis fermer.\nNon : l'arrêter tout de suite (le bloc en cours sera refait à la reprise).\nAnnuler : ne pas fermer.",
        "tab5": "Livre",
        "book_title": "Traduction de livre",
        "book_formats": "EPUB → EPUB · PDF → Markdown · TXT → TXT — serveur llama.cpp local, plusieurs passes, reprise",
        "book_pick_btn": "📂  Choisir un livre…",
        "book_none": "Aucun livre sélectionné",
        "book_server": "Serveur llama.cpp",
        "book_test_btn": "Tester",
        "book_testing": "Test en cours…",
        "book_server_ok": "✔ {model} · contexte {ctx}",
        "book_server_ko": "✖ injoignable : {err}",
        "book_langs": "Langues",
        "book_passes": "Passes",
        "book_passes_1": "1 — traduction",
        "book_passes_2": "2 — + révision bilingue",
        "book_passes_3": "3 — + relecture finale",
        "book_chunk": "Taille des blocs (car.)",
        "book_model": "Modèle (facultatif)",
        "book_glossary": "Glossaire",
        "book_glossary_hint": "facultatif · une ligne « terme = traduction »",
        "book_translate_btn": "Traduire le livre  →",
        "book_trial_btn": "Essai ({n} blocs)",
        "book_stop_btn": "■  Arrêter",
        "book_open_btn": "📁  Ouvrir le dossier",
        "book_progress": "{done}/{total} blocs · {pct} % · écoulé {elapsed} · reste ~{eta}",
        "book_no_file": "Veuillez choisir un livre (EPUB, PDF ou TXT).",
        "book_no_script": "traduire-livre.py est introuvable à côté de l'application.",
        "book_running": "Une traduction de livre est déjà en cours.",
        "book_done": "Livre traduit : {path}",
        "book_stopped": "Arrêté — relancez pour reprendre là où la traduction s'est arrêtée.",
        "book_failed": "Traduction du livre interrompue (code {rc}) — voir le journal. Relancez pour reprendre.",
        "error_file_pkg": (
            "argostranslatefiles n'est pas installé.\n\n"
            "Installez via : pip install argostranslatefiles"
        ),
        "error_file_trans": "Échec de la traduction du fichier :\n{err}",
        "define_btn": "📖 Définir",
        "define_title": "Définition",
        "define_no_dic": (
            "Aucun dictionnaire pour « {lang} ».\n\n"
            "Attendu : build/dic/{code}-{code}.db\n"
            "(table FTS5 : entries_fts(lemma, definition))"
        ),
        "define_not_found": "Aucune définition trouvée pour « {word} ».",
        "define_select": "Sélectionnez un mot, puis cliquez sur Définir.",
        "define_error": "Erreur dictionnaire :\n{err}",
        "define_from": "Dictionnaire : {lang}",
        "def_tab_title": "Recherche plein texte",
        "def_lang_label": "Dictionnaire",
        "def_search_btn": "Contenant",
        "def_btn_prefix": "Commençant",
        "def_btn_exact":  "Définition",
        "def_searching": "Recherche…",
        "def_results_n": "{n} résultat(s) pour « {word} »",
        "def_no_results": "Aucun résultat pour « {word} ».",
        "def_no_dic_tab": (
            "Aucun dictionnaire pour « {lang} ».\n"
            "Attendu : build/dic/{code}-{code}.db"
        ),
        "def_db_error": "Erreur base de données :\n{err}",
        "def_hint": "Saisissez un mot, puis cliquez sur Contenant, Commençant ou Définition.",
        "def_close": "✕  Fermer",
        "def_refresh": "↺",
        "about_description": "Truchement permet de traduire des textes et des fichiers et de consulter des définitions dans des dictionnaires monolingues.",
    },
    "de": {
        "via_pivot": "· über Englisch",
        "engine_ready": "Übersetzungs-Engine bereit.",
        "title": "Wörterbuch",
        "subtitle": "Texte übersetzen und Wörter definieren",
        "source_lang": "Quellsprache",
        "target_lang": "Zielsprache",
        "source_text": "Quelltext",
        "target_text": "Übersetzung",
        "translate_btn": "Übersetzen  →",
        "clear_btn": "Löschen",
        "swap_btn": "⇄  Tauschen",
        "translating": "Übersetzt…",
        "translating_elapsed": "Übersetzt… {sec}s",
        "translating_slow": "Läuft noch… das erste Laden des Modells kann etwas dauern ({sec}s)",
        "translating_timeout_soon": "Das dauert ungewöhnlich lange ({sec}s) — bitte warten",
        "no_text": "Bitte Text eingeben.",
        "error_title": "Fehler",
        "error_pkg": (
            "argostranslate nicht installiert.\n\n"
            "Installieren: pip install argostranslate"
        ),
        "error_trans": "Fehler:\n{err}",
        "error_no_pkg": "Kein Paket für {src} → {tgt} installiert.",
        "select_langs": "Bitte Sprachen auswählen.",
        "copied": "Übersetzung kopiert.",
        "copy_btn": "⎘ Kopieren",
        "char_count": "{n} Z.",
        "ui_lang": "Interface",
        "tab1": "Text 1",
        "tab2": "Text 2",
        "tab3": "Datei",
        "tab4": "Definition",
        "file_tab_title": "Dateiübersetzung",
        "file_pick_btn": "📂  Datei wählen…",
        "file_dir_label": "Ordner:",
        "file_translate_btn": "Datei übersetzen  →",
        "file_translating": "Datei wird übersetzt…",
        "file_translating_elapsed": "Datei wird übersetzt… {sec}s",
        "file_translating_slow": "Läuft noch… große Dateien oder das erste Laden des Modells können dauern ({sec}s)",
        "file_translating_timeout_soon": "Das dauert ungewöhnlich lange ({sec}s) — bitte warten",
        "file_no_file": "Bitte eine Datei auswählen.",
        "file_label": "Quelldatei",
        "file_none": "Keine Datei ausgewählt",
        "file_out_label": "Ausgabedatei",
        "file_success": "Datei übersetzt: {path}",
        "file_open_btn": "📁  Ordner öffnen",
        "file_formats": "Formate: .txt  .html  .srt  .docx  .pdf",
        # ── serveur llama.cpp local (⚙, Texte 2)
        "llm_title": "Lokaler llama.cpp-Server",
        "llm_hint": "Wird vom Tab Buch verwendet und, wenn das Kästchen „Lokaler Server“ aktiviert ist, von Text 2 (Durchgänge und Blockgröße wie im Tab Buch).",
        "llm_close": "Schließen",
        "llm_check": "Lokaler Server",
        "llm_translating": "Übersetzung mit dem lokalen Server…",
        "llm_translating_elapsed": "Übersetzung mit dem lokalen Server… {sec}s",
        "llm_error": "Lokaler Server: {err}",
        # ── onglet Livre
        "book_pause_btn": "⏸  Pause",
        "book_pausing": "Pause angefordert — aktueller Block wird beendet…",
        "book_paused": "⏸ Pausiert bei {pct} % — jederzeit fortsetzbar, auch nach einem Neustart des Computers.",
        "book_resume_btn": "Übersetzung fortsetzen  →",
        "book_job_paused": "⏸ Übersetzung pausiert: {pct} % ({done}/{total} Blöcke) · begonnen {created} · letzte Aktivität {updated}",
        "book_job_interrupted": "⏸ Übersetzung unterbrochen (Computer ausgeschaltet?): {pct} % ({done}/{total} Blöcke) · begonnen {created} · letzte Aktivität {updated}",
        "book_job_error": "✖ Übersetzung wegen eines Fehlers bei {pct} % ({done}/{total} Blöcke) gestoppt — Server prüfen, dann fortsetzen",
        "book_job_running": "▶ Dieses Buch wird in einem anderen Fenster übersetzt",
        "book_job_done": "✔ Bereits übersetzt ({updated}): {out}",
        "book_partial": "Vorschau: {name}",
        "book_close_running": "Eine Buchübersetzung läuft.\n\nJa: pausieren (am Ende des aktuellen Blocks), dann schließen.\nNein: sofort stoppen (der aktuelle Block wird beim Fortsetzen neu übersetzt).\nAbbrechen: nicht schließen.",
        "tab5": "Buch",
        "book_title": "Buchübersetzung",
        "book_formats": "EPUB → EPUB · PDF → Markdown · TXT → TXT — lokaler llama.cpp-Server, mehrere Durchgänge, fortsetzbar",
        "book_pick_btn": "📂  Buch wählen…",
        "book_none": "Kein Buch ausgewählt",
        "book_server": "llama.cpp-Server",
        "book_test_btn": "Testen",
        "book_testing": "Teste…",
        "book_server_ok": "✔ {model} · Kontext {ctx}",
        "book_server_ko": "✖ nicht erreichbar: {err}",
        "book_langs": "Sprachen",
        "book_passes": "Durchgänge",
        "book_passes_1": "1 — Übersetzung",
        "book_passes_2": "2 — + zweisprachige Revision",
        "book_passes_3": "3 — + Endkorrektur",
        "book_chunk": "Blockgröße (Zeichen)",
        "book_model": "Modell (optional)",
        "book_glossary": "Glossar",
        "book_glossary_hint": "optional · eine Zeile „Begriff = Übersetzung“",
        "book_translate_btn": "Buch übersetzen  →",
        "book_trial_btn": "Probe ({n} Blöcke)",
        "book_stop_btn": "■  Stopp",
        "book_open_btn": "📁  Ordner öffnen",
        "book_progress": "{done}/{total} Blöcke · {pct} % · vergangen {elapsed} · verbleibend ~{eta}",
        "book_no_file": "Bitte ein Buch wählen (EPUB, PDF oder TXT).",
        "book_no_script": "traduire-livre.py wurde neben der Anwendung nicht gefunden.",
        "book_running": "Eine Buchübersetzung läuft bereits.",
        "book_done": "Buch übersetzt: {path}",
        "book_stopped": "Gestoppt — erneut starten, um fortzufahren.",
        "book_failed": "Buchübersetzung abgebrochen (Code {rc}) — siehe Protokoll. Erneut starten, um fortzufahren.",
        "error_file_pkg": (
            "argostranslatefiles nicht installiert.\n\n"
            "Installieren: pip install argostranslatefiles"
        ),
        "error_file_trans": "Dateiübersetzung fehlgeschlagen:\n{err}",
        "define_btn": "📖 Definieren",
        "define_title": "Definition",
        "define_no_dic": (
            "Kein Wörterbuch für \u201e{lang}\u201c.\n\n"
            "Erwartet: build/dic/{code}-{code}.db"
        ),
        "define_not_found": "Keine Definition für \u201e{word}\u201c gefunden.",
        "define_select": "Wählen Sie zuerst ein Wort aus.",
        "define_error": "Wörterbuchfehler:\n{err}",
        "define_from": "Wörterbuch: {lang}",
        "def_tab_title": "Volltext-Wörterbuchsuche",
        "def_lang_label": "Wörterbuch",
        "def_search_btn": "Enthält",
        "def_btn_prefix": "Beginnt mit",
        "def_btn_exact":  "Definition",
        "def_searching": "Suche…",
        "def_results_n": "{n} Ergebnis(se) für \u201e{word}\u201c",
        "def_no_results": "Keine Ergebnisse für \u201e{word}\u201c.",
        "def_no_dic_tab": (
            "Kein Wörterbuch für \u201e{lang}\u201c.\n"
            "Erwartet: build/dic/{code}-{code}.db"
        ),
        "def_db_error": "Datenbankfehler:\n{err}",
        "def_hint": "Wort eingeben, dann Enthält, Beginnt mit oder Definition klicken.",
        "def_close": "✕  Schließen",
        "def_refresh": "↺",
        "about_description": "Truchement ermöglicht es, Texte und Dateien zu übersetzen und Definitionen in einsprachigen Wörterbüchern nachzuschlagen.",
    },
    "es": {
        "via_pivot": "· vía inglés",
        "engine_ready": "Motor de traducción listo.",
        "title": "Diccionario",
        "subtitle": "Traducir textos y definir palabras",
        "source_lang": "Idioma origen",
        "target_lang": "Idioma destino",
        "source_text": "Texto origen",
        "target_text": "Traducción",
        "translate_btn": "Traducir  →",
        "clear_btn": "Limpiar",
        "swap_btn": "⇄  Intercambiar",
        "translating": "Traduciendo…",
        "translating_elapsed": "Traduciendo… {sec}s",
        "translating_slow": "Aún trabajando… la primera carga del modelo puede tardar un poco ({sec}s)",
        "translating_timeout_soon": "Esto está tardando inusualmente ({sec}s) — por favor espere",
        "no_text": "Ingrese texto a traducir.",
        "error_title": "Error",
        "error_pkg": (
            "argostranslate no instalado.\n\n"
            "Instalar: pip install argostranslate"
        ),
        "error_trans": "Error:\n{err}",
        "error_no_pkg": "No hay paquete para {src} → {tgt}.",
        "select_langs": "Seleccione los idiomas.",
        "copied": "Traducción copiada.",
        "copy_btn": "⎘ Copiar",
        "char_count": "{n} car.",
        "ui_lang": "Interfaz",
        "tab1": "Texto 1",
        "tab2": "Texto 2",
        "tab3": "Archivo",
        "tab4": "Definición",
        "file_tab_title": "Traducción de archivo",
        "file_pick_btn": "📂  Elegir archivo…",
        "file_dir_label": "Carpeta:",
        "file_translate_btn": "Traducir archivo  →",
        "file_translating": "Traduciendo archivo…",
        "file_translating_elapsed": "Traduciendo archivo… {sec}s",
        "file_translating_slow": "Aún trabajando… archivos grandes o la primera carga del modelo pueden tardar ({sec}s)",
        "file_translating_timeout_soon": "Esto está tardando inusualmente ({sec}s) — por favor espere",
        "file_no_file": "Por favor elija un archivo.",
        "file_label": "Archivo origen",
        "file_none": "Ningún archivo seleccionado",
        "file_out_label": "Archivo de salida",
        "file_success": "Archivo traducido: {path}",
        "file_open_btn": "📁  Abrir carpeta",
        "file_formats": "Formatos: .txt  .html  .srt  .docx  .pdf",
        # ── serveur llama.cpp local (⚙, Texte 2)
        "llm_title": "Servidor llama.cpp local",
        "llm_hint": "Lo usa la pestaña Libro y, si su casilla «Servidor local» está marcada, Texto 2 (pasadas y tamaño de bloque: los de la pestaña Libro).",
        "llm_close": "Cerrar",
        "llm_check": "Servidor local",
        "llm_translating": "Traduciendo con el servidor local…",
        "llm_translating_elapsed": "Traduciendo con el servidor local… {sec}s",
        "llm_error": "Servidor local: {err}",
        # ── onglet Livre
        "book_pause_btn": "⏸  Pausa",
        "book_pausing": "Pausa solicitada — terminando el bloque actual…",
        "book_paused": "⏸ En pausa al {pct} % — se puede reanudar en cualquier momento, incluso tras reiniciar el ordenador.",
        "book_resume_btn": "Reanudar la traducción  →",
        "book_job_paused": "⏸ Traducción en pausa: {pct} % ({done}/{total} bloques) · iniciada {created} · última actividad {updated}",
        "book_job_interrupted": "⏸ Traducción interrumpida (¿ordenador apagado?): {pct} % ({done}/{total} bloques) · iniciada {created} · última actividad {updated}",
        "book_job_error": "✖ Traducción detenida por un error al {pct} % ({done}/{total} bloques) — compruebe el servidor y reanude",
        "book_job_running": "▶ Este libro se está traduciendo en otra ventana",
        "book_job_done": "✔ Ya traducido ({updated}): {out}",
        "book_partial": "vista previa: {name}",
        "book_close_running": "Hay una traducción de libro en curso.\n\nSí: pausarla (al final del bloque actual) y cerrar.\nNo: detenerla ya (el bloque actual se rehará al reanudar).\nCancelar: no cerrar.",
        "tab5": "Libro",
        "book_title": "Traducción de libro",
        "book_formats": "EPUB → EPUB · PDF → Markdown · TXT → TXT — servidor llama.cpp local, varias pasadas, reanudable",
        "book_pick_btn": "📂  Elegir un libro…",
        "book_none": "Ningún libro seleccionado",
        "book_server": "Servidor llama.cpp",
        "book_test_btn": "Probar",
        "book_testing": "Probando…",
        "book_server_ok": "✔ {model} · contexto {ctx}",
        "book_server_ko": "✖ inaccesible: {err}",
        "book_langs": "Idiomas",
        "book_passes": "Pasadas",
        "book_passes_1": "1 — traducción",
        "book_passes_2": "2 — + revisión bilingüe",
        "book_passes_3": "3 — + corrección final",
        "book_chunk": "Tamaño de bloque (car.)",
        "book_model": "Modelo (opcional)",
        "book_glossary": "Glosario",
        "book_glossary_hint": "opcional · una línea «término = traducción»",
        "book_translate_btn": "Traducir libro  →",
        "book_trial_btn": "Prueba ({n} bloques)",
        "book_stop_btn": "■  Detener",
        "book_open_btn": "📁  Abrir carpeta",
        "book_progress": "{done}/{total} bloques · {pct} % · transcurrido {elapsed} · restante ~{eta}",
        "book_no_file": "Elija un libro (EPUB, PDF o TXT).",
        "book_no_script": "No se encontró traduire-livre.py junto a la aplicación.",
        "book_running": "Ya hay una traducción de libro en curso.",
        "book_done": "Libro traducido: {path}",
        "book_stopped": "Detenido — vuelva a lanzar para reanudar.",
        "book_failed": "Traducción del libro interrumpida (código {rc}) — vea el registro. Vuelva a lanzar para reanudar.",
        "error_file_pkg": (
            "argostranslatefiles no instalado.\n\n"
            "Instalar: pip install argostranslatefiles"
        ),
        "error_file_trans": "Error al traducir el archivo:\n{err}",
        "define_btn": "📖 Definir",
        "define_title": "Definición",
        "define_no_dic": (
            "No hay diccionario para «{lang}».\n\n"
            "Esperado: build/dic/{code}-{code}.db"
        ),
        "define_not_found": "No se encontró definición para «{word}».",
        "define_select": "Seleccione una palabra primero.",
        "define_error": "Error en diccionario:\n{err}",
        "define_from": "Diccionario: {lang}",
        "def_tab_title": "Búsqueda de texto completo",
        "def_lang_label": "Diccionario",
        "def_search_btn": "Contiene",
        "def_btn_prefix": "Empieza con",
        "def_btn_exact":  "Definición",
        "def_searching": "Buscando…",
        "def_results_n": "{n} resultado(s) para «{word}»",
        "def_no_results": "Sin resultados para «{word}».",
        "def_no_dic_tab": (
            "No hay diccionario para «{lang}».\n"
            "Esperado: build/dic/{code}-{code}.db"
        ),
        "def_db_error": "Error de base de datos:\n{err}",
        "def_hint": "Escriba una palabra y haga clic en Contiene, Empieza con o Definición.",
        "def_close": "✕  Cerrar",
        "def_refresh": "↺",
        "about_description": "Truchement permite traducir textos y archivos y consultar definiciones en diccionarios monolingües.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# DÉTECTION DE LA LOCALE UI
# ═══════════════════════════════════════════════════════════════════════════════

def detect_ui_lang() -> str:
    """
    Retourne le code langue de l'interface ('fr', 'de', 'es', 'en') d'après
    la locale système.  Retourne 'en' si la locale n'est pas dans I18N.
    """
    try:
        lc = locale.getlocale()[0] or ""
    except Exception:
        lc = ""
    if not lc:
        import os
        for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
            val = os.environ.get(var, "")
            if val:
                lc = val
                break
    code = lc[:2].lower() if lc else "en"
    return code if code in I18N else "en"
