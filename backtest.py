"""Backtest : que se serait-il passé si on avait appliqué une règle d'achat et de vente dans le passé ?

Principe, en trois temps :
1. une règle produit chaque jour un « signal » : 1 = on détient l'action, 0 = on est en liquidités ;
2. on rejoue l'historique : quand le signal vaut 1, on gagne (ou perd) la variation du lendemain ;
3. on compare au résultat d'une personne qui aurait simplement acheté au début et conservé.

Hypothèses simples (à rappeler à chaque présentation) :
- on achète ou vend au cours de clôture du jour où le signal apparaît ;
- on investit tout le capital, sans effet de levier ni vente à découvert ;
- on paie des frais (en %) à chaque achat et à chaque vente ; pas d'impôts, pas de dividendes.

Ce fichier ne dépend ni de Streamlit ni d'Internet.
"""

import pandas as pd

import indicateurs as ind


# ---------------------------------------------------------------
# Les règles : chacune renvoie une série de 0 et de 1
# ---------------------------------------------------------------
def signal_rsi(cloture, seuil_achat=30, seuil_vente=70, periode=14):
    """On achète quand le RSI passe sous `seuil_achat` (survente), on vend quand il dépasse `seuil_vente`.

    Entre les deux, on garde la position du jour d'avant : c'est ce qui évite de racheter
    et revendre chaque jour.
    """
    valeurs_rsi = ind.rsi(cloture, periode)
    en_position = 0
    signaux = []
    for valeur in valeurs_rsi:
        if valeur == valeur:   # faux si la valeur est vide (NaN) : pas assez d'historique
            if en_position == 0 and valeur < seuil_achat:
                en_position = 1
            elif en_position == 1 and valeur > seuil_vente:
                en_position = 0
        signaux.append(en_position)
    return pd.Series(signaux, index=cloture.index)


def signal_croisement(cloture, court=50, long=200):
    """On détient l'action tant que la moyenne mobile courte est au-dessus de la longue."""
    ma_courte = ind.moyenne_mobile(cloture, court)
    ma_longue = ind.moyenne_mobile(cloture, long)
    return (ma_courte > ma_longue).astype(int)   # une comparaison avec une valeur vide donne faux, donc 0


# ---------------------------------------------------------------
# La simulation
# ---------------------------------------------------------------
def simuler(cloture, signal, debut=None, frais=0.001):
    """Rejoue l'historique avec la règle et compare avec « acheter et conserver ».

    `cloture` et `signal` : séries de même longueur (tout l'historique disponible, pour que
    les indicateurs soient déjà « chauffés » au début de la période testée).
    `debut` : première date testée (None = tout). `frais` : 0.001 = 0,1 % par achat ou vente.

    Renvoie un dictionnaire : courbe, reference (deux séries en base 100), trades, stats.
    """
    cloture = cloture.dropna()
    signal = signal.reindex(cloture.index).fillna(0).astype(int)

    variation = cloture.pct_change().fillna(0)
    # Le gain d'un jour est celui de la position détenue la veille au soir ;
    # les frais sont retirés le jour où l'on achète ou vend
    changement = signal.diff().abs().fillna(0)
    gain = (1 + signal.shift(1).fillna(0) * variation) * (1 - frais * changement) - 1

    if debut is not None:
        garder = cloture.index >= debut
        cloture, signal, gain = cloture[garder], signal[garder], gain[garder]
    if len(cloture) < 2:
        raise ValueError("Pas assez de données sur la période choisie.")

    gain = gain.copy()
    gain.iloc[0] = 0   # la simulation démarre à 100 le premier jour
    courbe = (1 + gain).cumprod() * 100
    reference = cloture / cloture.iloc[0] * 100

    trades = _lister_trades(cloture, signal, frais)
    return {"courbe": courbe, "reference": reference, "trades": trades, "stats": _statistiques(courbe, reference, signal, trades)}


def _lister_trades(cloture, signal, frais):
    """Liste les allers-retours : un achat (signal 0 -> 1) puis une vente (1 -> 0)."""
    trades = []
    entree = None
    precedent = 0
    for date, valeur in signal.items():
        if valeur == 1 and precedent == 0:
            entree = date
        elif valeur == 0 and precedent == 1 and entree is not None:
            trades.append(_un_trade(cloture, entree, date, frais, en_cours=False))
            entree = None
        precedent = valeur
    if precedent == 1 and entree is not None:   # position encore ouverte à la fin
        trades.append(_un_trade(cloture, entree, cloture.index[-1], frais, en_cours=True))
    return trades


def _un_trade(cloture, entree, sortie, frais, en_cours):
    prix_entree, prix_sortie = float(cloture[entree]), float(cloture[sortie])
    rendement = ((prix_sortie / prix_entree) * (1 - frais) ** 2 - 1) * 100   # frais à l'achat et à la vente
    return {
        "entree": entree, "sortie": sortie,
        "prix_entree": prix_entree, "prix_sortie": prix_sortie,
        "rendement_pct": rendement, "en_cours": en_cours,
    }


def _baisse_maximale(courbe):
    """Plus forte chute depuis un sommet, en % (nombre négatif ou nul)."""
    return float((courbe / courbe.cummax() - 1).min() * 100)


def _statistiques(courbe, reference, signal, trades):
    terminés = [t for t in trades if not t["en_cours"]]
    gagnants = [t for t in terminés if t["rendement_pct"] > 0]
    return {
        "perf_strategie": float(courbe.iloc[-1] - 100),
        "perf_reference": float(reference.iloc[-1] - 100),
        "nb_trades": len(trades),
        "taux_reussite": len(gagnants) / len(terminés) * 100 if terminés else None,
        "baisse_max_strategie": _baisse_maximale(courbe),
        "baisse_max_reference": _baisse_maximale(reference),
        "temps_investi": float(signal.mean() * 100),
    }
