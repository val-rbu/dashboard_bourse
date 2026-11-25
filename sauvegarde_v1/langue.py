"""Langue de l'interface : français (par défaut) ou anglais.

Tous les textes affichés par app.py passent par t("texte en français").
- En français, le texte est renvoyé tel quel.
- En anglais, on cherche sa traduction dans le dictionnaire EN ci-dessous
  (si elle manque, le texte reste en français plutôt que de planter).

Les textes avec des valeurs variables s'écrivent avec des {accolades} :
    t("Retirer {ticker}", ticker="AAPL")

Ce fichier ne dépend pas de Streamlit. Les messages Telegram restent en français.
"""

import re

LANGUE = "fr"   # "fr" ou "en", choisi par app.py à chaque affichage


def t(phrase, /, **valeurs):
    """Texte traduit dans la langue choisie, avec les {valeurs} remplacées."""
    if LANGUE == "en":
        phrase = EN.get(phrase, phrase)
    return phrase.format(**valeurs) if valeurs else phrase


def depuis(texte):
    """Traduit l'âge d'un article (« il y a 3 h », « le 28/10 ») produit par actualites.depuis."""
    if LANGUE != "en" or not texte:
        return texte
    for motif, remplacement in (
        (r"^il y a (\d+) min$", r"\1 min ago"),
        (r"^il y a (\d+) h$", r"\1 h ago"),
        (r"^il y a (\d+) j$", r"\1 d ago"),
        (r"^le (.+)$", r"on \1"),
    ):
        if re.match(motif, texte):
            return re.sub(motif, remplacement, texte)
    return texte


def libelle_condition(alerte, symbole_devise):
    """Condition d'une alerte en texte court (même contenu que verificateur.libelle_condition)."""
    hausse = alerte["sens"] == "hausse"
    signe = "≥" if hausse else "≤"
    if alerte["type"] == "volume_anormal":
        return t("volume ≥ {x:.1f} × la moyenne", x=alerte["seuil"])
    if alerte["type"] == "croisement_ma":
        return t("MA50 passe au-dessus de la MA200") if hausse else t("MA50 passe sous la MA200")
    if alerte["type"] == "rsi":
        return f"RSI {signe} {alerte['seuil']:.0f}"
    if alerte["type"] == "variation_jour":
        return t("variation du jour {signe} {s}{x:.1f} %", signe=signe, s="+" if hausse else "−", x=alerte["seuil"])
    return f"{signe} {alerte['seuil']:.2f} {symbole_devise}"


def decrire(alerte, mesure, symbole_devise):
    """Phrase décrivant une alerte déclenchée (même contenu que verificateur.decrire)."""
    ticker, d = alerte["ticker"], symbole_devise
    cond = libelle_condition(alerte, d)
    if alerte["type"] == "volume_anormal":
        return t("{ticker} : {cond} atteint (volume du jour {v:.1f} × la moyenne, cours {c:.2f} {d})",
                 ticker=ticker, cond=cond, v=mesure["volume_ratio"], c=mesure["cours"], d=d)
    if alerte["type"] == "croisement_ma":
        return t("{ticker} : {cond} (croisement des 5 dernières séances, cours {c:.2f} {d})",
                 ticker=ticker, cond=cond, c=mesure["cours"], d=d)
    if alerte["type"] == "rsi":
        return t("{ticker} : {cond} atteint (RSI actuel {r:.0f}, cours {c:.2f} {d})",
                 ticker=ticker, cond=cond, r=mesure["rsi"], c=mesure["cours"], d=d)
    if alerte["type"] == "variation_jour":
        return t("{ticker} : {cond} atteinte (variation actuelle {v:+.2f} %, cours {c:.2f} {d})",
                 ticker=ticker, cond=cond, v=mesure["variation"], c=mesure["cours"], d=d)
    return t("{ticker} : seuil {cond} atteint (cours actuel {c:.2f} {d})", ticker=ticker, cond=cond, c=mesure["cours"], d=d)


EN = {
    # --- En-tête, réglages, onglets
    "Tableau de bord financier": "Financial dashboard",
    "Cours différés d'environ 15 minutes · source : yfinance": "Prices delayed by about 15 minutes · source: yfinance",
    "Cours différé d'environ 15 minutes · source : yfinance": "Price delayed by about 15 minutes · source: yfinance",
    "Thème": "Theme",
    "Langue": "Language",
    "☀️ Clair": "☀️ Light",
    "🌙 Sombre": "🌙 Dark",
    "Vue": "View",
    "Une action": "Stock",
    "Comparaison": "Comparison",
    "Portefeuille": "Portfolio",
    "Backtest": "Backtest",
    "Projection": "Projection",
    # --- Devises
    "Devise d'affichage": "Display currency",
    "Devise d'origine": "Original currency",
    "Euro (€)": "Euro (€)",
    "Dollar ($)": "US dollar ($)",
    "Livre sterling (£)": "Pound sterling (£)",
    "Yen japonais (¥)": "Japanese yen (¥)",
    "Yuan chinois (CN¥)": "Chinese yuan (CN¥)",
    "{a} = {x:.4f} {b} · taux actuel": "{a} = {x:.4f} {b} · current rate",
    "Taux de change indisponible : prix affichés dans leur devise d'origine.":
        "Exchange rate unavailable: prices shown in their original currency.",
    # --- Périodes
    "1J": "1D", "1S": "1W", "1M": "1M", "1A": "1Y", "3A": "3Y", "5A": "5Y",
    "Période": "Period",
    "Type de graphique": "Chart type",
    "Courbe": "Line",
    "Chandeliers": "Candles",
    # --- Liste de suivi
    "Ma liste de suivi": "My watchlist",
    "{n} valeur": "{n} stock",
    "{n} valeurs": "{n} stocks",
    "Choisir {ticker}": "Select {ticker}",
    "Retirer {ticker}": "Remove {ticker}",
    "+ Ajouter une action": "+ Add a stock",
    "Tape son nom ou son ticker": "Type its name or ticker",
    "ex. Apple, LVMH, NVDA...": "e.g. Apple, LVMH, NVDA...",
    "Rechercher": "Search",
    "Nom ou ticker, puis Entrée": "Name or ticker, then Enter",
    "Résultats": "Results",
    "Aucun résultat.": "No results.",
    "Choix non reconnu : recommence la recherche.": "Choice not recognised: search again.",
    "{ticker} est déjà dans ta liste.": "{ticker} is already in your list.",
    "Ajouter {ticker}": "Add {ticker}",
    "Aucune donnée de cours pour {ticker} : essaie une autre valeur.": "No price data for {ticker}: try another stock.",
    "indisponible": "unavailable",
    # --- Portefeuille
    "Mon portefeuille": "My portfolio",
    "Action": "Stock",
    "Quantité": "Quantity",
    "Prix d'achat ({d})": "Purchase price ({d})",
    "Ajouter l'achat": "Add purchase",
    "Achat de {q:g} {ticker} enregistré.": "Purchase of {q:g} {ticker} saved.",
    "Ajoute d'abord une action à ta liste de suivi pour pouvoir l'acheter ici.":
        "First add a stock to your watchlist to be able to buy it here.",
    "Ton portefeuille est vide : enregistre un achat ci-dessus.": "Your portfolio is empty: record a purchase above.",
    "Valeur actuelle ({d})": "Current value ({d})",
    "Investi ({d})": "Invested ({d})",
    "Gain ou perte ({d})": "Gain or loss ({d})",
    "Prix d'achat moyen": "Average purchase price",
    "Cours actuel": "Current price",
    "Valeur": "Value",
    "Gain ou perte": "Gain or loss",
    "Télécharger le portefeuille (CSV)": "Download portfolio (CSV)",
    "Répartition ({d})": "Allocation ({d})",
    "Détail des achats": "Purchase details",
    "**{ticker}** · {q:g} à {p:.2f} {d} · {date}": "**{ticker}** · {q:g} at {p:.2f} {d} · {date}",
    "Supprimer cet achat": "Delete this purchase",
    "sans conversion de devise : chaque devise est totalisée séparément (choisis une devise en haut à droite pour tout additionner)":
        "no currency conversion: each currency is totalled separately (pick a currency at the top right to add everything up)",
    "tout est converti en {d} au taux de change du jour (le prix d'achat aussi : l'effet du change sur ton gain n'est pas isolé)":
        "everything is converted to {d} at today's exchange rate (the purchase price too: the currency effect on your gain is not isolated)",
    "Valeurs au dernier cours connu (différé), sans frais, {note}. Aide à la décision, pas un conseil financier.":
        "Values at the last known (delayed) price, without fees, {note}. Decision aid, not financial advice.",
    # --- Comparaison
    "Comparaison de performance": "Performance comparison",
    "Actions et indices à comparer": "Stocks and indices to compare",
    "Choisis au moins deux actions ou indices à comparer.": "Pick at least two stocks or indices to compare.",
    "Données indisponibles pour : {liste}": "Data unavailable for: {liste}",
    "Pas assez de données communes pour comparer. Réessaie dans une minute.":
        "Not enough common data to compare. Try again in a minute.",
    "Performance comparée (base 100) · {p}": "Compared performance (base 100) · {p}",
    "Base 100 au départ": "Base 100 at start",
    "Performance": "Performance",
    "Départ commun : {date}. ": "Common start: {date}. ",
    "Heures en temps universel (UTC) ; Paris et New York n'ouvrent pas aux mêmes heures : une courbe reste plate quand sa bourse est fermée. ":
        "Times in UTC; Paris and New York do not open at the same hours: a curve stays flat while its market is closed. ",
    "Les performances sont calculées sur les cours, sans dividendes (la devise d'affichage ne change pas une performance en %). Aide à la décision, pas un conseil financier.":
        "Performance is based on prices, without dividends (the display currency does not change a % performance). Decision aid, not financial advice.",
    "Ta liste de suivi est vide : ajoute une action dans la colonne de gauche.":
        "Your watchlist is empty: add a stock in the left column.",
    # --- Backtest
    "Backtest · {ticker}": "Backtest · {ticker}",
    "Que se serait-il passé si on avait appliqué une règle d'achat et de vente dans le passé ?":
        "What would have happened if a buy-and-sell rule had been applied in the past?",
    "Règle": "Rule",
    "RSI : acheter en survente, vendre en surchauffe": "RSI: buy when oversold, sell when overbought",
    "Croisement de moyennes mobiles": "Moving average crossover",
    "Acheter quand le RSI passe sous": "Buy when RSI falls below",
    "Vendre quand le RSI dépasse": "Sell when RSI rises above",
    "Moyenne courte (jours)": "Short average (days)",
    "Moyenne longue (jours)": "Long average (days)",
    "La moyenne courte doit être plus petite que la longue.": "The short average must be smaller than the long one.",
    "Frais par achat ou vente (%)": "Fees per buy or sell (%)",
    "Période testée": "Tested period",
    "Historique trop court pour tester une règle sur cette action.": "History too short to test a rule on this stock.",
    "Avec la règle": "With the rule",
    "{x:+.1f} pts vs conserver": "{x:+.1f} pts vs holding",
    "Acheter et conserver": "Buy and hold",
    "Transactions": "Trades",
    "{x:.0f} % gagnantes": "{x:.0f} % winners",
    "aucune terminée": "none closed",
    "Plus forte baisse": "Maximum drawdown",
    "{x:.1f} % si conservé": "{x:.1f} % if held",
    "Achat": "Buy",
    "Vente": "Sell",
    "{ticker} · valeur d'un capital de 100 · {p}": "{ticker} · value of a capital of 100 · {p}",
    "Capital (base 100)": "Capital (base 100)",
    "Prix d'achat": "Buy price",
    "en cours": "open",
    "Prix de vente": "Sell price",
    " (dernier cours)": " (last price)",
    "Résultat": "Result",
    "Télécharger les transactions (CSV)": "Download trades (CSV)",
    "La règle n'a déclenché aucune transaction sur cette période.": "The rule did not trigger any trade over this period.",
    "Temps passé investi : {x:.0f} % de la période. Achats et ventes au cours de clôture du jour du signal, capital entièrement investi, sans impôts ni dividendes. Le passé ne garantit pas l'avenir, et une règle réglée après coup sur un historique donné peut paraître meilleure qu'elle ne le sera vraiment. Aide à la décision, pas un conseil financier.":
        "Time invested: {x:.0f} % of the period. Buys and sells at the closing price on the signal day, capital fully invested, no taxes or dividends. The past does not guarantee the future, and a rule tuned after the fact on a given history may look better than it really is. Decision aid, not financial advice.",
    # --- Projection
    "Projection de tendance · {ticker}": "Trend projection · {ticker}",
    "Ce n'est pas une prévision : la projection prolonge simplement la tendance récente. La mesure de fiabilité ci-dessous montre à quel point elle s'est trompée dans le passé.":
        "This is not a forecast: the projection simply extends the recent trend. The reliability check below shows how wrong it has been in the past.",
    "Historique utilisé pour la tendance": "History used for the trend",
    "6 mois": "6 months", "1 an": "1 year", "3 ans": "3 years",
    "Horizon de projection": "Projection horizon",
    "{j} jours": "{j} days",
    "Historique trop court pour cette combinaison. Choisis un historique ou un horizon plus petit.":
        "History too short for this combination. Pick a shorter history or horizon.",
    "Dernier cours": "Last price",
    "Projection à {j} jours": "{j}-day projection",
    "Fourchette à 95 %": "95 % range",
    "Cours": "Price",
    "Haut 95 %": "High 95 %",
    "{ticker} · projection sur {j} jours": "{ticker} · {j}-day projection",
    "Prix ({d})": "Price ({d})",
    "Cette méthode s'est-elle déjà trompée ?": "Has this method been wrong before?",
    "Historique insuffisant pour mesurer la fiabilité.": "Not enough history to measure reliability.",
    "Cours réel dans la fourchette": "Actual price within range",
    "objectif : environ 95 %": "target: about 95 %",
    "Erreur moyenne de la projection": "Average projection error",
    "Erreur si « le cours ne bouge pas »": "Error if \"the price does not move\"",
    "Sur cet historique, prolonger la tendance a fait un peu mieux que supposer que le cours ne bouge pas.":
        "On this history, extending the trend did slightly better than assuming the price does not move.",
    "Sur cet historique, prolonger la tendance n'a pas fait mieux que supposer que le cours ne bouge pas.":
        "On this history, extending the trend did no better than assuming the price does not move.",
    "{verdict} Test rejoué sur {n} dates du passé, avec les seules données connues à l'époque. Les cours sont en grande partie imprévisibles à court terme : ne pas se fier à cette projection pour décider. Aide à la décision, pas un conseil financier.":
        "{verdict} Test replayed on {n} past dates, using only the data known at the time. Prices are largely unpredictable in the short term: do not rely on this projection to decide. Decision aid, not financial advice.",
    # --- Vue Une action : graphique
    "Les indicateurs utilisent des clôtures journalières : choisis une période de 1M ou plus.":
        "Indicators use daily closes: pick a period of 1M or more.",
    "Impossible de récupérer les cours pour le moment. Réessaie dans une minute.":
        "Unable to fetch prices right now. Try again in a minute.",
    "({x:+.2f} % sur la période)": "({x:+.2f} % over the period)",
    "Historique indisponible : les indicateurs ne peuvent pas être calculés.":
        "History unavailable: indicators cannot be calculated.",
    "Cours de clôture": "Closing price",
    "Bollinger haut": "Upper Bollinger",
    "Bandes de Bollinger": "Bollinger Bands",
    "Histogramme MACD": "MACD histogram",
    "Signal": "Signal",
    "Seuil d'alerte {signe} {x:.2f} {d}": "Alert threshold {signe} {x:.2f} {d}",
    "Début de période": "Period start",
    "Plus haut": "High",
    "Plus bas": "Low",
    "Volume cumulé": "Total volume",
    # --- Indicateurs techniques
    "Indicateurs techniques": "Technical indicators",
    "RSI (14 jours)": "RSI (14 days)",
    "n.d.": "n/a",
    "Survente": "Oversold",
    "Surchauffe": "Overbought",
    "Neutre": "Neutral",
    "Survente 30": "Oversold 30",
    "Surchauffe 70": "Overbought 70",
    "Moyennes mobiles": "Moving averages",
    "▲ Tendance haussière": "▲ Uptrend",
    "▼ Tendance baissière": "▼ Downtrend",
    "Moins de 200 jours d'historique": "Less than 200 days of history",
    "Volume vs moyenne 20 jours": "Volume vs 20-day average",
    "Volume élevé": "High volume",
    "Volume faible": "Low volume",
    "Dans la norme": "Normal",
    "RSI actuel : {x:.0f} · {texte}.": "Current RSI: {x:.0f} · {texte}.",
    "MACD : {texte}.": "MACD: {texte}.",
    "Bandes de Bollinger : cours {texte}.": "Bollinger Bands: price {texte}.",
    "MA200 indisponible : cette action n'a pas encore 200 jours d'historique.":
        "MA200 unavailable: this stock does not have 200 days of history yet.",
    # Textes venant de indicateurs.py
    "survente (moins de 30)": "oversold (below 30)",
    "surchauffe (plus de 70)": "overbought (above 70)",
    "zone neutre (entre 30 et 70)": "neutral zone (between 30 and 70)",
    "MACD au-dessus de sa ligne de signal : élan haussier": "MACD above its signal line: bullish momentum",
    "MACD sous sa ligne de signal : élan baissier": "MACD below its signal line: bearish momentum",
    "au-dessus de la bande haute (cours tendu vers le haut)": "above the upper band (stretched upwards)",
    "sous la bande basse (cours tendu vers le bas)": "below the lower band (stretched downwards)",
    "proche de la bande haute": "close to the upper band",
    "proche de la bande basse": "close to the lower band",
    "au milieu des bandes": "in the middle of the bands",
    # --- Actualités
    "Actualités · {ticker}": "News · {ticker}",
    "Aucune actualité disponible pour le moment (la source peut être indisponible).":
        "No news available right now (the source may be unavailable).",
    "Sentiment : **{e}** ({m:+.2f})": "Sentiment: **{e}** ({m:+.2f})",
    "positif": "positive", "négatif": "negative", "neutre": "neutral",
    "Articles en général en anglais (Yahoo Finance). Le sentiment est un simple décompte de mots positifs et négatifs dans le titre : indicatif.":
        "Articles from Yahoo Finance. Sentiment is a simple count of positive and negative words in the headline: indicative only.",
    # --- Alertes
    "Alertes actives": "Active alerts",
    "Aucune alerte pour le moment.": "No alerts yet.",
    "Supprimer cette alerte": "Delete this alert",
    "Vérifier les alertes maintenant": "Check alerts now",
    "Alerte déclenchée · {texte} ({info})": "Alert triggered · {texte} ({info})",
    "Seuil franchi · {texte}, mais le message Telegram n'est pas parti : {explication} L'alerte reste active.":
        "Threshold crossed · {texte}, but the Telegram message was not sent: {explication} The alert stays active.",
    "Vérification faite : aucun seuil n'est franchi.": "Check done: no threshold crossed.",
    "Notifications Telegram : activées.": "Telegram notifications: on.",
    "Notifications Telegram : non configurées (fichier .env à créer).": "Telegram notifications: not set up (.env file needed).",
    "＋ Nouvelle alerte sur {ticker}": "＋ New alert on {ticker}",
    "Les alertes de prix restent exprimées en {d}, la devise de cotation de {ticker}.":
        "Price alerts stay in {d}, the trading currency of {ticker}.",
    "Type d'alerte": "Alert type",
    "Prix": "Price",
    "Variation du jour (%)": "Daily change (%)",
    "Croisement MA50/MA200": "MA50/MA200 crossover",
    "Volume anormal": "Unusual volume",
    "Prévenez-moi quand l'action est": "Notify me when the stock is",
    "en surchauffe (RSI au-dessus de)": "overbought (RSI above)",
    "en survente (RSI en dessous de)": "oversold (RSI below)",
    "Seuil du RSI": "RSI threshold",
    "Volume du jour au moins égal à (× la moyenne des 20 derniers jours)": "Today's volume at least (× the 20-day average)",
    "Le volume du jour est partiel tant que la bourse est ouverte : l'alerte peut partir en fin de séance.":
        "Today's volume is partial while the market is open: the alert may fire at the end of the session.",
    "Prévenez-moi quand": "Notify me when",
    "la MA50 passe au-dessus de la MA200": "the MA50 crosses above the MA200",
    "la MA50 passe sous la MA200": "the MA50 crosses below the MA200",
    "Alerte envoyée si le croisement a eu lieu pendant les 5 dernières séances.":
        "Alert sent if the crossover happened during the last 5 sessions.",
    "Prévenez-moi quand le cours est": "Notify me when the price is",
    "au-dessus de": "above",
    "en dessous de": "below",
    "Seuil ({d})": "Threshold ({d})",
    "Prévenez-moi quand l'action": "Notify me when the stock",
    "monte d'au moins": "rises by at least",
    "baisse d'au moins": "falls by at least",
    "Variation sur la journée (%)": "Change over the day (%)",
    "Créer l'alerte": "Create alert",
    "Alerte créée sur {ticker}.": "Alert created on {ticker}.",
    "Cette condition est déjà remplie actuellement : l'alerte se déclenchera à la prochaine vérification.":
        "This condition is already met: the alert will fire at the next check.",
    "Alertes déclenchées": "Triggered alerts",
    "Date": "Date",
    "Condition": "Condition",
    "Cours au déclenchement": "Price when triggered",
    "Télécharger l'historique (CSV)": "Download history (CSV)",
    "Aucune alerte déclenchée pour le moment.": "No alerts triggered yet.",
    "Outil d'aide à la décision, ne constitue pas un conseil financier.": "Decision-support tool, not financial advice.",
    # Conditions et descriptions d'alertes
    "volume ≥ {x:.1f} × la moyenne": "volume ≥ {x:.1f} × average",
    "MA50 passe au-dessus de la MA200": "MA50 crosses above MA200",
    "MA50 passe sous la MA200": "MA50 crosses below MA200",
    "variation du jour {signe} {s}{x:.1f} %": "daily change {signe} {s}{x:.1f} %",
    "{ticker} : {cond} atteint (volume du jour {v:.1f} × la moyenne, cours {c:.2f} {d})":
        "{ticker}: {cond} reached (today's volume {v:.1f} × average, price {c:.2f} {d})",
    "{ticker} : {cond} (croisement des 5 dernières séances, cours {c:.2f} {d})":
        "{ticker}: {cond} (crossover in the last 5 sessions, price {c:.2f} {d})",
    "{ticker} : {cond} atteint (RSI actuel {r:.0f}, cours {c:.2f} {d})":
        "{ticker}: {cond} reached (current RSI {r:.0f}, price {c:.2f} {d})",
    "{ticker} : {cond} atteinte (variation actuelle {v:+.2f} %, cours {c:.2f} {d})":
        "{ticker}: {cond} reached (current change {v:+.2f} %, price {c:.2f} {d})",
    "{ticker} : seuil {cond} atteint (cours actuel {c:.2f} {d})":
        "{ticker}: threshold {cond} reached (current price {c:.2f} {d})",
}
