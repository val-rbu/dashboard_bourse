"""Base de données SQLite : liste de suivi, alertes et historique.

SQLite range tout dans un simple fichier (bourse.db, créé à côté de ce script).
Les données restent donc là même quand on ferme l'application.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

CHEMIN_BASE = Path(__file__).parent / "bourse.db"
LISTE_PAR_DEFAUT = ["AAPL", "MSFT", "MC.PA", "TTE.PA"]


def maintenant():
    """Date et heure actuelles, sous forme de texte (ex. 2026-11-04 09:30:00)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def _connexion():
    """Ouvre la base, enregistre les changements à la fin, puis la referme."""
    conn = sqlite3.connect(CHEMIN_BASE)
    conn.row_factory = sqlite3.Row   # permet de lire une ligne par nom de colonne
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialiser():
    """Crée les tables si elles n'existent pas (sans rien effacer)."""
    premiere_fois = not CHEMIN_BASE.exists()
    with _connexion() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                ticker     TEXT PRIMARY KEY,
                date_ajout TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alertes (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker        TEXT NOT NULL,
                sens          TEXT NOT NULL,          -- 'hausse' (>=) ou 'baisse' (<=)
                seuil         REAL NOT NULL,
                active        INTEGER NOT NULL DEFAULT 1,
                date_creation TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS historique_alertes (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                alerte_id         INTEGER NOT NULL,
                ticker            TEXT NOT NULL,
                sens              TEXT NOT NULL,
                seuil             REAL NOT NULL,
                cours             REAL NOT NULL,
                date_declenchement TEXT NOT NULL
            );
            """
        )
        if premiere_fois:
            conn.executemany(
                "INSERT INTO watchlist (ticker, date_ajout) VALUES (?, ?)",
                [(t, maintenant()) for t in LISTE_PAR_DEFAUT],
            )


# ---------------------------------------------------------------
# Liste de suivi
# ---------------------------------------------------------------
def lister_watchlist():
    with _connexion() as conn:
        lignes = conn.execute("SELECT ticker FROM watchlist ORDER BY date_ajout, rowid").fetchall()
    return [ligne["ticker"] for ligne in lignes]


def ajouter_ticker(ticker):
    with _connexion() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (ticker, date_ajout) VALUES (?, ?)",
            (ticker, maintenant()),
        )


def retirer_ticker(ticker):
    """Retire l'action de la liste et supprime aussi ses alertes actives."""
    with _connexion() as conn:
        conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
        conn.execute("DELETE FROM alertes WHERE ticker = ? AND active = 1", (ticker,))


# ---------------------------------------------------------------
# Alertes
# ---------------------------------------------------------------
def creer_alerte(ticker, sens, seuil):
    with _connexion() as conn:
        conn.execute(
            "INSERT INTO alertes (ticker, sens, seuil, date_creation) VALUES (?, ?, ?, ?)",
            (ticker, sens, seuil, maintenant()),
        )


def lister_alertes(ticker=None):
    """Renvoie les alertes actives (toutes, ou celles d'une seule action), en dictionnaires."""
    requete = "SELECT * FROM alertes WHERE active = 1"
    parametres = ()
    if ticker is not None:
        requete += " AND ticker = ?"
        parametres = (ticker,)
    requete += " ORDER BY id"
    with _connexion() as conn:
        return [dict(ligne) for ligne in conn.execute(requete, parametres).fetchall()]


def supprimer_alerte(alerte_id):
    with _connexion() as conn:
        conn.execute("DELETE FROM alertes WHERE id = ?", (alerte_id,))


def declencher_alerte(alerte, cours):
    """Désactive l'alerte (elle ne se déclenche qu'une fois) et l'écrit dans l'historique."""
    with _connexion() as conn:
        conn.execute("UPDATE alertes SET active = 0 WHERE id = ?", (alerte["id"],))
        conn.execute(
            "INSERT INTO historique_alertes "
            "(alerte_id, ticker, sens, seuil, cours, date_declenchement) VALUES (?, ?, ?, ?, ?, ?)",
            (alerte["id"], alerte["ticker"], alerte["sens"], alerte["seuil"], cours, maintenant()),
        )


def lister_historique(limite=20):
    """Renvoie les dernières alertes déclenchées, la plus récente en premier."""
    with _connexion() as conn:
        lignes = conn.execute(
            "SELECT * FROM historique_alertes ORDER BY id DESC LIMIT ?", (limite,)
        ).fetchall()
    return [dict(ligne) for ligne in lignes]
