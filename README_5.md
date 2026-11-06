# Tableau de bord financier

Application web qui permet de suivre des actions françaises et américaines, de voir l'évolution de leur cours d'analyser leur évolution (indicateurs, comparaison, portefeuille) et d'être prévenu par Telegram quand une alerte se déclenche. Projet de cours en Python.

> Les cours sont différés d'environ 15 minutes et viennent de `yfinance` (non officiel). L'outil est une aide à la décision et ne constitue pas un conseil financier.

## Fonctionnalités

**Suivi d'une action**
- Liste de suivi sauvegardée (ajout et retrait ; recherche par nom ou par ticker, avec une liste de propositions qui se met à jour pendant la frappe, par exemple « apple », « lvmh » ou `NVDA`), avec dernier cours et variation du jour
- Devise d'affichage au choix (devise d'origine, euro ou dollar) : prix, graphiques, comparaison, projection et portefeuille sont convertis avec le taux de change de chaque jour
- Graphiques interactifs en courbe ou en chandeliers, sur 1 jour, 1 mois, 1 an ou 5 ans
- Indicateurs techniques : moyennes mobiles 50 et 200 jours, bandes de Bollinger, RSI 14 jours, MACD

**Alertes** (une alerte se déclenche une fois, puis passe dans l'historique)
- Seuil de prix, au-dessus ou en dessous (affiché sur le graphique)
- Variation du jour en pourcentage
- RSI en surchauffe ou en survente
- Croisement des moyennes mobiles MA50 / MA200 (sur les 5 dernières séances)
- Volume anormal (volume du jour égal à X fois la moyenne des 20 derniers jours)
- Notifications Telegram

**Comparaison** : plusieurs actions et indices (CAC 40, S&P 500) sur un même graphique en base 100, avec classement des performances.

**Portefeuille** : saisie des achats, prix d'achat moyen, valeur actuelle, gain ou perte par action et au total (par devise), répartition.

**Actualités** : derniers articles par action, avec lien vers l'article d'origine et un score de sentiment des titres (méthode du dictionnaire, indicatif).

**Backtest** : simulation d'une règle d'achat et de vente sur 1, 3 ou 5 ans (RSI ou croisement de moyennes mobiles), comparée à « acheter et conserver », avec frais, transactions et plus forte baisse.

**Projection** : prolongement de la tendance récente avec une fourchette à 95 %, accompagné d'un test de fiabilité rejoué sur le passé (la méthode est comparée à « le cours ne bouge pas »).

**Export** : portefeuille, historique des alertes et transactions du backtest en CSV, lisibles directement dans Excel.

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
| `indicateurs.py` | Moyennes mobiles, RSI, MACD, Bollinger, volume, croisements |
| `comparaison.py` | Courbes de base 100 |
| `portefeuille.py` | Calculs de valeur et de gain |
| `actualites.py` | Mise en forme des actualités et liens |
| `sentiment.py` | Score de sentiment des titres |
| `backtest.py` | Simulation de règles d'achat et de vente |
| `projection.py` | Projection de tendance et évaluation |
| `export.py` | Export CSV |
| `devises.py` | Conversion euro / dollar |
| `recherche.py` | Recherche d'actions par nom |
| `database.py` | Base SQLite (liste de suivi, alertes, historique, portefeuille) |
| `verificateur.py` | Vérification des alertes |
| `notifications.py` | Envoi des messages Telegram |

La base de données `bourse.db` est créée automatiquement au premier lancement.

## Limites connues

- Les alertes ne sont vérifiées que lorsqu'on clique sur « Vérifier les alertes maintenant » ou qu'on laisse tourner `python verificateur.py --boucle` sur l'ordinateur.
- L'application tourne en local : la base SQLite et le fichier `.env` restent sur la machine.
- Les cours viennent de `yfinance`, un service non officiel qui peut être indisponible ou changer.
- Le sentiment compte des mots : il ne comprend ni le contexte ni l'ironie.
- La projection et le backtest sont des outils d'analyse : le passé ne garantit pas l'avenir, et les cours sont en grande partie imprévisibles à court terme.
- La conversion de devise gère l'euro et le dollar (taux EUR/USD de Yahoo Finance). Les alertes de prix restent exprimées dans la devise de cotation. Sans conversion choisie, le portefeuille totalise chaque devise séparément.

## Suite prévue

- Comptes multi-utilisateurs
- Vérification automatique en continu, hébergement
