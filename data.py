"""Module de données : tout ce qui va chercher des cours sur Internet.

Ce fichier est utilisé à la fois par l'interface (app.py) et par le vérificateur
d'alertes (verificateur.py). Il ne dépend pas de Streamlit.
"""

import yfinance as yf

import indicateurs as ind


def recuperer_cours(ticker, periode="1mo", intervalle="1d"):
    """Renvoie le tableau des cours d'une action (une ligne par point)."""
    return yf.Ticker(ticker).history(period=periode, interval=intervalle)


def dernier_prix(ticker):
    """Renvoie le dernier cours connu (différé d'environ 15 min), ou None si indisponible.

    On essaie d'abord les points de 5 minutes du jour, puis, si la bourse est
    fermée ou si rien ne vient, les clôtures des derniers jours.
    """
    for periode, intervalle in (("1d", "5m"), ("5d", "1d")):
        cours = recuperer_cours(ticker, periode, intervalle)
        if not cours.empty:
            return float(cours["Close"].iloc[-1])
    return None


def variation_jour(ticker):
    """Renvoie (dernier cours, variation en % par rapport à la clôture précédente), ou None.

    Même calcul que la liste de suivi de l'interface : on compare les deux
    dernières clôtures journalières.
    """
    clotures = recuperer_cours(ticker, "5d", "1d")["Close"].dropna()
    if len(clotures) < 2:
        return None
    dernier = float(clotures.iloc[-1])
    precedent = float(clotures.iloc[-2])
    return dernier, (dernier - precedent) / precedent * 100


def rapport_volume(ticker, fenetre=20):
    """Renvoie (dernier cours, volume du jour / volume moyen des jours précédents), ou None.

    Le volume du jour peut être partiel tant que la bourse est ouverte : le rapport augmente
    donc au fil de la séance.
    """
    donnees = recuperer_cours(ticker, "3mo", "1d")
    if donnees.empty:
        return None
    rapport = ind.rapport_volume(donnees["Volume"], fenetre)
    if rapport is None:
        return None
    return float(donnees["Close"].iloc[-1]), rapport


def actualites_brutes(ticker):
    """Renvoie la liste brute des articles récents sur l'action (liste vide en cas de problème)."""
    try:
        return yf.Ticker(ticker).news or []
    except Exception:   # yfinance est instable : mieux vaut aucune actualité qu'une page en erreur
        return []


def clotures_5ans(ticker):
    """Clôtures journalières des 5 dernières années (série vide si indisponible)."""
    return recuperer_cours(ticker, "5y", "1d")["Close"].dropna()


def devise(ticker):
    """Les actions de Paris finissent par .PA et sont en euros, les autres en dollars."""
    return "€" if ticker.endswith(".PA") else "$"
