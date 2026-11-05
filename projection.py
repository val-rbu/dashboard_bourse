"""Projection de tendance : prolonger la pente récente du cours, avec une fourchette d'incertitude.

Ce n'est PAS une prévision fiable : la méthode suppose que la tendance des derniers mois continue
et que les variations quotidiennes gardent la même amplitude. Elle sert à visualiser « où irait
le cours si rien ne changeait » et, grâce à `evaluer`, à mesurer honnêtement si cette méthode
aurait bien fonctionné dans le passé.

Méthode :
1. on ajuste une droite sur le logarithme des cours (une pente en % par jour) ;
2. la projection part du dernier cours et continue à cette pente ;
3. la fourchette à 95 % s'élargit avec la racine du nombre de jours, à partir de l'amplitude
   habituelle des variations quotidiennes (volatilité).

Ce fichier ne dépend ni de Streamlit ni d'Internet.
"""

import numpy as np
import pandas as pd

Z_95 = 1.96   # une fourchette à 95 % s'étend de 1,96 écart-type de part et d'autre


def _ajuster(valeurs):
    """Renvoie (pente par jour du log du cours, volatilité quotidienne) pour un tableau de cours."""
    log_cours = np.log(valeurs)
    pente = np.polyfit(np.arange(len(log_cours)), log_cours, 1)[0]
    volatilite = np.diff(log_cours).std(ddof=1)
    return float(pente), float(volatilite)


def _fourchette(dernier, pente, volatilite, jours):
    """Projection centrale, borne basse et borne haute pour chaque nombre de jours demandé."""
    jours = np.asarray(jours)
    centre = dernier * np.exp(pente * jours)
    marge = Z_95 * volatilite * np.sqrt(jours)
    return centre, centre * np.exp(-marge), centre * np.exp(marge)


def projeter(cloture, jours_historique=252, horizon=30):
    """Projette le cours sur `horizon` séances à partir de la tendance des `jours_historique` derniers jours.

    Renvoie un dictionnaire : "previsions" (tableau centre / bas / haut, indexé par date de séance),
    "pente_jour_pct" et "volatilite_jour_pct".
    """
    cloture = cloture.dropna().iloc[-jours_historique:]
    if len(cloture) < 30:
        raise ValueError("Pas assez de données pour projeter.")
    pente, volatilite = _ajuster(cloture.values)
    centre, bas, haut = _fourchette(float(cloture.iloc[-1]), pente, volatilite, np.arange(1, horizon + 1))
    dates = pd.bdate_range(cloture.index[-1] + pd.Timedelta(days=1), periods=horizon)
    return {
        "previsions": pd.DataFrame({"centre": centre, "bas": bas, "haut": haut}, index=dates),
        "pente_jour_pct": (np.exp(pente) - 1) * 100,
        "volatilite_jour_pct": volatilite * 100,
    }


def evaluer(cloture, jours_historique=252, horizon=30, pas=10):
    """Rejoue la méthode dans le passé : aurait-elle bien prévu le cours `horizon` séances plus tard ?

    À intervalles réguliers (`pas` séances), on projette avec les seules données connues à l'époque,
    puis on compare au cours réellement observé. Renvoie None si l'historique est trop court, sinon :
    - couverture_pct : part des cas où le cours réel est resté dans la fourchette (visé : environ 95 %) ;
    - erreur_modele_pct : écart moyen entre la projection et la réalité ;
    - erreur_naive_pct : écart moyen si on avait simplement supposé « le cours ne bouge pas ».
    Si l'erreur du modèle n'est pas plus faible que l'erreur naïve, la tendance n'apporte rien.
    """
    valeurs = cloture.dropna().values
    dans_fourchette, erreurs_modele, erreurs_naives = [], [], []
    for t in range(jours_historique, len(valeurs) - horizon, pas):
        fenetre = valeurs[t - jours_historique:t]
        dernier = float(fenetre[-1])
        pente, volatilite = _ajuster(fenetre)
        centre, bas, haut = _fourchette(dernier, pente, volatilite, [horizon])
        reel = float(valeurs[t - 1 + horizon])
        dans_fourchette.append(bool(bas[0] <= reel <= haut[0]))
        erreurs_modele.append(abs(centre[0] - reel) / reel * 100)
        erreurs_naives.append(abs(dernier - reel) / reel * 100)
    if not dans_fourchette:
        return None
    return {
        "nombre_tests": len(dans_fourchette),
        "couverture_pct": float(np.mean(dans_fourchette) * 100),
        "erreur_modele_pct": float(np.mean(erreurs_modele)),
        "erreur_naive_pct": float(np.mean(erreurs_naives)),
    }
