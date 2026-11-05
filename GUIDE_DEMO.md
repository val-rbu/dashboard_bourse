# Guide de démonstration (5 à 7 minutes)

Préparation, 10 minutes avant :
- lancer `streamlit run app.py` et vérifier que la page s'affiche ;
- avoir Telegram ouvert sur le téléphone ou l'ordinateur, bien visible ;
- vérifier que la liste de suivi contient 3 ou 4 actions (par exemple AAPL, MSFT, MC.PA, TTE.PA) ;
- si possible, démonstration pendant les heures d'ouverture de la bourse (Paris 9h-17h30, New York 15h30-22h, heure française) : les cours bougent ;
- prévoir une capture d'écran de chaque vue au cas où Internet tomberait.

## Déroulé

1. **Présentation (30 s)** : « Un tableau de bord pour suivre des actions, analyser leur évolution, tester des stratégies et être alerté sur Telegram. »
2. **Une action (1 min)** : cliquer sur une action de la liste, changer de période (1J, 1M, 1A, 5A), passer en chandeliers. Montrer les quatre chiffres clés.
3. **Indicateurs (1 min)** : cocher MA50, MA200 puis RSI. Lire le RSI affiché sous le graphique (surchauffe au-dessus de 70, survente en dessous de 30).
4. **Actualités (30 s)** : sous le graphique, montrer les titres avec leur pastille de sentiment (vert, gris, rouge) et cliquer sur un lien pour ouvrir l'article.
5. **Alerte et Telegram (2 min)**, le moment fort : créer une alerte de variation du jour avec un seuil très bas (0,1 %), cliquer sur « Vérifier les alertes maintenant », montrer le message reçu sur Telegram et la ligne dans l'historique.
6. **Comparaison (1 min)** : vue Comparaison, choisir 2 actions et le S&P 500, période 1A. « Laquelle a le mieux performé ? »
7. **Portefeuille (1 min)** : ajouter un achat, montrer le gain ou la perte, le camembert et le bouton d'export CSV.
8. **Backtest (1 min)** : vue Backtest, règle RSI sur 5 ans : « Aurait-on fait mieux qu'en conservant l'action ? » Montrer les achats et ventes sur le graphique et la plus forte baisse évitée (ou non).
9. **Projection (1 min)** : vue Projection, montrer la fourchette puis le test de fiabilité : « Même nous, on ne se fie pas à cette projection : voici combien de fois elle s'est trompée. »
10. **Conclusion (30 s)** : limites (données différées, usage local) et suite prévue (comptes, hébergement).

## Questions probables

- **D'où viennent les données ?** De yfinance (Yahoo Finance), gratuit mais non officiel, cours différés d'environ 15 minutes.
- **Pourquoi pas de conversion euro/dollar ?** Choix de simplicité : chaque devise est totalisée séparément.
- **Les alertes tournent-elles en permanence ?** Pas encore : vérification manuelle ou boucle sur l'ordinateur. L'hébergement est prévu en suite.
- **Où sont stockées les données ?** Dans un fichier SQLite local, `bourse.db`.
- **Comment est calculé le sentiment ?** Par un dictionnaire de mots positifs et négatifs dans les titres, avec gestion des négations. Simple et explicable, mais il ne comprend pas le contexte.
- **La projection est-elle fiable ?** Non, et l'application le mesure elle-même : elle compare la méthode à « le cours ne bouge pas » sur le passé.
- **Pourquoi la règle de backtest ne bat-elle pas toujours « conserver » ?** C'est fréquent : une règle simple limite surtout les baisses, elle ne garantit pas un meilleur rendement.
- **Est-ce un conseil financier ?** Non, c'est un outil d'aide à la décision.

## Si quelque chose plante

- Données vides : attendre une minute (limite de yfinance) et recharger la page.
- Pas de message Telegram : vérifier que `.env` existe et lancer `python notifications.py`.
- Page blanche : relancer `streamlit run app.py`.
