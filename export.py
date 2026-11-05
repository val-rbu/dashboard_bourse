"""Export de tableaux au format CSV, lisible directement par Excel en français.

Séparateur « ; », virgule décimale et marque d'encodage UTF-8 (BOM), pour que les accents
et les nombres s'affichent correctement à l'ouverture dans Excel.

Ce fichier ne dépend ni de Streamlit ni d'Internet.
"""

import csv
import io


def _cellule(valeur):
    """Met une valeur sous forme de texte adapté à Excel."""
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, float):
        return f"{valeur:.4f}".rstrip("0").rstrip(",.").replace(".", ",") if valeur == valeur else ""
    texte = str(valeur)
    # Excel prendrait un texte commençant par = + - @ pour une formule : on le neutralise
    if texte.startswith(("=", "+", "-", "@")):
        texte = "'" + texte
    return texte


def vers_csv(lignes):
    """Transforme une liste de dictionnaires (mêmes clés) en contenu CSV (octets). Liste vide : octets vides."""
    if not lignes:
        return b""
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    colonnes = list(lignes[0].keys())
    ecrivain.writerow(colonnes)
    for ligne in lignes:
        ecrivain.writerow([_cellule(ligne.get(c)) for c in colonnes])
    return sortie.getvalue().encode("utf-8-sig")
