"""Vérificateur d'alertes : compare les cours actuels aux seuils des alertes actives.

Deux façons de l'utiliser, dans le terminal :
    python verificateur.py             -> une vérification, puis le script s'arrête
    python verificateur.py --boucle    -> une vérification toutes les 5 minutes (Ctrl + C pour arrêter)

L'interface (app.py) peut aussi l'appeler avec le bouton « Vérifier maintenant ».
"""

import sys
import time

import database as db
from data import dernier_prix, devise
from notifications import envoyer_message, expliquer_erreur, telegram_configure

INTERVALLE_SECONDES = 5 * 60   # temps d'attente entre deux vérifications en mode boucle


def condition_remplie(sens, seuil, cours):
    """Vrai si le cours a franchi le seuil dans le bon sens."""
    if sens == "hausse":
        return cours >= seuil
    return cours <= seuil


def decrire(alerte, cours):
    """Phrase lisible décrivant une alerte déclenchée."""
    signe = "≥" if alerte["sens"] == "hausse" else "≤"
    d = devise(alerte["ticker"])
    return (
        f"{alerte['ticker']} : seuil {signe} {alerte['seuil']:.2f} {d} atteint "
        f"(cours actuel {cours:.2f} {d})"
    )


def composer_message(alerte, cours):
    """Renvoie le texte du message Telegram d'une alerte déclenchée."""
    return (
        f"🔔 Alerte {decrire(alerte, cours)}\n"
        f"Date et heure : {db.maintenant()}\n\n"
        "Cours différés d'environ 15 minutes. Aide à la décision, "
        "pas un conseil financier."
    )


def notifier(alerte, cours):
    """Prévient l'utilisateur. Renvoie (réussi, information).

    - Telegram non configuré : on affiche seulement un message, l'alerte est tout de même déclenchée ;
    - Telegram configuré et message envoyé : réussi ;
    - Telegram configuré mais en échec : l'alerte reste active et sera revérifiée plus tard.
    """
    print("ALERTE  " + decrire(alerte, cours))

    if not telegram_configure():
        print("   (Telegram non configuré : aucun message envoyé)")
        return True, "Telegram non configuré"

    try:
        envoyer_message(composer_message(alerte, cours))
    except Exception as erreur:
        explication = expliquer_erreur(erreur)
        print("   ERREUR : " + explication)
        return False, explication

    print("   message Telegram envoyé")
    return True, "message Telegram envoyé"


def verifier_alertes():
    """Vérifie toutes les alertes actives.

    Renvoie deux listes :
    - déclenchées : (alerte, cours, information sur la notification)
    - échecs : (alerte, cours, explication), alertes franchies dont le message n'a pas pu partir
    """
    declenchees = []
    echecs = []
    cours_par_ticker = {}   # évite de demander deux fois le même cours

    for alerte in db.lister_alertes():
        ticker = alerte["ticker"]
        if ticker not in cours_par_ticker:
            cours_par_ticker[ticker] = dernier_prix(ticker)
        cours = cours_par_ticker[ticker]

        if cours is None:   # cours indisponible : on réessaiera à la prochaine vérification
            continue

        if condition_remplie(alerte["sens"], alerte["seuil"], cours):
            reussi, information = notifier(alerte, cours)
            if reussi:
                db.declencher_alerte(alerte, cours)
                declenchees.append((alerte, cours, information))
            else:
                echecs.append((alerte, cours, information))

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
