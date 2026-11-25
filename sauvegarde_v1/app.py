"""Étape 15 (apparence) : tableau de bord financier (indicateurs dont MACD et Bollinger, alertes dont volume anormal,
comparaison, portefeuille, actualités, sentiment, backtest, projection, export CSV).

Pour lancer l'application, dans le terminal :
    streamlit run app.py

Fichiers du projet :
    app.py          l'interface (ce fichier)
    data.py         récupération des cours
    indicateurs.py  moyennes mobiles et RSI
    comparaison.py  courbes de base 100
    actualites.py   mise en forme des actualités
    backtest.py     simulation de règles d'achat et de vente
    sentiment.py    score de sentiment des titres d'actualité
    projection.py   projection de tendance et son évaluation
    export.py       export CSV
    devises.py      conversion euro / dollar
    recherche.py    recherche d'actions par nom
    portefeuille.py calculs de valeur et de gain
    database.py     base SQLite (liste de suivi, alertes, historique)
    verificateur.py vérification des alertes
    notifications.py envoi des messages Telegram
    style.py        apparence (couleurs, cartes, thème des graphiques)
"""

import html
import re

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import actualites
import backtest
import comparaison
import database as db
import devises
import export
import indicateurs as ind
import portefeuille
import projection
import recherche
import langue
import sentiment
import style
from langue import t
from data import actualites_brutes, devise, rechercher_actions
from data import recuperer_cours as _recuperer_cours
from notifications import telegram_configure
try:   # champ de recherche avec liste déroulante en direct (paquet facultatif : pip install streamlit-searchbox)
    from streamlit_searchbox import st_searchbox
except ImportError:
    st_searchbox = None

from verificateur import condition_remplie, decrire, libelle_condition, mesurer, verifier_alertes

# Streamlit relit app.py à chaque modification, mais pas toujours les fichiers qu'il importe :
# on recharge ces fichiers-là pour que les changements d'apparence et de devises soient pris en compte.
import importlib
importlib.reload(style)
importlib.reload(devises)
importlib.reload(comparaison)
importlib.reload(langue)
from langue import t   # noqa: E402 (version rechargée)

# ---------------------------------------------------------------
# Réglages de la page
# ---------------------------------------------------------------
# Mode d'affichage (sombre ou clair) et langue (fr ou en), gardés pour toute la session
st.session_state.setdefault("mode", "sombre")
st.session_state.setdefault("langue", "fr")
langue.LANGUE = st.session_state["langue"]

st.set_page_config(page_title=t("Tableau de bord financier"), layout="wide")

# Le thème de Streamlit (boutons, champs, tableaux) est envoyé au navigateur au début de chaque
# affichage : quand on change de mode, on règle ce thème puis on relance une fois l'affichage.
from streamlit import config as _config_streamlit   # noqa: E402

_theme_voulu = style.THEMES_STREAMLIT[st.session_state["mode"]]
if any(_config_streamlit.get_option(f"theme.{cle}") != valeur for cle, valeur in _theme_voulu.items()):
    for cle, valeur in _theme_voulu.items():
        _config_streamlit.set_option(f"theme.{cle}", valeur)
    st.rerun()

style.appliquer(st.session_state["mode"])   # couleurs et cartes (palette sombre ou claire)

# Crée la base de données au premier lancement et la met à jour si besoin
db.initialiser()

# Pour chaque bouton de période : (durée à récupérer, intervalle entre deux points)
PERIODES = {
    "1J": ("1d", "5m"),
    "1M": ("1mo", "1d"),
    "1A": ("1y", "1d"),
    "5A": ("5y", "1wk"),
}

# Périodes de la vue Comparaison (pas de 1J : les horaires de Paris et New York diffèrent)
# Pour 1J et 1S, on compare des points dans la journée (toutes les 5 ou 30 minutes)
PERIODES_COMPARAISON = {"1J": ("1d", "5m"), "1S": ("5d", "30m"), "1M": ("1mo", "1d"), "1A": ("1y", "1d"), "5A": ("5y", "1wk")}

# Indices de référence proposés dans la vue Comparaison (symboles Yahoo Finance)
INDICES = {"^FCHI": "CAC 40", "^GSPC": "S&P 500"}

# Couleurs des courbes d'indicateurs
COULEUR_MA50 = "#F59E0B"
COULEUR_MA200 = "#A78BFA"
COULEUR_RSI = "#2DD4BF"
COULEUR_MACD = "#60A5FA"
COULEUR_SIGNAL = "#F97316"
COULEUR_BOLLINGER = "#94A3B8"


# ---------------------------------------------------------------
# Données (avec une mémoire de 5 minutes pour limiter les demandes)
# ---------------------------------------------------------------
@st.cache_data(ttl=300)
def recuperer_cours(ticker, periode, intervalle):
    return _recuperer_cours(ticker, periode, intervalle)


@st.cache_data(ttl=900)
def liste_actualites(ticker):
    """Actualités de l'action, mises en forme (mémorisées 15 minutes)."""
    return actualites.normaliser(actualites_brutes(ticker), limite=8)


@st.cache_data(ttl=3600)
def chercher(texte):
    """Phrases à proposer dans la liste déroulante pour le texte tapé (mémorisées 1 heure)."""
    return recherche.options(texte, rechercher_actions(texte))


@st.cache_data(ttl=300)
def resume_du_jour(ticker):
    """Renvoie (dernier cours, variation en % par rapport à la veille), ou None."""
    cours = recuperer_cours(ticker, "5d", "1d")
    if len(cours) < 2:
        return None
    dernier = cours["Close"].iloc[-1]
    precedent = cours["Close"].iloc[-2]
    return dernier, (dernier - precedent) / precedent * 100


def choix_boutons(label, options, defaut, cle, visible=False):
    """Boutons côte à côte (style de la maquette). Sur une vieille version de Streamlit : boutons radio.

    Les options restent en français dans le code ; seul leur affichage est traduit.
    """
    visibilite = "visible" if visible else "collapsed"
    if hasattr(st, "segmented_control"):
        valeur = st.segmented_control(t(label), options, default=defaut, key=cle, label_visibility=visibilite, format_func=t)
        return valeur if valeur is not None else defaut   # si on décoche, on garde le choix par défaut
    return st.radio(t(label), options, index=options.index(defaut), horizontal=True, key=cle,
                    label_visibility=visibilite, format_func=t)


def libelle(alerte):
    """Condition d'une alerte, dans la langue de l'interface."""
    return langue.libelle_condition(alerte, devise(alerte["ticker"]))


def decrire_alerte(alerte, mesure):
    """Description d'une alerte déclenchée, dans la langue de l'interface."""
    return langue.decrire(alerte, mesure, devise(alerte["ticker"]))


# ---------------------------------------------------------------
# Messages à afficher après une action
# ---------------------------------------------------------------
# Un clic relance tout le script ; on garde donc les messages dans st.session_state
# pour pouvoir les afficher après le rechargement.
def ajouter_message(niveau, texte):
    st.session_state.setdefault("messages", []).append((niveau, texte))


def afficher_messages():
    for niveau, texte in st.session_state.pop("messages", []):
        getattr(st, niveau)(texte)   # st.success, st.warning, st.info...


# ---------------------------------------------------------------
# Devise d'affichage : convertir les prix au taux de change du jour
# ---------------------------------------------------------------
# cible = symbole de la devise choisie (None = chaque valeur dans sa devise d'origine)
# taux = {symbole: unités pour 1 dollar}, récupérés au moment de l'affichage
ORIGINE = "Devise d'origine"
OPTIONS_DEVISE = [ORIGINE] + [info[1] for info in devises.DEVISES.values()]
SYMBOLE_DE_NOM = {info[1]: sym for sym, info in devises.DEVISES.items()}


@st.cache_data(ttl=120)
def taux_du_jour():
    """Taux de change actuels (mémorisés 2 minutes) : {symbole: unités pour 1 $}."""
    taux = {}
    for symbole_dev, symbole_yahoo in devises.symboles_yahoo().items():
        for periode, intervalle in (("1d", "1m"), ("5d", "1d")):   # le plus récent possible, sinon la dernière clôture
            donnees = _recuperer_cours(symbole_yahoo, periode, intervalle)
            if not donnees.empty and donnees["Close"].dropna().size:
                taux[symbole_dev] = float(donnees["Close"].dropna().iloc[-1])
                break
    return taux


cible = SYMBOLE_DE_NOM.get(st.session_state.get("devise_choisie", ORIGINE))
taux = {}
if cible is not None:
    taux = taux_du_jour()
    if (cible != "$" and cible not in taux) or "€" not in taux:
        ajouter_message("warning", t("Taux de change indisponible : prix affichés dans leur devise d'origine."))
        cible = None


def facteur_vers_cible(ticker):
    """Facteur de conversion (taux du jour) d'un prix de cette action vers la devise d'affichage."""
    if cible is None:
        return 1.0
    return devises.facteur(devise(ticker), cible, taux)


def conv(donnees, ticker):
    """Convertit des cours (tableau ou série) dans la devise d'affichage choisie."""
    return devises.convertir(donnees, facteur_vers_cible(ticker))


def symbole_affiche(ticker):
    """Symbole de la devise dans laquelle le prix de cette action est affiché."""
    return cible or devise(ticker)


def _memoriser_devise(cle):
    st.session_state["devise_choisie"] = st.session_state[cle]


def selecteur_devise(cle):
    """Liste déroulante des devises. Le choix est commun à toutes les vues."""
    actuel = st.session_state.get("devise_choisie", ORIGINE)
    if cle not in st.session_state:
        st.session_state[cle] = actuel
    st.selectbox(t("Devise d'affichage"), OPTIONS_DEVISE, key=cle, on_change=_memoriser_devise, args=(cle,),
                 label_visibility="collapsed", format_func=t)
    if cible is not None:
        if cible == "$":
            st.caption(t("{a} = {x:.4f} {b} · taux actuel", a="1 €", x=devises.facteur("€", "$", taux), b="$"))
        else:
            st.caption(t("{a} = {x:.4f} {b} · taux actuel", a="1 $", x=devises.facteur("$", cible, taux), b=cible))


# ---------------------------------------------------------------
# Barre du haut : titre et onglets
# ---------------------------------------------------------------
liste_suivi = db.lister_watchlist()
VUES = ["Une action", "Comparaison", "Portefeuille", "Backtest", "Projection"]

def _changer_reglage(nom):
    """Recopie le choix du bouton (thème ou langue) dans la session ; un clic qui désélectionne ne change rien."""
    valeur = st.session_state[f"bouton_{nom}"]
    if valeur is not None:
        st.session_state[nom] = valeur


col_entete, col_mode, col_langue = st.columns([6, 1.5, 1])
with col_entete:
    titre_page = t("Tableau de bord financier")
    source_page = t("Cours différés d'environ 15 minutes · source : yfinance")
    st.markdown(
        f'<div class="tb-entete"><h1>{titre_page}</h1><span class="tb-pastille">{source_page}</span></div>',
        unsafe_allow_html=True,
    )
with col_mode:
    st.session_state["bouton_mode"] = st.session_state["mode"]
    st.segmented_control(t("Thème"), ["clair", "sombre"], key="bouton_mode", label_visibility="collapsed",
                         format_func=lambda m: t("☀️ Clair") if m == "clair" else t("🌙 Sombre"),
                         on_change=_changer_reglage, args=("mode",))
with col_langue:
    st.session_state["bouton_langue"] = st.session_state["langue"]
    st.segmented_control(t("Langue"), ["fr", "en"], key="bouton_langue", label_visibility="collapsed",
                         format_func=str.upper, on_change=_changer_reglage, args=("langue",))

vue = choix_boutons("Vue", VUES, VUES[0], "vue")   # les onglets du haut
afficher_messages()

# ---------------------------------------------------------------
# Colonne de gauche : la liste de suivi (une carte cliquable par action)
# ---------------------------------------------------------------
if liste_suivi and st.session_state.get("choix") not in liste_suivi:
    st.session_state["choix"] = liste_suivi[0]
choix = st.session_state.get("choix") if liste_suivi else None

with st.sidebar:
    st.markdown(
        f'<div class="tb-liste-titre"><h2>{t("Ma liste de suivi")}</h2>'
        f'<span>{t("{n} valeurs" if len(liste_suivi) > 1 else "{n} valeur", n=len(liste_suivi))}</span></div>',
        unsafe_allow_html=True,
    )
    for ticker_l in liste_suivi:
        resume_l = resume_du_jour(ticker_l)
        with st.container(key="carte_" + re.sub(r"\W", "_", ticker_l)):
            if resume_l is None:
                st.markdown(style.ligne_suivi(ticker_l, None, None, ticker_l == choix), unsafe_allow_html=True)
            else:
                prix_l = f"{resume_l[0] * facteur_vers_cible(ticker_l):.2f} {symbole_affiche(ticker_l)}"
                st.markdown(style.ligne_suivi(ticker_l, prix_l, resume_l[1], ticker_l == choix), unsafe_allow_html=True)
            # Bouton invisible posé sur toute la carte : un clic sur la carte choisit l'action
            if st.button(t("Choisir {ticker}", ticker=ticker_l), key=f"choisir_{ticker_l}"):
                st.session_state["choix"] = ticker_l
                st.rerun()

    if choix is not None and st.button(t("Retirer {ticker}", ticker=choix), key="retirer"):
        db.retirer_ticker(choix)   # supprime aussi ses alertes actives
        st.rerun()

    with st.expander(t("+ Ajouter une action")):
        st.caption(t("Tape son nom ou son ticker"))
        if st_searchbox is not None:
            # La liste de propositions se met à jour à chaque lettre tapée
            libelle_choisi = st_searchbox(chercher, placeholder=t("ex. Apple, LVMH, NVDA..."), key="recherche_action")
        else:
            # Sans le paquet : on tape puis on valide avec Entrée, et les propositions apparaissent
            texte_recherche = st.text_input(t("Rechercher"), placeholder=t("Nom ou ticker, puis Entrée")) or ""
            propositions = chercher(texte_recherche) if len(texte_recherche.strip()) >= 2 else []
            libelle_choisi = st.selectbox(t("Résultats"), propositions) if propositions else None
            if texte_recherche.strip() and not propositions:
                st.caption(t("Aucun résultat."))

        if libelle_choisi:
            symbole_choisi = recherche.symbole_depuis_libelle(libelle_choisi)
            if symbole_choisi is None:
                st.warning(t("Choix non reconnu : recommence la recherche."))
            elif symbole_choisi in liste_suivi:
                st.caption(t("{ticker} est déjà dans ta liste.", ticker=symbole_choisi))
            elif st.button(t("Ajouter {ticker}", ticker=symbole_choisi)):
                if recuperer_cours(symbole_choisi, "5d", "1d").empty:
                    st.error(t("Aucune donnée de cours pour {ticker} : essaie une autre valeur.", ticker=symbole_choisi))
                else:
                    db.ajouter_ticker(symbole_choisi)
                    st.session_state["choix"] = symbole_choisi
                    st.rerun()


# ---------------------------------------------------------------
# Vue Portefeuille : mes achats, leur valeur et mon gain
# ---------------------------------------------------------------
if vue == "Portefeuille":
    c_titre_pf, c_dev_pf = st.columns([4, 1.3])
    c_titre_pf.subheader(t("Mon portefeuille"))
    with c_dev_pf:
        selecteur_devise("devise_portefeuille")

    if liste_suivi:
        c_t, c_q, c_p, c_b = st.columns([2, 2, 2, 2])
        ticker_achat = c_t.selectbox(t("Action"), liste_suivi)
        resume_achat = resume_du_jour(ticker_achat)
        quantite_achat = c_q.number_input(t("Quantité"), min_value=0.0001, value=1.0, step=1.0, format="%.4f")
        prix_achat = c_p.number_input(
            t("Prix d'achat ({d})", d=devise(ticker_achat)),
            min_value=0.01,
            value=round(float(resume_achat[0]), 2) if resume_achat else 1.0,
            step=1.0,
            format="%.2f",
        )
        c_b.write("")   # petit espace pour aligner le bouton avec les champs
        if c_b.button(t("Ajouter l'achat")):
            db.ajouter_position(ticker_achat, float(quantite_achat), float(prix_achat))
            ajouter_message("success", t("Achat de {q:g} {ticker} enregistré.", q=quantite_achat, ticker=ticker_achat))
            st.rerun()
    else:
        st.info(t("Ajoute d'abord une action à ta liste de suivi pour pouvoir l'acheter ici."))

    lots = db.lister_positions()
    if not lots:
        st.info(t("Ton portefeuille est vide : enregistre un achat ci-dessus."))
        st.stop()

    # Dernier cours de chaque action détenue
    cours_actuels = {}
    for tk in {lot["ticker"] for lot in lots}:
        resume_t = resume_du_jour(tk)
        cours_actuels[tk] = float(resume_t[0]) if resume_t else None

    lignes = portefeuille.synthese(lots, cours_actuels)
    if cible is not None:
        lignes = portefeuille.convertir_lignes(lignes, cible, lambda de: devises.facteur(de, cible, taux))
    totaux = portefeuille.totaux_par_devise(lignes)

    # Les totaux, une ligne par devise
    for symbole_dev, tot in totaux.items():
        m1, m2, m3 = st.columns(3)
        m1.metric(t("Valeur actuelle ({d})", d=symbole_dev), f"{tot['valeur']:,.2f}".replace(",", " "))
        m2.metric(t("Investi ({d})", d=symbole_dev), f"{tot['investi']:,.2f}".replace(",", " "))
        m3.metric(t("Gain ou perte ({d})", d=symbole_dev), f"{tot['gain']:+,.2f}".replace(",", " "), f"{tot['gain_pct']:+.2f} %")

    st.dataframe(
        [
            {
                t("Action"): l["ticker"],
                t("Quantité"): f"{l['quantite']:g}",
                t("Prix d'achat moyen"): f"{l['pru']:.2f} {l['devise']}",
                t("Cours actuel"): f"{l['cours']:.2f} {l['devise']}" if l["cours"] is not None else t("indisponible"),
                t("Valeur"): f"{l['valeur']:.2f} {l['devise']}" if l["valeur"] is not None else "-",
                t("Gain ou perte"): (
                    f"{l['gain']:+.2f} {l['devise']} ({l['gain_pct']:+.1f} %)" if l["gain"] is not None else "-"
                ),
            }
            for l in lignes
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.download_button(
        t("Télécharger le portefeuille (CSV)"),
        export.vers_csv(
            [
                {
                    "Action": l["ticker"], "Devise": l["devise"], "Quantité": l["quantite"],
                    "Prix d'achat moyen": l["pru"], "Cours actuel": l["cours"], "Valeur": l["valeur"],
                    "Gain": l["gain"], "Gain (%)": l["gain_pct"],
                }
                for l in lignes
            ]
        ),
        file_name="portefeuille.csv",
        mime="text/csv",
    )

    # Répartition : un graphique par devise (on ne mélange pas € et $)
    if totaux:
        colonnes_pie = st.columns(len(totaux))
        for colonne, symbole_dev in zip(colonnes_pie, totaux):
            parts = [l for l in lignes if l["devise"] == symbole_dev and l["valeur"] is not None]
            fig_pie = go.Figure(
                go.Pie(labels=[l["ticker"] for l in parts], values=[l["valeur"] for l in parts], hole=0.45)
            )
            fig_pie.update_layout(title=t("Répartition ({d})", d=symbole_dev))
            style.theme_graphique(fig_pie, 380)
            colonne.plotly_chart(fig_pie, use_container_width=True)

    with st.expander(t("Détail des achats")):
        for lot in lots:
            c_texte, c_bouton = st.columns([6, 1])
            c_texte.write(
                t("**{ticker}** · {q:g} à {p:.2f} {d} · {date}", ticker=lot["ticker"], q=lot["quantite"],
                  p=lot["prix_achat"], d=devise(lot["ticker"]), date=lot["date_achat"][:10])
            )
            if c_bouton.button("✕", key=f"suppr_lot_{lot['id']}", help=t("Supprimer cet achat")):
                db.supprimer_position(lot["id"])
                st.rerun()

    if cible is None:
        note_devise = t("sans conversion de devise : chaque devise est totalisée séparément (choisis une devise en haut à droite pour tout additionner)")
    else:
        note_devise = t("tout est converti en {d} au taux de change du jour (le prix d'achat aussi : l'effet du change sur ton gain n'est pas isolé)", d=cible)
    st.caption(t("Valeurs au dernier cours connu (différé), sans frais, {note}. Aide à la décision, pas un conseil financier.",
                 note=note_devise))
    st.stop()

# ---------------------------------------------------------------
# Vue Comparaison : plusieurs actions et indices en base 100
# ---------------------------------------------------------------
if vue == "Comparaison":
    def nom_affiche(symbole_yahoo):
        return INDICES.get(symbole_yahoo, symbole_yahoo)

    st.subheader(t("Comparaison de performance"))
    selection = st.multiselect(
        t("Actions et indices à comparer"),
        liste_suivi + list(INDICES),
        default=liste_suivi[:2] + ["^GSPC"],
        format_func=nom_affiche,
    )
    periode_comp = st.radio(t("Période"), list(PERIODES_COMPARAISON), index=2, horizontal=True, key="periode_comp", format_func=t)

    if len(selection) < 2:
        st.info(t("Choisis au moins deux actions ou indices à comparer."))
        st.stop()

    periode_c, intervalle_c = PERIODES_COMPARAISON[periode_comp]
    clotures = {}
    indisponibles = []
    for symbole_yahoo in selection:
        donnees = recuperer_cours(symbole_yahoo, periode_c, intervalle_c)
        if donnees.empty:
            indisponibles.append(symbole_yahoo)
        else:
            clotures[nom_affiche(symbole_yahoo)] = conv(donnees["Close"], symbole_yahoo)
    if indisponibles:
        st.warning(t("Données indisponibles pour : {liste}", liste=", ".join(indisponibles)))

    courbes = comparaison.base_100(clotures, intraday=periode_comp in ("1J", "1S"))
    if courbes.empty or len(courbes.columns) < 2:
        st.warning(t("Pas assez de données communes pour comparer. Réessaie dans une minute."))
        st.stop()

    fig_comp = go.Figure()
    for nom in courbes.columns:
        fig_comp.add_trace(go.Scatter(x=courbes.index, y=courbes[nom], mode="lines", name=nom))
    fig_comp.add_hline(y=100, line_dash="dot", line_color=style.TEXTE_DISCRET)
    fig_comp.update_layout(
        title=t("Performance comparée (base 100) · {p}", p=t(periode_comp)),
        yaxis_title=t("Base 100 au départ"),
    )
    style.theme_graphique(fig_comp, 520)
    st.plotly_chart(fig_comp, use_container_width=True)

    # Classement, de la meilleure à la moins bonne performance
    performances = (courbes.iloc[-1] - 100).sort_values(ascending=False)
    st.dataframe(
        [{t("Valeur"): nom, t("Performance"): f"{perf:+.1f} %"} for nom, perf in performances.items()],
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        t("Départ commun : {date}. ", date=courbes.index[0].strftime('%d/%m/%Y %H:%M UTC' if periode_comp in ('1J', '1S') else '%d/%m/%Y'))
        + (t("Heures en temps universel (UTC) ; Paris et New York n'ouvrent pas aux mêmes heures : une courbe reste plate quand sa bourse est fermée. ")
           if periode_comp in ("1J", "1S") else "")
        + t("Les performances sont calculées sur les cours, sans dividendes (la devise d'affichage ne change pas une performance en %). Aide à la décision, pas un conseil financier.")
    )
    st.stop()

if choix is None:
    st.info(t("Ta liste de suivi est vide : ajoute une action dans la colonne de gauche."))
    st.stop()

# ---------------------------------------------------------------
# Vue Backtest : tester une règle d'achat et de vente sur le passé
# ---------------------------------------------------------------
if vue == "Backtest":
    st.subheader(t("Backtest · {ticker}", ticker=choix))
    st.caption(t("Que se serait-il passé si on avait appliqué une règle d'achat et de vente dans le passé ?"))

    regle = st.radio(t("Règle"), ["RSI : acheter en survente, vendre en surchauffe", "Croisement de moyennes mobiles"], format_func=t)
    c_a, c_b, c_c, c_d = st.columns(4)
    if regle.startswith("RSI"):
        seuil_achat = c_a.number_input(t("Acheter quand le RSI passe sous"), min_value=5, max_value=50, value=30, step=1)
        seuil_vente = c_b.number_input(t("Vendre quand le RSI dépasse"), min_value=50, max_value=95, value=70, step=1)
    else:
        ma_courte = c_a.number_input(t("Moyenne courte (jours)"), min_value=5, max_value=100, value=50, step=5)
        ma_longue = c_b.number_input(t("Moyenne longue (jours)"), min_value=20, max_value=400, value=200, step=10)
        if ma_courte >= ma_longue:
            st.warning(t("La moyenne courte doit être plus petite que la longue."))
            st.stop()
    frais_pct = c_c.number_input(t("Frais par achat ou vente (%)"), min_value=0.0, max_value=2.0, value=0.1, step=0.05, format="%.2f")
    duree = c_d.radio(t("Période testée"), ["1A", "3A", "5A"], index=2, horizontal=True, format_func=t)

    # On charge 10 ans pour que les indicateurs soient déjà calculés au début de la période testée
    historique_bt = recuperer_cours(choix, "10y", "1d")["Close"].dropna()
    if len(historique_bt) < 260:
        st.warning(t("Historique trop court pour tester une règle sur cette action."))
        st.stop()

    if regle.startswith("RSI"):
        signal = backtest.signal_rsi(historique_bt, seuil_achat, seuil_vente)
    else:
        signal = backtest.signal_croisement(historique_bt, int(ma_courte), int(ma_longue))

    annees = int(duree[0])
    debut_test = historique_bt.index[-1] - pd.DateOffset(years=annees)
    resultat = backtest.simuler(historique_bt, signal, debut=debut_test, frais=frais_pct / 100)
    stats = resultat["stats"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("Avec la règle"), f"{stats['perf_strategie']:+.1f} %",
              t("{x:+.1f} pts vs conserver", x=stats["perf_strategie"] - stats["perf_reference"]))
    m2.metric(t("Acheter et conserver"), f"{stats['perf_reference']:+.1f} %")
    m3.metric(t("Transactions"), f"{stats['nb_trades']}",
              t("{x:.0f} % gagnantes", x=stats["taux_reussite"]) if stats["taux_reussite"] is not None else t("aucune terminée"))
    m4.metric(t("Plus forte baisse"), f"{stats['baisse_max_strategie']:.1f} %",
              t("{x:.1f} % si conservé", x=stats["baisse_max_reference"]), delta_color="off")

    fig_bt = go.Figure()
    fig_bt.add_trace(go.Scatter(x=resultat["reference"].index, y=resultat["reference"], mode="lines",
                                name=t("Acheter et conserver"), line=dict(color=style.TEXTE_DISCRET, width=1.6)))
    fig_bt.add_trace(go.Scatter(x=resultat["courbe"].index, y=resultat["courbe"], mode="lines",
                                name=t("Avec la règle"), line=dict(color=style.TURQUOISE, width=2)))
    achats = [tr["entree"] for tr in resultat["trades"]]
    ventes = [tr["sortie"] for tr in resultat["trades"] if not tr["en_cours"]]
    if achats:
        fig_bt.add_trace(go.Scatter(x=achats, y=resultat["courbe"].loc[achats], mode="markers", name=t("Achat"),
                                    marker=dict(symbol="triangle-up", size=11, color=style.VERT)))
    if ventes:
        fig_bt.add_trace(go.Scatter(x=ventes, y=resultat["courbe"].loc[ventes], mode="markers", name=t("Vente"),
                                    marker=dict(symbol="triangle-down", size=11, color=style.ROUGE)))
    fig_bt.update_layout(
        title=t("{ticker} · valeur d'un capital de 100 · {p}", ticker=choix, p=t(duree)),
        yaxis_title=t("Capital (base 100)"),
    )
    style.theme_graphique(fig_bt, 480)
    st.plotly_chart(fig_bt, use_container_width=True)

    if resultat["trades"]:
        symbole_bt = devise(choix)
        st.dataframe(
            [
                {
                    t("Achat"): f"{tr['entree']:%d/%m/%Y}",
                    t("Prix d'achat"): f"{tr['prix_entree']:.2f} {symbole_bt}",
                    t("Vente"): t("en cours") if tr["en_cours"] else f"{tr['sortie']:%d/%m/%Y}",
                    t("Prix de vente"): f"{tr['prix_sortie']:.2f} {symbole_bt}" + (t(" (dernier cours)") if tr["en_cours"] else ""),
                    t("Résultat"): f"{tr['rendement_pct']:+.1f} %",
                }
                for tr in reversed(resultat["trades"])
            ],
            hide_index=True,
            use_container_width=True,
        )
        st.download_button(
            t("Télécharger les transactions (CSV)"),
            export.vers_csv(
                [
                    {
                        "Achat": f"{tr['entree']:%Y-%m-%d}", "Prix d'achat": tr["prix_entree"],
                        "Vente": "" if tr["en_cours"] else f"{tr['sortie']:%Y-%m-%d}", "Prix de vente": tr["prix_sortie"],
                        "Résultat (%)": tr["rendement_pct"], "En cours": tr["en_cours"],
                    }
                    for tr in resultat["trades"]
                ]
            ),
            file_name=f"backtest_{choix}.csv",
            mime="text/csv",
        )
    else:
        st.info(t("La règle n'a déclenché aucune transaction sur cette période."))

    st.caption(t(
        "Temps passé investi : {x:.0f} % de la période. Achats et ventes au cours de clôture du jour du signal, "
        "capital entièrement investi, sans impôts ni dividendes. Le passé ne garantit pas l'avenir, et une règle réglée après coup "
        "sur un historique donné peut paraître meilleure qu'elle ne le sera vraiment. Aide à la décision, pas un conseil financier.",
        x=stats["temps_investi"],
    ))
    st.stop()

# ---------------------------------------------------------------
# Vue Projection : prolonger la tendance récente (indicatif)
# ---------------------------------------------------------------
if vue == "Projection":
    c_titre_p, c_dev_p = st.columns([4, 1.3])
    c_titre_p.subheader(t("Projection de tendance · {ticker}", ticker=choix))
    with c_dev_p:
        selecteur_devise("devise_projection")
    st.warning(t(
        "Ce n'est pas une prévision : la projection prolonge simplement la tendance récente. "
        "La mesure de fiabilité ci-dessous montre à quel point elle s'est trompée dans le passé."
    ))
    c_hist, c_hor = st.columns(2)
    base_choisie = c_hist.radio(t("Historique utilisé pour la tendance"), ["6 mois", "1 an", "3 ans"], index=1, horizontal=True, format_func=t)
    horizon = c_hor.radio(t("Horizon de projection"), [30, 60, 90], index=0, horizontal=True, format_func=lambda j: t("{j} jours", j=j))
    jours_historique = {"6 mois": 126, "1 an": 252, "3 ans": 756}[base_choisie]

    serie_proj = conv(recuperer_cours(choix, "5y", "1d")["Close"].dropna(), choix)
    if len(serie_proj) < jours_historique + horizon + 60:
        st.warning(t("Historique trop court pour cette combinaison. Choisis un historique ou un horizon plus petit."))
        st.stop()

    resultat_proj = projection.projeter(serie_proj, jours_historique, horizon)
    previsions = resultat_proj["previsions"]
    symbole_p = symbole_affiche(choix)
    dernier_p = float(serie_proj.iloc[-1])
    centre_final = float(previsions["centre"].iloc[-1])

    k1, k2, k3 = st.columns(3)
    k1.metric(t("Dernier cours"), f"{dernier_p:.2f} {symbole_p}")
    k2.metric(t("Projection à {j} jours", j=horizon), f"{centre_final:.2f} {symbole_p}", f"{(centre_final / dernier_p - 1) * 100:+.1f} %")
    k3.metric(t("Fourchette à 95 %"), f"{previsions['bas'].iloc[-1]:.0f} – {previsions['haut'].iloc[-1]:.0f} {symbole_p}")

    recent = serie_proj.iloc[-252:]
    fig_p = go.Figure()
    fig_p.add_trace(go.Scatter(x=recent.index, y=recent, mode="lines", name=t("Cours"), line=dict(color=style.TEXTE_DISCRET, width=1.8)))
    fig_p.add_trace(go.Scatter(x=previsions.index, y=previsions["haut"], mode="lines", name=t("Haut 95 %"),
                               line=dict(width=0), showlegend=False))
    fig_p.add_trace(go.Scatter(x=previsions.index, y=previsions["bas"], mode="lines", name=t("Fourchette à 95 %"),
                               line=dict(width=0), fill="tonexty", fillcolor="rgba(45,212,191,0.18)"))
    fig_p.add_trace(go.Scatter(x=previsions.index, y=previsions["centre"], mode="lines", name=t("Projection"),
                               line=dict(color=style.TURQUOISE, width=2, dash="dash")))
    fig_p.update_layout(title=t("{ticker} · projection sur {j} jours", ticker=choix, j=horizon), yaxis_title=t("Prix ({d})", d=symbole_p))
    style.theme_graphique(fig_p, 480)
    st.plotly_chart(fig_p, use_container_width=True)

    st.subheader(t("Cette méthode s'est-elle déjà trompée ?"))
    bilan = projection.evaluer(serie_proj, jours_historique, horizon)
    if bilan is None:
        st.caption(t("Historique insuffisant pour mesurer la fiabilité."))
    else:
        e1, e2, e3 = st.columns(3)
        e1.metric(t("Cours réel dans la fourchette"), f"{bilan['couverture_pct']:.0f} %", t("objectif : environ 95 %"), delta_color="off")
        e2.metric(t("Erreur moyenne de la projection"), f"{bilan['erreur_modele_pct']:.1f} %")
        e3.metric(t("Erreur si « le cours ne bouge pas »"), f"{bilan['erreur_naive_pct']:.1f} %")
        if bilan["erreur_modele_pct"] < bilan["erreur_naive_pct"]:
            verdict = t("Sur cet historique, prolonger la tendance a fait un peu mieux que supposer que le cours ne bouge pas.")
        else:
            verdict = t("Sur cet historique, prolonger la tendance n'a pas fait mieux que supposer que le cours ne bouge pas.")
        st.caption(t(
            "{verdict} Test rejoué sur {n} dates du passé, avec les seules données connues à l'époque. "
            "Les cours sont en grande partie imprévisibles à court terme : ne pas se fier à cette projection pour décider. "
            "Aide à la décision, pas un conseil financier.",
            verdict=verdict, n=bilan["nombre_tests"],
        ))
    st.stop()

# Trois colonnes, toujours visibles : cours | actualités | alertes et indicateurs techniques
_col_g, _col_a, _col_d = st.columns([2.6, 1.25, 1.15])
col_centre = _col_g.container(key="zone_principale")
col_actus = _col_a.container(key="zone_actus")
col_droite = _col_d.container(key="zone_alertes")
# Colonne de droite, de haut en bas : alertes actives, indicateurs techniques, alertes déclenchées
with col_droite:
    carte_alertes = st.container(border=True)
    carte_indicateurs = st.container(border=True)
    carte_historique = st.container(border=True)
carte = col_centre.container(border=True)   # la grande carte du haut : titre, graphique et chiffres clés
with carte:
    col_titre_carte, col_devise_carte = st.columns([4, 1.3])
    zone_titre = col_titre_carte.container()   # remplie plus bas, quand le cours est connu
    with col_devise_carte:
        selecteur_devise("devise_action")   # liste déroulante des devises, en haut à droite de la carte
    col_periode, col_type = st.columns(2)
    with col_periode:
        periode_choisie = choix_boutons("Période", list(PERIODES), "1M", "periode")
    with col_type:
        type_graphique = choix_boutons("Type de graphique", ["Courbe", "Chandeliers"], "Courbe", "type_graphique")

# Les indicateurs sont calculés sur des clôtures journalières : pas disponibles pour 1J
indicateurs_disponibles = periode_choisie != "1J"
with carte:
    col_ma50, col_ma200, col_boll, col_rsi, col_macd = st.columns(5)
    with col_ma50:
        veut_ma50 = st.checkbox("MA 50", disabled=not indicateurs_disponibles)
    with col_ma200:
        veut_ma200 = st.checkbox("MA 200", disabled=not indicateurs_disponibles)
    with col_boll:
        veut_boll = st.checkbox("Bollinger", disabled=not indicateurs_disponibles)
    with col_rsi:
        veut_rsi = st.checkbox("RSI", disabled=not indicateurs_disponibles)
    with col_macd:
        veut_macd = st.checkbox("MACD", disabled=not indicateurs_disponibles)
    if not indicateurs_disponibles:
        st.caption(t("Les indicateurs utilisent des clôtures journalières : choisis une période de 1M ou plus."))

# Une case grisée peut rester cochée : on ne tient compte que des cases actives
afficher_ma50 = veut_ma50 and indicateurs_disponibles
afficher_ma200 = veut_ma200 and indicateurs_disponibles
afficher_rsi = veut_rsi and indicateurs_disponibles
afficher_boll = veut_boll and indicateurs_disponibles
afficher_macd = veut_macd and indicateurs_disponibles

periode, intervalle = PERIODES[periode_choisie]
cours = recuperer_cours(choix, periode, intervalle)

if cours.empty:
    st.warning(t("Impossible de récupérer les cours pour le moment. Réessaie dans une minute."))
    st.stop()

# Les quatre chiffres clés au-dessus du graphique
symbole = devise(choix)              # devise de cotation : c'est elle qui sert aux alertes
dernier = cours["Close"].iloc[-1]    # dernier cours dans la devise de cotation

# Pour l'affichage (chiffres et graphique), on convertit dans la devise choisie
cours_aff = conv(cours, choix)
symbole_aff = symbole_affiche(choix)
dernier_aff = cours_aff["Close"].iloc[-1]
premier_aff = cours_aff["Close"].iloc[0]
variation_periode = (dernier_aff - premier_aff) / premier_aff * 100

# Titre de la carte : nom, prix en grand, variation colorée
classe_var = "tb-hausse" if variation_periode >= 0 else "tb-baisse"
fleche_var = "▲" if variation_periode >= 0 else "▼"
texte_variation = t("({x:+.2f} % sur la période)", x=variation_periode)
texte_source = t("Cours différé d'environ 15 minutes · source : yfinance")
with zone_titre:
    st.markdown(
        f'<h2 class="tb-titre-carte">{choix}</h2>'
        f'<div><span class="tb-prix">{dernier_aff:.2f} {symbole_aff}</span>'
        f'<span class="{classe_var}">{fleche_var} {dernier_aff - premier_aff:+.2f} {symbole_aff} '
        f'{texte_variation}</span></div>'
        f'<div class="tb-discret">{texte_source}</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------
# Calcul des indicateurs
# ---------------------------------------------------------------
# Une moyenne sur 200 jours a besoin de 200 jours d'historique AVANT la première date
# affichée. On calcule donc les indicateurs sur 5 ans de clôtures journalières, puis on
# ne garde que la partie visible sur le graphique.
serie_ma50 = serie_ma200 = serie_rsi = None
bandes = macd_serie = None
if afficher_ma50 or afficher_ma200 or afficher_rsi or afficher_boll or afficher_macd:
    historique = recuperer_cours(choix, "5y", "1d")["Close"].dropna()
    if not historique.empty:
        historique = conv(historique, choix)
    if historique.empty:
        st.warning(t("Historique indisponible : les indicateurs ne peuvent pas être calculés."))
        afficher_ma50 = afficher_ma200 = afficher_rsi = afficher_boll = afficher_macd = False
    else:
        debut_affichage = cours.index[0]

        def partie_visible(serie):
            serie = serie[serie.index >= debut_affichage].dropna()
            return serie

        if afficher_ma50:
            serie_ma50 = partie_visible(ind.moyenne_mobile(historique, 50))
        if afficher_ma200:
            serie_ma200 = partie_visible(ind.moyenne_mobile(historique, 200))
        if afficher_rsi:
            serie_rsi = partie_visible(ind.rsi(historique, 14))
        if afficher_boll:
            milieu_b, haute_b, basse_b = ind.bollinger(historique, 20, 2)
            bandes = (partie_visible(haute_b), partie_visible(basse_b))
        if afficher_macd:
            ligne_m, signal_m, histo_m = ind.macd(historique)
            macd_serie = (partie_visible(ligne_m), partie_visible(signal_m), partie_visible(histo_m))

# ---------------------------------------------------------------
# Le graphique
# ---------------------------------------------------------------
avec_rsi = serie_rsi is not None and not serie_rsi.empty
avec_macd = macd_serie is not None and not macd_serie[0].empty

# Une zone pour le cours, plus une zone en dessous pour chaque indicateur qui a sa propre échelle
zones = (["rsi"] if avec_rsi else []) + (["macd"] if avec_macd else [])
ligne_de = {nom: 2 + i for i, nom in enumerate(zones)}   # numéro de ligne de chaque zone
if zones:
    part_cours = 0.72 if len(zones) == 1 else 0.58
    hauteurs = [part_cours] + [(1 - part_cours) / len(zones)] * len(zones)
    fig = make_subplots(rows=1 + len(zones), cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=hauteurs)
else:
    fig = make_subplots(rows=1, cols=1)

if type_graphique == "Courbe":
    # Une ligne invisible au niveau du plus bas permet de colorer l'aire sous la courbe (comme sur la maquette)
    fig.add_trace(
        go.Scatter(x=cours_aff.index, y=[float(cours_aff["Close"].min())] * len(cours_aff), mode="lines",
                   line=dict(width=0), hoverinfo="skip", showlegend=False),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=cours_aff.index, y=cours_aff["Close"], mode="lines", name=t("Cours de clôture"),
                   line=dict(color=style.TURQUOISE, width=2.4), fill="tonexty", fillcolor="rgba(45,212,191,0.12)"),
        row=1, col=1,
    )
else:
    fig.add_trace(
        go.Candlestick(
            x=cours_aff.index,
            open=cours_aff["Open"],
            high=cours_aff["High"],
            low=cours_aff["Low"],
            close=cours_aff["Close"],
            name=t("Cours"),
            increasing_line_color=style.VERT,
            decreasing_line_color=style.ROUGE,
        ),
        row=1,
        col=1,
    )

if serie_ma50 is not None and not serie_ma50.empty:
    fig.add_trace(
        go.Scatter(x=serie_ma50.index, y=serie_ma50, mode="lines", name="MA50", line=dict(color=COULEUR_MA50, width=1.6)),
        row=1,
        col=1,
    )
if serie_ma200 is not None and not serie_ma200.empty:
    fig.add_trace(
        go.Scatter(x=serie_ma200.index, y=serie_ma200, mode="lines", name="MA200", line=dict(color=COULEUR_MA200, width=1.6)),
        row=1,
        col=1,
    )

if bandes is not None and not bandes[0].empty:
    haute, basse = bandes
    fig.add_trace(
        go.Scatter(x=haute.index, y=haute, mode="lines", name=t("Bollinger haut"), showlegend=False,
                   line=dict(color=COULEUR_BOLLINGER, width=1)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=basse.index, y=basse, mode="lines", name=t("Bandes de Bollinger"), fill="tonexty",
                   fillcolor="rgba(148,163,184,0.12)", line=dict(color=COULEUR_BOLLINGER, width=1)),
        row=1,
        col=1,
    )

if avec_rsi:
    ligne_rsi = ligne_de["rsi"]
    fig.add_trace(
        go.Scatter(x=serie_rsi.index, y=serie_rsi, mode="lines", name="RSI", line=dict(color=COULEUR_RSI, width=1.6)),
        row=ligne_rsi,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color=style.TEXTE_DISCRET, row=ligne_rsi, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color=style.TEXTE_DISCRET, row=ligne_rsi, col=1)
    fig.update_yaxes(range=[0, 100], title_text="RSI", row=ligne_rsi, col=1)

if avec_macd:
    ligne_macd = ligne_de["macd"]
    serie_m, serie_s, serie_h = macd_serie
    fig.add_trace(
        go.Bar(x=serie_h.index, y=serie_h, name=t("Histogramme MACD"),
               marker_color=[style.VERT if v >= 0 else style.ROUGE for v in serie_h]),
        row=ligne_macd,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=serie_m.index, y=serie_m, mode="lines", name="MACD", line=dict(color=COULEUR_MACD, width=1.6)),
        row=ligne_macd,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=serie_s.index, y=serie_s, mode="lines", name=t("Signal"), line=dict(color=COULEUR_SIGNAL, width=1.6)),
        row=ligne_macd,
        col=1,
    )
    fig.update_yaxes(title_text="MACD", row=ligne_macd, col=1)

# Une ligne pointillée jaune pour chaque alerte de prix active sur cette action
for alerte in db.lister_alertes(choix):
    if alerte["type"] == "prix":
        signe = "≥" if alerte["sens"] == "hausse" else "≤"
        fig.add_hline(
            y=alerte["seuil"] * facteur_vers_cible(choix),   # ligne placée dans la devise d'affichage
            line_dash="dash",
            line_color=style.JAUNE,
            annotation_text=t("Seuil d'alerte {signe} {x:.2f} {d}", signe=signe, x=alerte["seuil"], d=symbole),
            annotation_position="top right",
            annotation_font_color=style.JAUNE,
            row=1,
            col=1,
        )

fig.update_layout(
    yaxis_title=t("Prix ({d})", d=symbole_aff),
    xaxis_rangeslider_visible=False,
)
style.theme_graphique(fig, 460 + 180 * len(zones))
with carte:
    st.plotly_chart(fig, use_container_width=True)

    # Les quatre chiffres clés sous le graphique
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("Début de période"), f"{cours_aff['Open'].iloc[0]:.2f} {symbole_aff}")
    c2.metric(t("Plus haut"), f"{cours_aff['High'].max():.2f} {symbole_aff}")
    c3.metric(t("Plus bas"), f"{cours_aff['Low'].min():.2f} {symbole_aff}")
    c4.metric(t("Volume cumulé"), f"{cours['Volume'].sum() / 1e6:.1f} M")

# Carte « Indicateurs techniques » : l'état actuel, quelle que soit la période affichée
with carte_indicateurs:
    st.markdown(f'<h2 class="tb-titre-carte">{t("Indicateurs techniques")}</h2>', unsafe_allow_html=True)
    hist5 = recuperer_cours(choix, "5y", "1d")
    clotures5 = hist5["Close"].dropna() if not hist5.empty else None
    # Les trois tuiles, l'une sous l'autre

    with st.container(border=True):
        valeur_rsi = None
        if clotures5 is not None and len(clotures5) > 30:
            serie_r = ind.rsi(clotures5, 14).dropna()
            valeur_rsi = float(serie_r.iloc[-1]) if not serie_r.empty else None
        if valeur_rsi is None:
            st.markdown(style.tuile(t("RSI (14 jours)"), t("n.d.")), unsafe_allow_html=True)
        else:
            etat = t("Survente") if valeur_rsi <= 30 else t("Surchauffe") if valeur_rsi >= 70 else t("Neutre")
            st.markdown(
                style.tuile(t("RSI (14 jours)"), f"{valeur_rsi:.0f}", etat, barre=valeur_rsi, bornes=(t("Survente 30"), t("Surchauffe 70"))),
                unsafe_allow_html=True,
            )

    with st.container(border=True):
        if clotures5 is not None and len(clotures5) >= 200:
            m50 = float(ind.moyenne_mobile(clotures5, 50).iloc[-1])
            m200 = float(ind.moyenne_mobile(clotures5, 200).iloc[-1])
            haussier = m50 > m200
            st.markdown(
                style.tuile(t("Moyennes mobiles"), "MA50 " + (">" if haussier else "<") + " MA200",
                            (t("▲ Tendance haussière") if haussier else t("▼ Tendance baissière")),
                            "tb-hausse" if haussier else "tb-baisse"),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(style.tuile(t("Moyennes mobiles"), t("n.d."), t("Moins de 200 jours d'historique")), unsafe_allow_html=True)

    with st.container(border=True):
        rapport_vol = ind.rapport_volume(hist5["Volume"], 20) if clotures5 is not None else None
        if rapport_vol is None:
            st.markdown(style.tuile(t("Volume vs moyenne 20 jours"), t("n.d.")), unsafe_allow_html=True)
        else:
            avis = t("Volume élevé") if rapport_vol >= 1.5 else t("Volume faible") if rapport_vol <= 0.6 else t("Dans la norme")
            st.markdown(style.tuile(t("Volume vs moyenne 20 jours"), f"{(rapport_vol - 1) * 100:+.0f} %", avis), unsafe_allow_html=True)

with carte:
    if avec_rsi:
        rsi_actuel = serie_rsi.iloc[-1]
        st.caption(t("RSI actuel : {x:.0f} · {texte}.", x=rsi_actuel, texte=t(ind.interpreter_rsi(rsi_actuel))))
    if avec_macd:
        st.caption(t("MACD : {texte}.", texte=t(ind.interpreter_macd(macd_serie[0].iloc[-1], macd_serie[1].iloc[-1]))))
    if bandes is not None and not bandes[0].empty:
        st.caption(t("Bandes de Bollinger : cours {texte}.", texte=t(ind.interpreter_bollinger(float(cours_aff['Close'].iloc[-1]), float(bandes[1].iloc[-1]), float(bandes[0].iloc[-1])))))
    if afficher_ma200 and (serie_ma200 is None or serie_ma200.empty):
        st.caption(t("MA200 indisponible : cette action n'a pas encore 200 jours d'historique."))

# ---------------------------------------------------------------
# Les actualités
# ---------------------------------------------------------------
articles = liste_actualites(choix)
scores = [sentiment.score_titre(a["titre"]) for a in articles]


def bloc_actualites(compact):
    """Carte des actualités. compact=True : version étroite pour la colonne de droite."""
    st.markdown(f'<h2 class="tb-titre-carte">{t("Actualités · {ticker}", ticker=choix)}</h2>', unsafe_allow_html=True)
    if not articles:
        st.caption(t("Aucune actualité disponible pour le moment (la source peut être indisponible)."))
        return
    resume_sentiment = sentiment.synthese(scores)
    if resume_sentiment:
        st.caption(
            t("Sentiment : **{e}** ({m:+.2f})", e=t(resume_sentiment["etiquette"]), m=resume_sentiment["moyenne"]) + " · "
            f"🟢 {resume_sentiment['positifs']} · ⚪ {resume_sentiment['neutres']} · 🔴 {resume_sentiment['negatifs']}"
        )
    for article, score in zip(articles, scores):
        ligne = " · ".join(x for x in (article["source"], langue.depuis(actualites.depuis(article["date"]))) if x)
        st.markdown(
            f'<div class="tb-actu{" tb-actu-compacte" if compact else ""}">'
            f'<a href="{html.escape(article["lien"] or "#")}" target="_blank">{sentiment.pastille(score)} {html.escape(article["titre"])}</a>'
            f'<div class="tb-discret">{ligne}</div></div>',
            unsafe_allow_html=True,
        )
    st.caption(t(
        "Articles en général en anglais (Yahoo Finance). Le sentiment est un simple décompte de mots "
        "positifs et négatifs dans le titre : indicatif."
    ))


# Toujours à droite du graphique
with col_actus.container(border=True):
    bloc_actualites(compact=True)

# ---------------------------------------------------------------
# Colonne de droite : les alertes
# ---------------------------------------------------------------
with carte_alertes:
    st.markdown(f'<h2 class="tb-titre-carte">{t("Alertes actives")}</h2>', unsafe_allow_html=True)
    alertes = db.lister_alertes()
    if not alertes:
        st.caption(t("Aucune alerte pour le moment."))
    for alerte in alertes:
        with st.container(border=True):
            c_texte, c_bouton = st.columns([5, 1])
            c_texte.write(f"**{alerte['ticker']}**  {libelle(alerte)}")
            if c_bouton.button("✕", key=f"suppr_{alerte['id']}", help=t("Supprimer cette alerte")):
                db.supprimer_alerte(alerte["id"])
                st.rerun()

    if alertes and st.button(t("Vérifier les alertes maintenant")):
        declenchees, echecs = verifier_alertes()
        for alerte, mesure, information in declenchees:
            ajouter_message("warning", t("Alerte déclenchée · {texte} ({info})", texte=decrire_alerte(alerte, mesure), info=information))
        for alerte, mesure, explication in echecs:
            ajouter_message(
                "error",
                t("Seuil franchi · {texte}, mais le message Telegram n'est pas parti : {explication} L'alerte reste active.",
                  texte=decrire_alerte(alerte, mesure), explication=explication),
            )
        if not declenchees and not echecs:
            ajouter_message("success", t("Vérification faite : aucun seuil n'est franchi."))
        st.rerun()

    if telegram_configure():
        st.caption(t("Notifications Telegram : activées."))
    else:
        st.caption(t("Notifications Telegram : non configurées (fichier .env à créer)."))

    with st.popover(t("＋ Nouvelle alerte sur {ticker}", ticker=choix), type="primary", width="stretch"):

        if cible is not None and cible != symbole:
            st.caption(t("Les alertes de prix restent exprimées en {d}, la devise de cotation de {ticker}.", d=symbole, ticker=choix))
        type_choisi = st.radio(
            t("Type d'alerte"), ["Prix", "Variation du jour (%)", "RSI", "Croisement MA50/MA200", "Volume anormal"], format_func=t
        )

        if type_choisi == "RSI":
            type_alerte = "rsi"
            sens_choisi = st.radio(t("Prévenez-moi quand l'action est"), ["en surchauffe (RSI au-dessus de)", "en survente (RSI en dessous de)"], format_func=t)
            sens = "hausse" if sens_choisi.startswith("en surchauffe") else "baisse"
            seuil = st.number_input(
                t("Seuil du RSI"), min_value=1.0, max_value=99.0, value=70.0 if sens == "hausse" else 30.0, step=1.0, format="%.0f"
            )
        elif type_choisi == "Volume anormal":
            type_alerte = "volume_anormal"
            sens = "hausse"
            seuil = st.number_input(
                t("Volume du jour au moins égal à (× la moyenne des 20 derniers jours)"),
                min_value=1.2, max_value=10.0, value=2.0, step=0.1, format="%.1f",
            )
            st.caption(t("Le volume du jour est partiel tant que la bourse est ouverte : l'alerte peut partir en fin de séance."))
        elif type_choisi == "Croisement MA50/MA200":
            type_alerte = "croisement_ma"
            sens_choisi = st.radio(t("Prévenez-moi quand"), ["la MA50 passe au-dessus de la MA200", "la MA50 passe sous la MA200"], format_func=t)
            sens = "hausse" if "au-dessus" in sens_choisi else "baisse"
            seuil = 0.0
            st.caption(t("Alerte envoyée si le croisement a eu lieu pendant les 5 dernières séances."))
        elif type_choisi == "Prix":
            type_alerte = "prix"
            sens_choisi = st.radio(t("Prévenez-moi quand le cours est"), ["au-dessus de", "en dessous de"], horizontal=True, format_func=t)
            sens = "hausse" if sens_choisi == "au-dessus de" else "baisse"
            seuil = st.number_input(
                t("Seuil ({d})", d=symbole), min_value=0.01, value=round(float(dernier), 2), step=1.0, format="%.2f"
            )
        else:
            type_alerte = "variation_jour"
            sens_choisi = st.radio(t("Prévenez-moi quand l'action"), ["monte d'au moins", "baisse d'au moins"], horizontal=True, format_func=t)
            sens = "hausse" if sens_choisi == "monte d'au moins" else "baisse"
            seuil = st.number_input(t("Variation sur la journée (%)"), min_value=0.1, value=5.0, step=0.1, format="%.1f")

        if st.button(t("Créer l'alerte")):
            db.creer_alerte(choix, sens, float(seuil), type_alerte)
            ajouter_message("success", t("Alerte créée sur {ticker}.", ticker=choix))

            # On prévient si la condition est déjà vraie : l'alerte partira à la prochaine vérification
            if type_alerte == "prix":
                deja_franchi = (dernier >= seuil) if sens == "hausse" else (dernier <= seuil)
            elif type_alerte in ("rsi", "croisement_ma", "volume_anormal"):
                nouvelle = {"ticker": choix, "type": type_alerte, "sens": sens, "seuil": float(seuil)}
                mesure_actuelle = mesurer(nouvelle, {})
                deja_franchi = mesure_actuelle is not None and condition_remplie(nouvelle, mesure_actuelle)
            else:
                resume = resume_du_jour(choix)
                variation_actuelle = resume[1] if resume else None
                deja_franchi = variation_actuelle is not None and (
                    variation_actuelle >= seuil if sens == "hausse" else variation_actuelle <= -seuil
                )
            if deja_franchi:
                ajouter_message(
                    "info",
                    t("Cette condition est déjà remplie actuellement : l'alerte se déclenchera "
                      "à la prochaine vérification."),
                )
            st.rerun()

with carte_historique:
    st.markdown(f'<h2 class="tb-titre-carte">{t("Alertes déclenchées")}</h2>', unsafe_allow_html=True)
    historique_alertes = db.lister_historique()
    if historique_alertes:
        st.dataframe(
            [
                {
                    t("Date"): h["date_declenchement"],
                    t("Action"): h["ticker"],
                    t("Condition"): libelle(h),
                    t("Cours au déclenchement"): f"{h['cours']:.2f} {devise(h['ticker'])}"
                    + (f" ({h['variation']:+.2f} %)" if h["variation"] is not None else ""),
                }
                for h in historique_alertes[:5]   # les 5 plus récentes ; le CSV contient tout l'historique
            ],
            hide_index=True,
            use_container_width=True,
        )
        st.download_button(
            t("Télécharger l'historique (CSV)"),
            export.vers_csv(
                [
                    {
                        "Date": h["date_declenchement"], "Action": h["ticker"], "Condition": libelle_condition(h),
                        "Cours": h["cours"], "Variation du jour (%)": h["variation"],
                    }
                    for h in historique_alertes
                ]
            ),
            file_name="historique_alertes.csv",
            mime="text/csv",
        )
    else:
        st.caption(t("Aucune alerte déclenchée pour le moment."))

st.caption(t("Outil d'aide à la décision, ne constitue pas un conseil financier."))
