"""Score de sentiment des titres d'actualité, par la méthode du dictionnaire.

Principe : on compte les mots « positifs » (hausse, bénéfice, beat, surge...) et « négatifs »
(chute, perte, miss, lawsuit...) d'un titre. Un mot de négation juste avant (« not », « no »,
« pas »...) inverse le sens du mot. Le score va de -1 (très négatif) à +1 (très positif).

C'est volontairement simple et transparent : on voit exactement pourquoi un titre est noté
ainsi. Limites : un dictionnaire ne comprend ni l'ironie ni le contexte (« cuts costs » est
plutôt positif, « cuts jobs » plutôt négatif). Un modèle de langage ferait mieux, mais
serait une boîte noire beaucoup plus lourde à installer.

Ce fichier ne dépend ni de Streamlit ni d'Internet.
"""

import re

MOTS_POSITIFS = {
    # anglais
    "up", "rise", "rises", "rising", "rose", "growth", "grow", "grows", "growing", "profit", "profits",
    "profitable", "record", "strong", "stronger", "strongest", "bullish", "upgrade", "upgrades", "upgraded",
    "outperform", "outperforms", "optimistic", "win", "wins", "winning", "boost", "boosts", "boosted",
    "rebound", "rebounds", "recovery", "recovers", "positive", "success", "successful", "improve",
    "improves", "improved", "expansion", "expands", "dividend", "buyback", "approval", "approved",
    "breakthrough", "higher", "best", "soar", "soars", "soared", "surge", "surges", "surged", "jump",
    "jumps", "jumped", "gain", "gains", "gained", "rally", "rallies", "beat", "beats", "exceeds",
    "exceeded", "tops", "topped",
    # français
    "hausse", "hausses", "progresse", "progression", "bondit", "grimpe", "croissance", "bénéfice",
    "bénéfices", "rebond", "optimiste", "haussier", "succès", "dividende", "surperforme", "amélioration",
    "gagne", "forte", "record",
}

MOTS_NEGATIFS = {
    # anglais
    "down", "fall", "falls", "falling", "fell", "drop", "drops", "dropped", "plunge", "plunges",
    "plunged", "slump", "slumps", "tumble", "tumbles", "tumbled", "sink", "sinks", "sank", "loss",
    "losses", "lose", "loses", "lost", "weak", "weaker", "weakness", "bearish", "downgrade",
    "downgrades", "downgraded", "underperform", "miss", "misses", "missed", "cut", "cuts", "layoffs",
    "lawsuit", "sues", "probe", "investigation", "fraud", "recall", "warning", "warns", "warn", "fears",
    "fear", "concern", "concerns", "worry", "worries", "decline", "declines", "declined", "slows",
    "slowdown", "recession", "crisis", "bankruptcy", "default", "selloff", "sell-off", "lower", "worst",
    # français
    "baisse", "baisses", "chute", "chutes", "recule", "recul", "plonge", "plongeon", "perte", "pertes",
    "déficit", "faible", "baissier", "avertissement", "enquête", "procès", "fraude", "crise", "faillite",
    "ralentissement", "inquiétude", "inquiétudes", "dégringole", "décroche", "dévisse",
}

NEGATIONS = {"not", "no", "never", "without", "pas", "jamais", "sans", "aucun", "aucune"}

SEUIL_ARTICLE = 0.2    # au-delà, un titre est jugé positif ; en deçà de -0.2, négatif
SEUIL_GLOBAL = 0.1


def _mots(texte):
    return re.findall(r"[\w'’-]+", texte.lower())


def _est_negation(mot):
    return mot in NEGATIONS or mot.endswith(("n't", "n’t"))


def score_titre(texte):
    """Score d'un titre, entre -1 et +1 (0 = neutre ou aucun mot connu)."""
    mots = _mots(texte or "")
    total = 0
    nombre = 0
    for i, mot in enumerate(mots):
        if mot in MOTS_POSITIFS:
            valeur = 1
        elif mot in MOTS_NEGATIFS:
            valeur = -1
        else:
            continue
        if any(_est_negation(m) for m in mots[max(0, i - 2):i]):   # « not rising », « pas de hausse »
            valeur = -valeur
        total += valeur
        nombre += 1
    return total / (nombre + 1)   # +1 : un seul mot ne suffit pas à donner un score extrême


def etiquette(score, seuil=SEUIL_ARTICLE):
    """Traduit un score en mot : positif, négatif ou neutre."""
    if score > seuil:
        return "positif"
    if score < -seuil:
        return "négatif"
    return "neutre"


def pastille(score):
    """Petit rond de couleur pour l'affichage."""
    return {"positif": "🟢", "négatif": "🔴", "neutre": "⚪"}[etiquette(score)]


def synthese(scores):
    """Résumé d'une liste de scores : moyenne, étiquette globale et nombre de titres de chaque type.

    Renvoie None s'il n'y a aucun score.
    """
    if not scores:
        return None
    moyenne = sum(scores) / len(scores)
    etiquettes = [etiquette(s) for s in scores]
    return {
        "moyenne": moyenne,
        "etiquette": etiquette(moyenne, SEUIL_GLOBAL),
        "positifs": etiquettes.count("positif"),
        "neutres": etiquettes.count("neutre"),
        "negatifs": etiquettes.count("négatif"),
        "nombre": len(scores),
    }
