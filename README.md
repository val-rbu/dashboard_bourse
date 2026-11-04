# Tableau de bord financier

Application web qui permet de suivre des actions françaises et américaines, de voir l'évolution de leur cours et d'être prévenu par Telegram quand un seuil de prix est franchi. Projet de cours en Python.

> Les cours sont différés d'environ 15 minutes et viennent de `yfinance` (non officiel). L'outil est une aide à la décision et ne constitue pas un conseil financier.

## Fonctionnalités

- Liste de suivi sauvegardée (ajout et retrait d'actions par ticker, par exemple `AAPL` ou `MC.PA`)
- Graphiques interactifs en courbe ou en chandeliers, sur 1 jour, 1 mois, 1 an ou 5 ans
- Alertes à seuil de prix (au-dessus ou en dessous), affichées sur le graphique
- Historique des alertes déclenchées
- Notifications Telegram

## Installation (Windows)

Prérequis : Python 3 et VS Code. Le projet a été développé avec Python 3.15.

Dans un terminal, depuis le dossier du projet :

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration de Telegram

1. Dans Telegram, créer un bot avec **@BotFather** (commande `/newbot`) et récupérer son token.
2. Ouvrir le bot et appuyer sur **Démarrer**.
3. Copier `.env.example` en `.env` et y mettre le token.
4. Lancer `python notifications.py --chat-id` pour retrouver `TELEGRAM_CHAT_ID`, puis le copier dans `.env`.
5. Tester avec `python notifications.py` : un message doit arriver dans Telegram.

Le fichier `.env` contient des secrets : il ne doit jamais être publié.

## Utilisation

```
streamlit run app.py                  # lancer l'application
python verificateur.py                # vérifier les alertes une fois
python verificateur.py --boucle       # vérifier les alertes toutes les 5 minutes
```

## Organisation du code

| Fichier | Rôle |
|---|---|
| `app.py` | Interface Streamlit |
| `data.py` | Récupération des cours |
| `database.py` | Base SQLite (liste de suivi, alertes, historique) |
| `verificateur.py` | Vérification des alertes |
| `notifications.py` | Envoi des messages Telegram |

La base de données `bourse.db` est créée automatiquement au premier lancement.

## Suite prévue

- Version 2 : indicateurs techniques (moyennes mobiles, RSI), alertes en pourcentage, portefeuille, comparaison d'actions
- Version 3 : actualités, score de sentiment, backtesting, prédiction simple, comptes utilisateurs