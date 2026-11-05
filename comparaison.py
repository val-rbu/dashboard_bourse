"""Comparaison de plusieurs actions sur un même graphique (base 100).

Comparer deux cours bruts n'a pas de sens : une action à 400 € et une autre à 40 $
ne sont pas à la même échelle. On ramène donc chaque courbe à 100 à la date de départ.
Une courbe à 130 a gagné 30 % depuis le début, une courbe à 85 a perdu 15 %.
"""

import pandas as pd


def base_100(clotures):
    """Transforme des clôtures en courbes de base 100.

    `clotures` est un dictionnaire {nom: série de clôtures}. Renvoie un tableau avec
    une colonne par nom, qui commence à 100 pour toutes les colonnes.

    Paris et New York n'ont pas exactement les mêmes jours de bourse ouverte et pas
    les mêmes heures. Pour pouvoir les comparer, on ne garde que la date (sans l'heure),
    on reporte le dernier cours connu sur les jours fériés d'une des deux places,
    et on démarre à la première date où toutes les courbes existent.
    """
    colonnes = {}
    for nom, serie in clotures.items():
        serie = serie.dropna()
        if serie.empty:
            continue
        serie = serie.copy()
        index = pd.DatetimeIndex(serie.index)
        if index.tz is not None:
            index = index.tz_localize(None)
        serie.index = index.normalize()
        colonnes[nom] = serie[~serie.index.duplicated(keep="last")]

    if not colonnes:
        return pd.DataFrame()

    tableau = pd.concat(colonnes, axis=1).sort_index().ffill().dropna()
    if tableau.empty:
        return tableau
    return tableau / tableau.iloc[0] * 100
