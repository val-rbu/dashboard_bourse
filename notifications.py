"""Notifications Telegram.

Un « bot » Telegram envoie les alertes dans ta conversation privée. Ses identifiants
ne sont JAMAIS écrits dans le code : ils sont lus dans un fichier nommé .env,
placé à côté de ce script. Contenu du fichier .env :

    TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
    TELEGRAM_CHAT_ID=123456789

Commandes utiles, dans le terminal :
    python notifications.py --chat-id    -> retrouve ton TELEGRAM_CHAT_ID
    python notifications.py              -> envoie un message de test
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

FICHIER_ENV = Path(__file__).parent / ".env"
URL_API = "https://api.telegram.org/bot{token}/{methode}"
DELAI_SECONDES = 20


class TelegramNonConfigure(Exception):
    """Levée quand le fichier .env n'existe pas ou est incomplet."""


class ErreurTelegram(Exception):
    """Erreur avec un message déjà lisible (et qui ne contient jamais le token)."""


def _lire_configuration():
    """Lit le fichier .env (à chaque appel, donc une modification est prise en compte tout de suite)."""
    load_dotenv(FICHIER_ENV, override=True)
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    return token, chat_id


def telegram_configure():
    """Vrai si le token et l'identifiant de conversation sont renseignés dans .env."""
    token, chat_id = _lire_configuration()
    return bool(token and chat_id)


def _appeler(token, methode, **parametres):
    """Appelle l'API de Telegram et renvoie le champ « result » de sa réponse.

    Le token fait partie de l'adresse appelée : on évite donc de remonter les
    messages d'erreur techniques, qui pourraient l'afficher.
    """
    try:
        reponse = requests.post(
            URL_API.format(token=token, methode=methode), data=parametres, timeout=DELAI_SECONDES
        )
    except requests.exceptions.RequestException:
        raise ErreurTelegram("Impossible de joindre Telegram. Vérifie ta connexion Internet.") from None

    try:
        donnees = reponse.json()
    except ValueError:
        raise ErreurTelegram(f"Réponse inattendue de Telegram (code {reponse.status_code}).") from None

    if not donnees.get("ok"):
        code = donnees.get("error_code")
        description = donnees.get("description", "")
        if code in (401, 404):
            message = (
                "Telegram refuse le token : vérifie TELEGRAM_BOT_TOKEN dans le fichier .env "
                "(copie-le en entier depuis BotFather, sans espace ni guillemets)."
            )
        elif code == 400 and "chat not found" in description.lower():
            message = (
                "Telegram ne trouve pas la conversation : ouvre ton bot dans Telegram, appuie sur "
                "Démarrer (ou envoie /start), puis vérifie TELEGRAM_CHAT_ID dans le fichier .env."
            )
        elif code == 403:
            message = (
                "Le bot n'a pas le droit de t'écrire : ouvre-le dans Telegram et appuie sur "
                "Démarrer (ou débloque-le)."
            )
        else:
            message = f"Telegram a répondu : {description} (code {code})."
        raise ErreurTelegram(message)

    return donnees.get("result")


def envoyer_message(texte):
    """Envoie un message dans la conversation configurée. Lève une exception en cas de problème."""
    token, chat_id = _lire_configuration()
    if not token or not chat_id:
        raise TelegramNonConfigure(
            "Telegram non configuré : il manque TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID dans le fichier .env."
        )
    _appeler(token, "sendMessage", chat_id=chat_id, text=texte)


def trouver_chat_id():
    """Renvoie {identifiant: nom} des conversations qui ont écrit récemment au bot."""
    token, _ = _lire_configuration()
    if not token:
        raise TelegramNonConfigure("Il manque TELEGRAM_BOT_TOKEN dans le fichier .env.")

    conversations = {}
    for mise_a_jour in _appeler(token, "getUpdates") or []:
        message = mise_a_jour.get("message") or mise_a_jour.get("channel_post") or {}
        chat = message.get("chat")
        if chat:
            nom = chat.get("first_name") or chat.get("title") or chat.get("username") or "(sans nom)"
            conversations[chat["id"]] = nom
    return conversations


def expliquer_erreur(erreur):
    """Renvoie une explication lisible, sans jamais afficher le token."""
    if isinstance(erreur, (TelegramNonConfigure, ErreurTelegram)):
        return str(erreur)
    return f"Erreur inattendue ({type(erreur).__name__})."


if __name__ == "__main__":
    try:
        if "--chat-id" in sys.argv:
            conversations = trouver_chat_id()
            if not conversations:
                print(
                    "Aucun message trouvé. Ouvre ton bot dans Telegram, envoie-lui « bonjour », "
                    "puis relance cette commande."
                )
            for identifiant, nom in conversations.items():
                print(f"Conversation avec {nom} : TELEGRAM_CHAT_ID={identifiant}")
        else:
            print("Envoi d'un message de test...")
            envoyer_message("Test du tableau de bord financier : les notifications Telegram fonctionnent.")
            print("Message envoyé. Regarde ton Telegram.")
    except Exception as erreur:
        print("ÉCHEC : " + expliquer_erreur(erreur))
