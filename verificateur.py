"""Vérificateur d'alertes : compare les cours actuels aux seuils des alertes actives.

Quatre types d'alertes sont gérés :
- « prix » : le cours dépasse ou passe sous un seuil ;
- « variation_jour » : le cours varie d'au moins X % par rapport à la clôture précédente ;
- « rsi » : le RSI 14 jours dépasse ou passe sous un seuil (70 = surchauffe, 30 = survente) ;
- « croisement_ma » : la moyenne mobile 50 jours croise la moyenne mobile 200 jours.

Deux façons de l'utiliser, dans le terminal :
    python verificateur.py             -> une vérification, puis le script s'arrête
    python verificateur.py --boucle    -> une vérification toutes les 5 minutes (Ctrl + C pour arrêter)

L'interface (app.py) peut aussi l'appeler avec le bouton « Vérifier maintenant ».
"""

import sys
import time

import database as db
import indicateurs as ind
from data import clotures_5ans, dernier_prix, devise, variation_jour
from notifications import envoyer_message, expliquer_erreur, telegram_configure

INTERVALLE_SECONDES = 5 * 60   # temps d'attente entre deux vérifications en mode boucle


def libelle_condition(alerte):
    """Condition d'une alerte en texte court : « ≥ 390.00 $ » ou « variation du jour ≤ −5.0 % »."""
    hausse = alerte["sens"] == "hausse"
    signe = "≥" if hausse else "≤"
    if alerte["type"] == "croisement_ma":
        return "MA50 passe au-dessus de la MA200" if hausse else "MA50 passe sous la MA200"
    if alerte["type"] == "rsi":
        return f"RSI {signe} {alerte['seuil']:.0f}"
    if alerte["type"] == "variation_jour":
        return f"variation du jour {signe} {'+' if hausse else '−'}{alerte['seuil']:.1f} %"
    return f"{signe} {alerte['seuil']:.2f} {devise(alerte['ticker'])}"


def mesurer(alerte, memoire):
    """Récupère la mesure utile à une alerte : {"cours": ..., "variation": ...}, ou None si indisponible.

    `memoire` évite de demander deux fois la même chose pour la même action.
    """
    ticker = alerte["ticker"]

    if alerte["type"] in ("rsi", "croisement_ma"):
        cle = ("serie", ticker)
        if cle not in memoire:
            memoire[cle] = clotures_5ans(ticker)
        serie = memoire[cle]
        if serie is None or serie.empty:
            return None
        mesure = {"cours": float(serie.iloc[-1]), "variation": None, "rsi": None, "croisement": None}
        if alerte["type"] == "rsi":
            valeur_rsi = ind.rsi(serie, 14).iloc[-1]
            if valeur_rsi != valeur_rsi:   # NaN : pas assez d'historique
                return None
            mesure["rsi"] = float(valeur_rsi)
        else:
            if len(serie) < 205:           # il faut 200 jours pour la MA200, plus quelques jours
                return None
            mesure["croisement"] = ind.croisement_recent(serie, 5)
        return mesure

    if alerte["type"] == "variation_jour":
        cle = ("variation", ticker)
        if cle not in memoire:
            memoire[cle] = variation_jour(ticker)
        resultat = memoire[cle]
        if resultat is None:
            return None
        return {"cours": resultat[0], "variation": resultat[1]}

    cle = ("prix", ticker)
    if cle not in memoire:
        memoire[cle] = dernier_prix(ticker)
    prix = memoire[cle]
    if prix is None:
        return None
    return {"cours": prix, "variation": None}


def condition_remplie(alerte, mesure):
    """Vrai si la mesure franchit le seuil de l'alerte, dans le bon sens."""
    hausse = alerte["sens"] == "hausse"
    if alerte["type"] == "croisement_ma":
        return mesure["croisement"] == alerte["sens"]
    if alerte["type"] == "rsi":
        return mesure["rsi"] >= alerte["seuil"] if hausse else mesure["rsi"] <= alerte["seuil"]
    if alerte["type"] == "variation_jour":
        variation = mesure["variation"]
        return variation >= alerte["seuil"] if hausse else variation <= -alerte["seuil"]
    cours = mesure["cours"]
    return cours >= alerte["seuil"] if hausse else cours <= alerte["seuil"]


def decrire(alerte, mesure):
    """Phrase lisible décrivant une alerte déclenchée."""
    ticker = alerte["ticker"]
    d = devise(ticker)
    if alerte["type"] == "croisement_ma":
        return f"{ticker} : {libelle_condition(alerte)} (croisement des 5 dernières séances, cours {mesure['cours']:.2f} {d})"
    if alerte["type"] == "rsi":
        return f"{ticker} : {libelle_condition(alerte)} atteint (RSI actuel {mesure['rsi']:.0f}, cours {mesure['cours']:.2f} {d})"
    if alerte["type"] == "variation_jour":
        return (
            f"{ticker} : {libelle_condition(alerte)} atteinte "
            f"(variation actuelle {mesure['variation']:+.2f} %, cours {mesure['cours']:.2f} {d})"
        )
    return f"{ticker} : seuil {libelle_condition(alerte)} atteint (cours actuel {mesure['cours']:.2f} {d})"


def composer_message(alerte, mesure):
    """Renvoie le texte du message Telegram d'une alerte déclenchée."""
    return (
        f"🔔 Alerte {decrire(alerte, mesure)}\n"
        f"Date et heure : {db.maintenant()}\n\n"
        "Cours différés d'environ 15 minutes. Aide à la décision, "
        "pas un conseil financier."
    )


def notifier(alerte, mesure):
    """Prévient l'utilisateur. Renvoie (réussi, information).

    - Telegram non configuré : on affiche seulement un message, l'alerte est tout de même déclenchée ;
    - Telegram configuré et message envoyé : réussi ;
    - Telegram configuré mais en échec : l'alerte reste active et sera revérifiée plus tard.
    """
    print("ALERTE  " + decrire(alerte, mesure))

    if not telegram_configure():
        print("   (Telegram non configuré : aucun message envoyé)")
        return True, "Telegram non configuré"

    try:
        envoyer_message(composer_message(alerte, mesure))
    except Exception as erreur:
        explication = expliquer_erreur(erreur)
        print("   ERREUR : " + explication)
        return False, explication

    print("   message Telegram envoyé")
    return True, "message Telegram envoyé"


def verifier_alertes():
    """Vérifie toutes les alertes actives.

    Renvoie deux listes :
    - déclenchées : (alerte, mesure, information sur la notification)
    - échecs : (alerte, mesure, explication), alertes franchies dont le message n'a pas pu partir
    """
    declenchees = []
    echecs = []
    memoire = {}

    for alerte in db.lister_alertes():
        mesure = mesurer(alerte, memoire)
        if mesure is None:   # donnée indisponible : on réessaiera à la prochaine vérification
            continue

        if condition_remplie(alerte, mesure):
            reussi, information = notifier(alerte, mesure)
            if reussi:
                db.declencher_alerte(alerte, mesure["cours"], mesure["variation"])
                declenchees.append((alerte, mesure, information))
            else:
                echecs.append((alerte, mesure, information))

    return declenchees, echecs


if __name__ == "__main__":
    db.initialiser()

    if "--boucle" in sys.argv:
        print(f"Vérification toutes les {INTERVALLE_SECONDES // 60} minutes. Ctrl + C pour arrêter.")
        while True:
            heure = time.strftime("%H:%M:%S")
            declenchees, echecs = verifier_alertes()
            print(f"[{heure}] vérification faite : {len(declenchees)} déclenchée(s), {len(echecs)} en échec")
            time.sleep(INTERVALLE_SECONDES)
    else:
        declenchees, echecs = verifier_alertes()
        print(f"Vérification faite : {len(declenchees)} déclenchée(s), {len(echecs)} en échec.")
