"""Conversion de prix entre plusieurs devises, au taux de change du jour.

Tous les taux sont exprimés par rapport au dollar : combien d'unités de la devise pour 1 $.
Yahoo Finance les donne avec les symboles « EUR=X », « GBP=X », « JPY=X », « CNY=X ».
Pour passer d'une devise A à une devise B : montant × (taux de B / taux de A).

Le même taux (celui du jour) est appliqué à tout l'historique : un graphique converti garde
donc exactement la même forme, seule l'échelle des prix change.

Ce fichier ne dépend ni de Streamlit ni d'Internet : app.py lui fournit les taux.
"""

# Symbole affiché -> (code de la devise, nom dans la liste déroulante, symbole Yahoo du taux pour 1 $)
DEVISES = {
    "€": ("EUR", "Euro (€)", "EUR=X"),
    "$": ("USD", "Dollar ($)", None),          # le dollar est la référence : taux = 1
    "£": ("GBP", "Livre sterling (£)", "GBP=X"),
    "¥": ("JPY", "Yen japonais (¥)", "JPY=X"),
    "CN¥": ("CNY", "Yuan chinois (CN¥)", "CNY=X"),
}


def symboles_yahoo():
    """Symboles Yahoo à télécharger pour connaître tous les taux : {symbole affiché: symbole Yahoo}."""
    return {sym: info[2] for sym, info in DEVISES.items() if info[2]}


def facteur(de, vers, taux):
    """Nombre par lequel multiplier un montant en `de` pour l'avoir en `vers`.

    taux : {symbole affiché: unités pour 1 $}. Si un taux manque, on ne convertit pas (facteur 1).
    """
    if de == vers:
        return 1.0
    t_de = 1.0 if de == "$" else taux.get(de)
    t_vers = 1.0 if vers == "$" else taux.get(vers)
    if not t_de or not t_vers:
        return 1.0
    return t_vers / t_de


def convertir(donnees, f):
    """Applique un facteur à une série de prix, ou aux colonnes Open/High/Low/Close d'un tableau (pas au volume)."""
    if f == 1.0:
        return donnees
    if hasattr(donnees, "columns"):
        donnees = donnees.copy()
        for colonne in ("Open", "High", "Low", "Close"):
            if colonne in donnees:
                donnees[colonne] = donnees[colonne] * f
        return donnees
    return donnees * f
