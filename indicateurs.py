"""Indicateurs techniques, calculés à partir d'une série de cours de clôture.

Une « série » est une colonne de tableau pandas : une valeur par jour, avec la date
comme repère (par exemple cours["Close"]). Chaque fonction renvoie une série de
même longueur. Les premières valeurs sont vides (NaN) quand il n'y a pas encore
assez de jours pour calculer l'indicateur.
"""


def moyenne_mobile(cloture, fenetre):
    """Moyenne des `fenetre` dernières clôtures (ex. 50 jours pour la MA50).

    Elle lisse les variations quotidiennes et montre la tendance de fond :
    un cours au-dessus de sa moyenne mobile est souvent signe de tendance haussière.
    """
    return cloture.rolling(fenetre).mean()


def rsi(cloture, periode=14):
    """RSI (Relative Strength Index), un nombre entre 0 et 100.

    Il compare la force des hausses récentes à celle des baisses :
    - au-dessus de 70 : l'action a beaucoup monté, on parle de surchauffe ;
    - en dessous de 30 : elle a beaucoup baissé, on parle de survente ;
    - entre les deux : zone neutre.

    Calcul de Wilder : on lisse la moyenne des gains et celle des pertes
    sur `periode` jours, puis RSI = 100 - 100 / (1 + gain moyen / perte moyenne).
    """
    variation = cloture.diff()                  # écart avec la veille
    gains = variation.clip(lower=0)             # on garde les hausses (0 sinon)
    pertes = -variation.clip(upper=0)           # on garde les baisses, en positif

    # Moyenne lissée de Wilder : moyenne exponentielle de coefficient 1 / periode
    gain_moyen = gains.ewm(alpha=1 / periode, min_periods=periode, adjust=False).mean()
    perte_moyenne = pertes.ewm(alpha=1 / periode, min_periods=periode, adjust=False).mean()

    force = gain_moyen / perte_moyenne
    return 100 - 100 / (1 + force)


def interpreter_rsi(valeur):
    """Traduit une valeur de RSI en texte."""
    if valeur < 30:
        return "survente (moins de 30)"
    if valeur > 70:
        return "surchauffe (plus de 70)"
    return "zone neutre (entre 30 et 70)"
