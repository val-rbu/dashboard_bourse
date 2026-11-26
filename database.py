"""Base de données : liste de suivi, alertes, historique et portefeuille.

Deux façons de ranger les données :
- sur ton ordinateur : SQLite, un simple fichier (bourse.db, créé à côté de ce script) ;
- sur le site en ligne : PostgreSQL (base Neon), partagée par tous les visiteurs. Chaque ligne y porte
  la colonne « utilisateur » (l'identifiant Telegram de son propriétaire) : chacun ne voit que ses données.

Le choix se fait visiteur par visiteur (utiliser_sqlite / utiliser_postgres). Il est rangé « par fil
d'exécution » : Streamlit fait tourner chaque visiteur dans son propre fil, donc ils ne se mélangent jamais.
Sans rien choisir, c'est le fichier bourse.db (comportement de toujours).

Types d'alertes :
- "prix"           : le cours dépasse (hausse) ou passe sous (baisse) un seuil en devise ;
- "variation_jour" : le cours varie d'au moins X % sur la journée (seuil = X, positif) ;
- "rsi"            : le RSI dépasse (hausse) ou passe sous (baisse) un seuil entre 0 et 100 ;
- "croisement_ma"  : la MA50 croise la MA200 (hausse = vers le haut, baisse = vers le bas ; seuil inutilisé, 0) ;
- "volume_anormal" : le volume du jour atteint X fois la moyenne des 20 jours précédents (sens "hausse", seuil = X).
"""

import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

CHEMIN_BASE = Path(__file__).parent / "bourse.db"
LISTE_PAR_DEFAUT = ["AAPL", "MSFT", "MC.PA", "TTE.PA"]

_contexte = threading.local()          # la base choisie pour le visiteur en cours
_verrou_pg = threading.Lock()          # une seule requête à la fois sur la connexion partagée
_connexions_pg = {}                    # adresse de la base -> [connexion, heure de dernière utilisation]
_tables_pg_creees = set()              # adresses des bases dont les tables existent déjà


def maintenant():
    """Date et heure actuelles, sous forme de texte (ex. 2026-11-04 09:30:00)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------
# Choix de la base pour le visiteur en cours
# ---------------------------------------------------------------
def utiliser_sqlite(chemin=None):
    """Ce visiteur utilise un fichier SQLite (par défaut bourse.db)."""
    _contexte.mode = "sqlite"
    _contexte.chemin = Path(chemin) if chemin else None
    _contexte.utilisateur = None


def utiliser_postgres(adresse, utilisateur=None):
    """Ce visiteur utilise la base PostgreSQL en ligne. utilisateur = son identifiant Telegram (texte)."""
    _contexte.mode = "postgres"
    _contexte.adresse = adresse
    _contexte.utilisateur = None if utilisateur is None else str(utilisateur)


def en_ligne():
    """Vrai si le visiteur en cours utilise la base PostgreSQL."""
    return getattr(_contexte, "mode", "sqlite") == "postgres"


def utilisateur_courant():
    return getattr(_contexte, "utilisateur", None)


def _chemin_sqlite():
    return getattr(_contexte, "chemin", None) or CHEMIN_BASE


# ---------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------
def _connexion_pg(adresse):
    """Connexion PostgreSQL gardée ouverte (plus rapide), refaite si la base l'a fermée."""
    import psycopg   # importé seulement en ligne : inutile sur le PC
    from psycopg.rows import dict_row

    conn, derniere = _connexions_pg.get(adresse, (None, 0))
    if conn is not None and not conn.closed and time.time() - derniere > 60:
        try:   # après une pause, Neon a pu couper la connexion : on vérifie
            conn.execute("SELECT 1")
            conn.commit()
        except psycopg.Error:
            conn = None
    if conn is None or conn.closed or conn.broken:
        conn = psycopg.connect(adresse, row_factory=dict_row, connect_timeout=15)
    _connexions_pg[adresse] = [conn, time.time()]
    return conn


class _CurseurPg:
    """Fait accepter à PostgreSQL les requêtes écrites avec des « ? » (le style de SQLite)."""

    def __init__(self, conn):
        self.conn = conn

    def execute(self, requete, parametres=()):
        return self.conn.execute(requete.replace("?", "%s"), parametres)

    def executemany(self, requete, lignes):
        with self.conn.cursor() as curseur:
            curseur.executemany(requete.replace("?", "%s"), lignes)


@contextmanager
def _connexion():
    """Ouvre la base, enregistre les changements à la fin (ou annule tout en cas d'erreur)."""
    if en_ligne():
        with _verrou_pg:
            conn = _connexion_pg(_contexte.adresse)
            try:
                yield _CurseurPg(conn)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return
    conn = sqlite3.connect(_chemin_sqlite())
    conn.row_factory = sqlite3.Row   # permet de lire une ligne par nom de colonne
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _moi():
    """Condition SQL qui garde seulement les lignes du visiteur (en ligne), et ses paramètres."""
    if en_ligne():
        return "utilisateur = ?", (utilisateur_courant(),)
    return "1 = 1", ()


def _inserer(conn, table, valeurs):
    """INSERT simple ; en ligne, la ligne est rattachée au visiteur."""
    valeurs = dict(valeurs)
    if en_ligne():
        valeurs["utilisateur"] = utilisateur_courant()
    colonnes = ", ".join(valeurs)
    trous = ", ".join("?" for _ in valeurs)
    conn.execute(f"INSERT INTO {table} ({colonnes}) VALUES ({trous})", tuple(valeurs.values()))


# ---------------------------------------------------------------
# Création des tables
# ---------------------------------------------------------------
TABLES_POSTGRES = [
    """CREATE TABLE IF NOT EXISTS utilisateurs (
        utilisateur      TEXT PRIMARY KEY,
        date_inscription TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS sessions (
        jeton         TEXT PRIMARY KEY,
        utilisateur   TEXT NOT NULL,
        date_creation TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS watchlist (
        ordre       SERIAL,
        utilisateur TEXT NOT NULL,
        ticker      TEXT NOT NULL,
        date_ajout  TEXT NOT NULL,
        PRIMARY KEY (utilisateur, ticker))""",
    """CREATE TABLE IF NOT EXISTS alertes (
        id            SERIAL PRIMARY KEY,
        utilisateur   TEXT NOT NULL,
        ticker        TEXT NOT NULL,
        sens          TEXT NOT NULL,
        seuil         DOUBLE PRECISION NOT NULL,
        active        INTEGER NOT NULL DEFAULT 1,
        date_creation TEXT NOT NULL,
        type          TEXT NOT NULL DEFAULT 'prix',
        devise        TEXT)""",
    """CREATE TABLE IF NOT EXISTS historique_alertes (
        id                 SERIAL PRIMARY KEY,
        utilisateur        TEXT NOT NULL,
        alerte_id          INTEGER NOT NULL,
        ticker             TEXT NOT NULL,
        sens               TEXT NOT NULL,
        seuil              DOUBLE PRECISION NOT NULL,
        cours              DOUBLE PRECISION NOT NULL,
        date_declenchement TEXT NOT NULL,
        type               TEXT NOT NULL DEFAULT 'prix',
        variation          DOUBLE PRECISION,
        devise             TEXT)""",
    """CREATE TABLE IF NOT EXISTS positions (
        id          SERIAL PRIMARY KEY,
        utilisateur TEXT NOT NULL,
        ticker      TEXT NOT NULL,
        quantite    DOUBLE PRECISION NOT NULL,
        prix_achat  DOUBLE PRECISION NOT NULL,
        date_achat  TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS alertes_utilisateur ON alertes (utilisateur, active)",
    # Mise à jour d'une base créée avant l'ajout de la devise des alertes
    "ALTER TABLE alertes ADD COLUMN IF NOT EXISTS devise TEXT",
    "ALTER TABLE historique_alertes ADD COLUMN IF NOT EXISTS devise TEXT",
]


def _ajouter_colonne_si_absente(conn, table, colonne, definition):
    """Ajoute une colonne à une table SQLite existante (utile pour mettre à jour une ancienne base)."""
    colonnes = [ligne["name"] for ligne in conn.execute(f"PRAGMA table_info({table})")]
    if colonne not in colonnes:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")


def initialiser():
    """Crée les tables si besoin. Renvoie True si c'est la toute première fois (base ou utilisateur nouveau).

    La première fois, la liste de suivi reçoit quelques actions par défaut.
    """
    if en_ligne():
        return _initialiser_postgres()

    premiere_fois = not _chemin_sqlite().exists()
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
                date_creation TEXT NOT NULL,
                type          TEXT NOT NULL DEFAULT 'prix'
            );
            CREATE TABLE IF NOT EXISTS historique_alertes (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                alerte_id          INTEGER NOT NULL,
                ticker             TEXT NOT NULL,
                sens               TEXT NOT NULL,
                seuil              REAL NOT NULL,
                cours              REAL NOT NULL,
                date_declenchement TEXT NOT NULL,
                type               TEXT NOT NULL DEFAULT 'prix',
                variation          REAL             -- variation du jour (%) au déclenchement, si pertinent
            );
            CREATE TABLE IF NOT EXISTS positions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker     TEXT NOT NULL,
                quantite   REAL NOT NULL,
                prix_achat REAL NOT NULL,
                date_achat TEXT NOT NULL
            );
            """
        )
        # Mise à jour d'une base créée avant l'étape 6 : on ajoute les nouvelles colonnes
        _ajouter_colonne_si_absente(conn, "alertes", "type", "TEXT NOT NULL DEFAULT 'prix'")
        _ajouter_colonne_si_absente(conn, "historique_alertes", "type", "TEXT NOT NULL DEFAULT 'prix'")
        _ajouter_colonne_si_absente(conn, "historique_alertes", "variation", "REAL")
        # devise du seuil (alertes de prix) et du cours enregistré ; vide = devise de cotation de l'action
        _ajouter_colonne_si_absente(conn, "alertes", "devise", "TEXT")
        _ajouter_colonne_si_absente(conn, "historique_alertes", "devise", "TEXT")

        if premiere_fois:
            conn.executemany(
                "INSERT INTO watchlist (ticker, date_ajout) VALUES (?, ?)",
                [(t, maintenant()) for t in LISTE_PAR_DEFAUT],
            )
    return premiere_fois


def _initialiser_postgres():
    adresse = _contexte.adresse
    if adresse not in _tables_pg_creees:
        with _connexion() as conn:
            for requete in TABLES_POSTGRES:
                conn.execute(requete)
        _tables_pg_creees.add(adresse)

    utilisateur = utilisateur_courant()
    if utilisateur is None:   # vérificateur automatique : il n'a besoin que des tables
        return False
    with _connexion() as conn:
        nouveau = conn.execute(
            "INSERT INTO utilisateurs (utilisateur, date_inscription) VALUES (?, ?) ON CONFLICT DO NOTHING RETURNING utilisateur",
            (utilisateur, maintenant()),
        ).fetchone() is not None
        if nouveau:
            conn.executemany(
                "INSERT INTO watchlist (utilisateur, ticker, date_ajout) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                [(utilisateur, t, maintenant()) for t in LISTE_PAR_DEFAUT],
            )
    return nouveau


# ---------------------------------------------------------------
# Liste de suivi
# ---------------------------------------------------------------
def lister_watchlist():
    condition, parametres = _moi()
    ordre = "ordre" if en_ligne() else "date_ajout, rowid"
    with _connexion() as conn:
        lignes = conn.execute(f"SELECT ticker FROM watchlist WHERE {condition} ORDER BY {ordre}", parametres).fetchall()
    return [ligne["ticker"] for ligne in lignes]


def ajouter_ticker(ticker):
    with _connexion() as conn:
        if en_ligne():
            conn.execute(
                "INSERT INTO watchlist (utilisateur, ticker, date_ajout) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                (utilisateur_courant(), ticker, maintenant()),
            )
        else:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (ticker, date_ajout) VALUES (?, ?)",
                (ticker, maintenant()),
            )


def retirer_ticker(ticker):
    """Retire l'action de la liste et supprime aussi ses alertes actives."""
    condition, parametres = _moi()
    with _connexion() as conn:
        conn.execute(f"DELETE FROM watchlist WHERE ticker = ? AND {condition}", (ticker, *parametres))
        conn.execute(f"DELETE FROM alertes WHERE ticker = ? AND active = 1 AND {condition}", (ticker, *parametres))


# ---------------------------------------------------------------
# Alertes
# ---------------------------------------------------------------
def creer_alerte(ticker, sens, seuil, type_alerte="prix", devise=None):
    """devise = symbole de la devise du seuil (ex. « € ») pour une alerte de prix ; None = devise de cotation."""
    with _connexion() as conn:
        _inserer(conn, "alertes", {
            "ticker": ticker, "sens": sens, "seuil": seuil, "date_creation": maintenant(), "type": type_alerte,
            "devise": devise,
        })


def lister_alertes(ticker=None):
    """Renvoie les alertes actives (toutes, ou celles d'une seule action), en dictionnaires."""
    condition, parametres = _moi()
    requete = f"SELECT * FROM alertes WHERE active = 1 AND {condition}"
    if ticker is not None:
        requete += " AND ticker = ?"
        parametres = (*parametres, ticker)
    requete += " ORDER BY id"
    with _connexion() as conn:
        return [dict(ligne) for ligne in conn.execute(requete, parametres).fetchall()]


def supprimer_alerte(alerte_id):
    condition, parametres = _moi()
    with _connexion() as conn:
        conn.execute(f"DELETE FROM alertes WHERE id = ? AND {condition}", (alerte_id, *parametres))


def declencher_alerte(alerte, cours, variation=None, devise=None):
    """Désactive l'alerte (elle ne se déclenche qu'une fois) et l'écrit dans l'historique."""
    with _connexion() as conn:
        conn.execute("UPDATE alertes SET active = 0 WHERE id = ?", (alerte["id"],))
        _inserer(conn, "historique_alertes", {
            "alerte_id": alerte["id"], "ticker": alerte["ticker"], "sens": alerte["sens"], "seuil": alerte["seuil"],
            "cours": cours, "date_declenchement": maintenant(), "type": alerte["type"], "variation": variation,
            "devise": devise,
        })


def lister_historique(limite=20):
    """Renvoie les dernières alertes déclenchées, la plus récente en premier."""
    condition, parametres = _moi()
    with _connexion() as conn:
        lignes = conn.execute(
            f"SELECT * FROM historique_alertes WHERE {condition} ORDER BY id DESC LIMIT ?", (*parametres, limite)
        ).fetchall()
    return [dict(ligne) for ligne in lignes]


# ---------------------------------------------------------------
# Portefeuille (un achat = une ligne, appelée « lot »)
# ---------------------------------------------------------------
def ajouter_position(ticker, quantite, prix_achat):
    with _connexion() as conn:
        _inserer(conn, "positions", {
            "ticker": ticker, "quantite": quantite, "prix_achat": prix_achat, "date_achat": maintenant(),
        })


def lister_positions():
    """Renvoie tous les achats enregistrés, en dictionnaires, du plus ancien au plus récent."""
    condition, parametres = _moi()
    with _connexion() as conn:
        return [dict(ligne) for ligne in conn.execute(
            f"SELECT * FROM positions WHERE {condition} ORDER BY id", parametres
        ).fetchall()]


def supprimer_position(position_id):
    condition, parametres = _moi()
    with _connexion() as conn:
        conn.execute(f"DELETE FROM positions WHERE id = ? AND {condition}", (position_id, *parametres))


# ---------------------------------------------------------------
# En ligne seulement : sessions (« se souvenir de moi ») et vérification de tous les comptes
# ---------------------------------------------------------------
DUREE_SESSION_JOURS = 90


def creer_session(jeton, utilisateur):
    with _connexion() as conn:
        conn.execute(
            "INSERT INTO sessions (jeton, utilisateur, date_creation) VALUES (?, ?, ?)",
            (jeton, str(utilisateur), maintenant()),
        )


def utilisateur_de_session(jeton):
    """Renvoie l'identifiant Telegram lié à ce jeton (s'il n'a pas expiré), sinon None."""
    limite = (datetime.now() - timedelta(days=DUREE_SESSION_JOURS)).strftime("%Y-%m-%d %H:%M:%S")
    with _connexion() as conn:
        ligne = conn.execute(
            "SELECT utilisateur FROM sessions WHERE jeton = ? AND date_creation >= ?", (jeton, limite)
        ).fetchone()
    return ligne["utilisateur"] if ligne else None


def supprimer_session(jeton):
    with _connexion() as conn:
        conn.execute("DELETE FROM sessions WHERE jeton = ?", (jeton,))


def nettoyer_sessions():
    """Supprime les sessions trop anciennes."""
    limite = (datetime.now() - timedelta(days=DUREE_SESSION_JOURS)).strftime("%Y-%m-%d %H:%M:%S")
    with _connexion() as conn:
        conn.execute("DELETE FROM sessions WHERE date_creation < ?", (limite,))


def utilisateurs_avec_alertes():
    """Identifiants de tous les comptes qui ont au moins une alerte active (pour le vérificateur)."""
    with _connexion() as conn:
        lignes = conn.execute("SELECT DISTINCT utilisateur FROM alertes WHERE active = 1").fetchall()
    return [ligne["utilisateur"] for ligne in lignes]
