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


def croisement_recent(cloture, jours=5):
    """Cherche un croisement MA50 / MA200 pendant les `jours` dernières séances.

    Renvoie :
    - "hausse" : la MA50 est passée au-dessus de la MA200 (« croisement doré », signal haussier) ;
    - "baisse" : la MA50 est passée sous la MA200 (« croisement de la mort », signal baissier) ;
    - None     : pas de croisement récent (ou pas assez d'historique).
    Si les deux se sont produits, c'est le plus récent qui compte.
    """
    ecart = (moyenne_mobile(cloture, 50) - moyenne_mobile(cloture, 200)).dropna()
    if len(ecart) < jours + 1:
        return None
    veille = ecart.shift(1)
    monte = (veille <= 0) & (ecart > 0)
    descend = (veille >= 0) & (ecart < 0)
    for date in reversed(ecart.index[-jours:]):
        if monte[date]:
            return "hausse"
        if descend[date]:
            return "baisse"
    return None


def macd(cloture, rapide=12, lente=26, signal=9):
    """MACD (Moving Average Convergence Divergence) : mesure l'élan de la tendance.

    - ligne MACD = moyenne mobile exponentielle rapide (12 jours) - lente (26 jours) ;
    - ligne de signal = moyenne exponentielle de la ligne MACD sur 9 jours ;
    - histogramme = MACD - signal.
    Quand la ligne MACD passe au-dessus de sa ligne de signal, l'élan devient haussier ;
    quand elle passe en dessous, il devient baissier.
    Renvoie les trois séries : (macd, signal, histogramme).
    """
    ligne = cloture.ewm(span=rapide, adjust=False).mean() - cloture.ewm(span=lente, adjust=False).mean()
    ligne_signal = ligne.ewm(span=signal, adjust=False).mean()
    return ligne, ligne_signal, ligne - ligne_signal


def interpreter_macd(valeur_macd, valeur_signal):
    """Traduit la position du MACD par rapport à son signal en texte."""
    if valeur_macd > valeur_signal:
        return "MACD au-dessus de sa ligne de signal : élan haussier"
    return "MACD sous sa ligne de signal : élan baissier"


def bollinger(cloture, fenetre=20, ecarts=2):
    """Bandes de Bollinger : une enveloppe autour de la moyenne mobile 20 jours.

    La bande haute (et la basse) se situe à 2 écarts-types au-dessus (en dessous) de la moyenne.
    L'enveloppe s'élargit quand le cours devient volatil et se resserre quand il est calme.
    Un cours qui touche la bande haute est « tendu » vers le haut ; vers le bas pour la bande basse.
    Renvoie (milieu, bande haute, bande basse).
    """
    milieu = cloture.rolling(fenetre).mean()
    ecart_type = cloture.rolling(fenetre).std(ddof=0)
    return milieu, milieu + ecarts * ecart_type, milieu - ecarts * ecart_type


def interpreter_bollinger(cours, bas, haut):
    """Situe le dernier cours par rapport aux bandes."""
    if cours > haut:
        return "au-dessus de la bande haute (cours tendu vers le haut)"
    if cours < bas:
        return "sous la bande basse (cours tendu vers le bas)"
    position = (cours - bas) / (haut - bas) if haut > bas else 0.5
    if position > 0.8:
        return "proche de la bande haute"
    if position < 0.2:
        return "proche de la bande basse"
    return "au milieu des bandes"


def rapport_volume(volumes, fenetre=20):
    """Volume du dernier jour divisé par la moyenne des `fenetre` jours précédents (None si impossible).

    Un rapport de 2 signifie « deux fois plus d'échanges que d'habitude » : souvent le signe
    d'une nouvelle importante ou d'un mouvement de fond.
    """
    volumes = volumes.dropna()
    if len(volumes) < fenetre + 1:
        return None
    moyenne = volumes.iloc[-fenetre - 1:-1].mean()
    if moyenne <= 0:
        return None
    return float(volumes.iloc[-1] / moyenne)
