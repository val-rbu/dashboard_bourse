"""Recherche d'actions par nom ou par ticker : mise en forme des résultats de Yahoo Finance.

Yahoo renvoie, pour un texte comme « apple » ou « lvmh », une liste de valeurs avec leur ticker,
leur nom et leur place de cotation. Ce fichier transforme cette liste en phrases lisibles pour une
liste déroulante, et sait retrouver le ticker à partir de la phrase choisie.

Une phrase a la forme : « Apple Inc. (AAPL) · NASDAQ ».

Ce fichier ne dépend ni de Streamlit ni d'Internet.
"""

import re

TYPES_ACCEPTES = {"EQUITY": "", "ETF": "ETF", "INDEX": "indice"}   # actions, fonds indiciels, indices
FORME_TICKER = re.compile(r"^[A-Za-z0-9.^=\-]{1,12}$")


def normaliser(quotes, limite=10):
    """Garde les actions, ETF et indices, sans doublon, sous la forme {symbole, nom, place}."""
    resultats = []
    vus = set()
    for q in quotes or []:
        if not isinstance(q, dict):
            continue
        symbole = q.get("symbol")
        type_ = q.get("quoteType")
        if not isinstance(symbole, str) or not symbole or type_ not in TYPES_ACCEPTES or symbole in vus:
            continue
        vus.add(symbole)
        nom = q.get("longname") or q.get("shortname") or symbole
        place = q.get("exchDisp") or q.get("exchange") or ""
        etiquette = TYPES_ACCEPTES[type_]
        resultats.append({
            "symbole": symbole,
            "nom": str(nom),
            "place": " · ".join(x for x in (str(place).replace("(", "").replace(")", ""), etiquette) if x),
        })
    return resultats[:limite]


def libelle(resultat):
    """Phrase affichée dans la liste déroulante."""
    return f"{resultat['nom']} ({resultat['symbole']}) · {resultat['place'] or 'bourse inconnue'}"


def symbole_depuis_libelle(texte):
    """Retrouve le ticker à partir d'une phrase de la liste (None si le format n'est pas reconnu).

    On lit le dernier « (TICKER) · place » de la phrase : le nom de la société peut lui-même
    contenir des parenthèses, et la place peut contenir un « · » (ex. « NYSE Arca · ETF »).
    """
    if not isinstance(texte, str):
        return None
    trouve = re.search(r"\(([^()]+)\) · [^()]*$", texte.strip())
    return trouve.group(1) if trouve else None


def options(texte, quotes, limite=10):
    """Liste des phrases à proposer pour le texte tapé (rien en dessous de 2 lettres).

    Si la recherche ne trouve rien (valeur inconnue de Yahoo, service indisponible) et que le texte
    ressemble à un ticker (« NVDA », « AIR.PA »), on le propose tel quel : on pourra tenter de
    l'ajouter, l'application vérifiera ensuite qu'il existe vraiment.
    """
    texte = (texte or "").strip()
    if len(texte) < 2:
        return []
    phrases = [libelle(r) for r in normaliser(quotes, limite)]
    if not phrases and FORME_TICKER.match(texte):
        direct = texte.upper()
        phrases.append(f"{direct} ({direct}) · ticker saisi directement")
    return phrases
