"""Calculs du portefeuille : valeur actuelle, gain ou perte, par action et au total.

Un « lot » est un achat : (ticker, quantité, prix d'achat). Si tu achètes deux fois la
même action, tu as deux lots ; on les regroupe ici avec un prix d'achat moyen (le PRU,
« prix de revient unitaire »).

Ce fichier ne dépend ni de Streamlit ni d'Internet : on lui donne les lots et les cours.
"""

from data import devise


def synthese(lots, cours):
    """Regroupe les lots par action et calcule la valeur et le gain de chacune.

    `lots`  : liste de dictionnaires avec les clés ticker, quantite, prix_achat
    `cours` : dictionnaire {ticker: dernier cours connu, ou None}
    Renvoie une liste de dictionnaires, une par action.
    """
    groupes = {}
    for lot in lots:
        g = groupes.setdefault(lot["ticker"], {"quantite": 0.0, "investi": 0.0})
        g["quantite"] += lot["quantite"]
        g["investi"] += lot["quantite"] * lot["prix_achat"]

    lignes = []
    for ticker, g in groupes.items():
        prix = cours.get(ticker)
        ligne = {
            "ticker": ticker,
            "devise": devise(ticker),
            "quantite": g["quantite"],
            "pru": g["investi"] / g["quantite"],
            "investi": g["investi"],
            "cours": prix,
            "valeur": None,
            "gain": None,
            "gain_pct": None,
        }
        if prix is not None:
            ligne["valeur"] = g["quantite"] * prix
            ligne["gain"] = ligne["valeur"] - g["investi"]
            ligne["gain_pct"] = ligne["gain"] / g["investi"] * 100
        lignes.append(ligne)
    return lignes


def totaux_par_devise(lignes):
    """Additionne par devise (on ne mélange pas des euros et des dollars sans conversion).

    Renvoie {"€": {"investi", "valeur", "gain", "gain_pct"}, "$": {...}}.
    Les actions dont le cours est indisponible sont ignorées.
    """
    totaux = {}
    for ligne in lignes:
        if ligne["valeur"] is None:
            continue
        t = totaux.setdefault(ligne["devise"], {"investi": 0.0, "valeur": 0.0})
        t["investi"] += ligne["investi"]
        t["valeur"] += ligne["valeur"]
    for t in totaux.values():
        t["gain"] = t["valeur"] - t["investi"]
        t["gain_pct"] = t["gain"] / t["investi"] * 100
    return totaux
