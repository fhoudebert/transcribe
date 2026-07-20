"""
dictionary.py — Couche dictionnaire SQLite FTS5
=================================================
Convention de nommage des bases :
    build/dic/<code>-<code>.db    ex. build/dic/fr-fr.db

Schéma attendu :
    CREATE TABLE entries (lemma TEXT PRIMARY KEY, definition TEXT);
    CREATE VIRTUAL TABLE entries_fts USING fts5(lemma, definition);

Règles d'accès :
  • Les définitions viennent TOUJOURS de la table physique 'entries'.
  • entries_fts est utilisé pour MATCH (Contenant) via JOIN sur lemma.
  • LIKE (Commençant) et = (Définition / clic) s'exécutent sur entries.

Les connexions sont ouvertes une seule fois par session (check_same_thread=False)
et fermées proprement via close_all_conns() à la fermeture de l'app.
"""

from __future__ import annotations

import os
import sqlite3

from bootstrap import BASE_DIR

# ─── Chemins ───────────────────────────────────────────────────────────────────

DIC_DIR: str = os.path.join(BASE_DIR, "build", "dic")

# Connexions persistantes par code langue : { "fr": sqlite3.Connection, … }
_CONNS: dict[str, sqlite3.Connection] = {}


# ─── Connexions ────────────────────────────────────────────────────────────────

def _db_path(code: str) -> str:
    """Chemin canonique pour build/dic/<code>-<code>.db."""
    return os.path.join(DIC_DIR, f"{code}-{code}.db")


def _get_conn(code: str) -> sqlite3.Connection | None:
    """
    Connexion persistante (lecture/écriture) sur la base *code*.
    Retourne None si le fichier .db est absent.
    """
    if code in _CONNS:
        return _CONNS[code]
    path = _db_path(code)
    if not os.path.isfile(path):
        return None
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _CONNS[code] = conn
    return conn


def _open_ro(code: str) -> sqlite3.Connection:
    """
    Connexion dédiée en lecture seule (mode URI ?mode=ro quand disponible).
    row_factory = sqlite3.Row toujours positionné.
    Lève FileNotFoundError si le .db est absent.
    """
    path = _db_path(code)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    try:
        uri = "file:" + path.replace("\\", "/") + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    except sqlite3.OperationalError:
        conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def close_all_conns() -> None:
    """Ferme proprement toutes les connexions (appelé à la fermeture de l'app)."""
    for conn in list(_CONNS.values()):
        try:
            conn.close()
        except Exception:
            pass
    _CONNS.clear()


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
        (table,),
    )
    return cur.fetchone() is not None


# ─── Utilitaire FTS5 ───────────────────────────────────────────────────────────

def _fts5_escape(query: str) -> str:
    """
    Encapsule *query* entre guillemets FTS5 doubles (opérateurs neutralisés).
    Ex : 'bien-être' → '"bien-être"'
    """
    token = query.strip().replace('"', '""')
    return f'"{token}"'


# ─── Requêtes ──────────────────────────────────────────────────────────────────

def lookup_lemma(code: str, word: str) -> list[sqlite3.Row]:
    """
    Recherche exacte du lemme (utilisée par le bouton 📖 et le clic droit).
    Stratégie :
      1. Table physique 'entries'  WHERE lemma = ?
      2. Fallback 'entries_fts'    WHERE lemma = ?
    Lève FileNotFoundError si le .db est absent.
    Lève RuntimeError en cas d'erreur SQL inattendue.
    """
    conn = _get_conn(code)
    if conn is None:
        raise FileNotFoundError(_db_path(code))
    w = word.strip()
    cur = conn.cursor()
    try:
        cur.execute("SELECT lemma, definition FROM entries WHERE lemma = ?", (w,))
        rows = cur.fetchall()
        if rows:
            return rows
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("SELECT lemma, definition FROM entries_fts WHERE lemma = ?", (w,))
        return cur.fetchall()
    except sqlite3.OperationalError as exc:
        raise RuntimeError(str(exc))


def search_fts(code: str, query: str) -> list[sqlite3.Row]:
    """
    Recherche « Contenant » via FTS5 MATCH, retourne (lemma, definition).

        SELECT e.lemma, e.definition
        FROM entries e
        JOIN entries_fts fts ON e.lemma = fts.lemma
        WHERE fts.lemma MATCH ?
    """
    conn = _get_conn(code)
    if conn is None:
        raise FileNotFoundError(_db_path(code))
    escaped = _fts5_escape(query.strip())
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT e.lemma, e.definition
            FROM entries e
            JOIN entries_fts fts ON e.lemma = fts.lemma
            WHERE fts.lemma MATCH ?
            """,
            (escaped,),
        )
        return cur.fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(str(exc))


def search_like_prefix(code: str, query: str) -> list[sqlite3.Row]:
    """
    Recherche « Commençant par » — LIKE 'query%' ESCAPE '\\' sur entries.
    """
    conn = _get_conn(code)
    if conn is None:
        raise FileNotFoundError(_db_path(code))
    safe = (
        query.strip()
        .replace("\\", "\\\\")
        .replace("%",  "\\%")
        .replace("_",  "\\_")
    )
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT lemma, definition FROM entries"
            " WHERE lemma LIKE ? ESCAPE '\\' ORDER BY lemma",
            (safe + "%",),
        )
        return cur.fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(str(exc))


def search_exact(code: str, query: str) -> list[sqlite3.Row]:
    """
    Recherche « Définition » — égalité stricte sur entries.
    """
    conn = _get_conn(code)
    if conn is None:
        raise FileNotFoundError(_db_path(code))
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT lemma, definition FROM entries WHERE lemma = ?",
            (query.strip(),),
        )
        return cur.fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(str(exc))


def fetch_entry(code: str, lemma: str) -> list[sqlite3.Row]:
    """
    Fiche complète d'un lemme via connexion dédiée en lecture seule
    (évite les conflits avec les recherches asynchrones).
    """
    word = lemma.strip()
    conn = _open_ro(code)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT lemma, definition FROM entries WHERE lemma = ?", (word,)
        )
        return cur.fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(str(exc))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def available_dics() -> list[str]:
    """
    Retourne les codes langue pour lesquels build/dic/<code>-<code>.db existe.
    Ex. ['en', 'fr', 'de']
    """
    if not os.path.isdir(DIC_DIR):
        return []
    codes: list[str] = []
    for fname in sorted(os.listdir(DIC_DIR)):
        if not fname.endswith(".db"):
            continue
        stem = fname[:-3]          # "fr-fr"
        parts = stem.split("-")
        if len(parts) == 2 and parts[0] == parts[1] and parts[0]:
            codes.append(parts[0])
    return codes
