"""Conversion de prix entre l'euro (€) et le dollar ($).

On part du taux EUR/USD (nombre de dollars pour 1 euro), récupéré sous forme de série
journalière. Pour afficher l'historique d'un cours dans une autre devise, on convertit chaque
jour avec le taux de ce jour-là : le graphique tient ainsi compte de l'évolution du change.

Seuls € et $ sont gérés ; toute autre combinaison laisse les valeurs inchangées.

Ce fichier ne dépend ni de Streamlit ni d'Internet.
"""

import numpy as np
import pandas as pd

DEVISES_GEREES = ("€", "$")


def _convertible(de, vers):
    return de != vers and de in DEVISES_GEREES and vers in DEVISES_GEREES


def _jours(index):
    """Ramène des dates avec heure (et fuseau) à des jours simples, pour pouvoir les comparer."""
    jours = pd.DatetimeIndex(index)
    if jours.tz is not None:
        jours = jours.tz_localize(None)
    return jours.normalize()


def facteurs(index, de, vers, eurusd):
    """Nombre par lequel multiplier un prix en `de` pour l'avoir en `vers`, pour chaque date de `index`.

    Le taux utilisé est celui du jour ; s'il manque (week-end, jour férié), on reprend le dernier connu.
    """
    if not _convertible(de, vers):
        return np.ones(len(index))
    taux_jour = eurusd.dropna().copy()
    taux_jour.index = _jours(taux_jour.index)
    taux_jour = taux_jour[~taux_jour.index.duplicated(keep="last")].sort_index()
    cles = _jours(index)
    taux = taux_jour.reindex(taux_jour.index.union(cles.unique())).ffill().bfill().reindex(cles).to_numpy(dtype=float)
    return taux if de == "€" else 1 / taux   # € -> $ : on multiplie par le taux ; $ -> € : on le divise


def convertir_serie(serie, de, vers, eurusd):
    """Série de prix (une valeur par date) convertie de `de` vers `vers`."""
    if not _convertible(de, vers):
        return serie
    return serie * facteurs(serie.index, de, vers, eurusd)


def convertir_ohlc(donnees, de, vers, eurusd):
    """Tableau de cours (Open, High, Low, Close) converti ; le volume ne change pas."""
    if not _convertible(de, vers):
        return donnees
    donnees = donnees.copy()
    f = facteurs(donnees.index, de, vers, eurusd)
    for colonne in ("Open", "High", "Low", "Close"):
        if colonne in donnees:
            donnees[colonne] = donnees[colonne] * f
    return donnees


def facteur_actuel(de, vers, eurusd):
    """Facteur de conversion avec le dernier taux connu (pour un prix isolé)."""
    if not _convertible(de, vers):
        return 1.0
    taux = float(eurusd.dropna().iloc[-1])
    return taux if de == "€" else 1 / taux
