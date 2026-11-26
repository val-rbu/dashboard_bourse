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
import json
import os
import re
import secrets
import tempfile
import time
import uuid
from pathlib import Path

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
import notifications
from notifications import telegram_configure
try:   # champ de recherche avec liste déroulante en direct (paquet facultatif : pip install streamlit-searchbox)
    from streamlit_searchbox import st_searchbox
except ImportError:
    st_searchbox = None
try:   # petit composant qui lit et écrit la mémoire du navigateur (localStorage) : sert au site en ligne
    from streamlit_js_eval import streamlit_js_eval
except ImportError:
    streamlit_js_eval = None

from verificateur import condition_remplie, decrire, devise_alerte, devise_mesure, libelle_condition, mesurer, verifier_alertes

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

# ---------------------------------------------------------------
# Base de données et compte du visiteur
# ---------------------------------------------------------------
# Sur ton PC : le fichier bourse.db et ton Telegram du fichier .env (comme toujours).
# Sur le site (secret MODE_EN_LIGNE = "1") :
#   - un visiteur non connecté a une base temporaire (effacée au bout d'une journée) et pas de Telegram ;
#   - un visiteur connecté avec Telegram retrouve ses données dans la base Neon (secret DATABASE_URL),
#     reçoit ses alertes sur SON Telegram, et le navigateur se souvient de lui (cookie).
EN_LIGNE = os.getenv("MODE_EN_LIGNE") == "1"
ADRESSE_BASE = (os.getenv("DATABASE_URL") or "").strip()
COMPTES = EN_LIGNE and bool(ADRESSE_BASE)   # la connexion avec Telegram n'existe qu'en ligne, avec la base Neon
CHAT_ID_VALIDE = r"-?\d{5,15}"
NOM_COOKIE = "tb_session"
DUREE_COOKIE_SECONDES = 90 * 24 * 3600


def utiliser_base_invite():
    """Base temporaire propre à ce visiteur (site en ligne, sans compte)."""
    if "id_visiteur" not in st.session_state:
        # L'adresse de la page garde le numéro du visiteur (?v=…) : recharger la page retrouve la même base
        id_url = st.query_params.get("v", "")
        if re.fullmatch(r"[0-9a-f]{32}", id_url):
            st.session_state.update(id_visiteur=id_url, invite_fixe=True)
        else:
            st.session_state["id_visiteur"] = uuid.uuid4().hex
        for ancien in Path(tempfile.gettempdir()).glob("bourse_visiteur_*.db"):
            try:
                if time.time() - ancien.stat().st_mtime > 86400:
                    ancien.unlink()
            except OSError:
                pass
    # Nouvel onglet sans ?v= : la mémoire du navigateur peut redonner le numéro de la visite précédente
    if "memoire" in st.session_state and not st.session_state.get("invite_fixe"):
        id_memoire = st.session_state["memoire"].get("v", "")
        fichier = Path(tempfile.gettempdir()) / f"bourse_visiteur_{id_memoire}.db"
        if re.fullmatch(r"[0-9a-f]{32}", id_memoire) and fichier.exists():
            st.session_state.update(id_visiteur=id_memoire, liste_initialisee=True)
        st.session_state["invite_fixe"] = True
    if st.query_params.get("v") != st.session_state["id_visiteur"]:
        st.query_params["v"] = st.session_state["id_visiteur"]
    db.utiliser_sqlite(Path(tempfile.gettempdir()) / f"bourse_visiteur_{st.session_state['id_visiteur']}.db")
    db.initialiser()
    # La liste de départ est créée une seule fois (même si le premier chargement a été interrompu)
    if not st.session_state.get("liste_initialisee"):
        if not db.lister_watchlist():
            for ticker_depart in db.LISTE_PAR_DEFAUT:
                db.ajouter_ticker(ticker_depart)
        st.session_state["liste_initialisee"] = True


def lire_memoire_navigateur():
    """Lit, une fois par visite, ce que le navigateur a gardé : connexion (s) et numéro d'invité (v).

    La réponse du navigateur arrive à l'affichage suivant : d'ici là, la fonction ne fait rien.
    """
    if streamlit_js_eval is None or "memoire" in st.session_state:
        return
    brut = streamlit_js_eval(
        js_expressions="JSON.stringify({s: localStorage.getItem('tb_session') || '', v: localStorage.getItem('tb_invite') || ''})",
        key="lire_memoire",
    )
    if brut is not None:
        try:
            st.session_state["memoire"] = json.loads(brut)
        except (TypeError, ValueError):
            st.session_state["memoire"] = {}


def memoriser(nom, valeur):
    """Garde une valeur dans la mémoire du navigateur (ou l'efface si valeur est None), jusqu'à confirmation."""
    if streamlit_js_eval is None or "memoire" not in st.session_state:
        return   # on attend d'avoir lu la mémoire, pour ne rien écraser
    if valeur is None:
        expression, cle = f"(localStorage.removeItem('{nom}'), 'ok')", f"oublier_{nom}"
    else:
        expression, cle = f"(localStorage.setItem('{nom}', '{valeur}'), 'ok')", f"garder_{nom}_{valeur}"
    faits = st.session_state.setdefault("memoire_faite", set())
    if cle not in faits and streamlit_js_eval(js_expressions=expression, key=cle) == "ok":
        faits.add(cle)


def connecter(utilisateur):
    """Connecte le visiteur à son compte. Un compte tout neuf récupère ce qu'il avait fait en invité."""
    invite = (db.lister_watchlist(), db.lister_alertes(), db.lister_positions())
    db.utiliser_postgres(ADRESSE_BASE, utilisateur)
    if db.initialiser():   # compte créé à l'instant : on y recopie la liste, les alertes et le portefeuille
        liste, alertes_invite, positions_invite = invite
        for ticker_invite in liste:
            db.ajouter_ticker(ticker_invite)
        for a in alertes_invite:
            db.creer_alerte(a["ticker"], a["sens"], a["seuil"], a["type"], a.get("devise"))
        for lot in positions_invite:
            db.ajouter_position(lot["ticker"], lot["quantite"], lot["prix_achat"])
    jeton = secrets.token_urlsafe(32)
    db.creer_session(jeton, utilisateur)
    st.session_state.update(utilisateur=utilisateur, jeton=jeton, compte_pret=True, oublier_session=False)
    st.query_params["s"] = jeton          # l'adresse de la page garde la connexion (rechargement, favori)
    if "v" in st.query_params:
        del st.query_params["v"]
    st.session_state.pop("code_connexion", None)
    st.rerun()


def deconnecter():
    """Oublie le compte sur ce navigateur (les données restent dans le compte)."""
    if st.session_state.get("jeton"):
        db.supprimer_session(st.session_state["jeton"])
    for cle in ("utilisateur", "jeton", "compte_pret"):
        st.session_state.pop(cle, None)
    st.session_state["oublier_session"] = True
    st.session_state.setdefault("memoire", {})["s"] = ""
    st.session_state.get("memoire_faite", set()).discard("oublier_tb_session")   # pour pouvoir l'effacer à nouveau
    if "s" in st.query_params:
        del st.query_params["s"]
    st.rerun()


if not EN_LIGNE:
    db.utiliser_sqlite()   # ton PC : bourse.db
    db.initialiser()
else:
    lire_memoire_navigateur()
    # Visiteur qui revient : sa connexion est dans l'adresse (?s=…), la mémoire du navigateur ou un cookie
    if COMPTES and not st.session_state.get("utilisateur"):
        essayes = st.session_state.setdefault("jetons_essayes", set())
        candidats = [st.query_params.get("s"), (st.session_state.get("memoire") or {}).get("s"), st.context.cookies.get(NOM_COOKIE)]
        for jeton_candidat in candidats:
            if not jeton_candidat or jeton_candidat in essayes:
                continue
            essayes.add(jeton_candidat)
            try:
                db.utiliser_postgres(ADRESSE_BASE)
                db.initialiser()
                utilisateur_trouve = db.utilisateur_de_session(jeton_candidat)
            except Exception:
                break   # base injoignable : le visiteur continue en invité
            if utilisateur_trouve:
                st.session_state.update(utilisateur=utilisateur_trouve, jeton=jeton_candidat)
                break
            if st.query_params.get("s") == jeton_candidat:
                del st.query_params["s"]   # connexion expirée ou fermée
            if (st.session_state.get("memoire") or {}).get("s") == jeton_candidat:
                st.session_state["oublier_session"] = True

    UTILISATEUR = st.session_state.get("utilisateur") if COMPTES else None
    if UTILISATEUR:
        try:
            db.utiliser_postgres(ADRESSE_BASE, UTILISATEUR)
            if not st.session_state.get("compte_pret"):
                db.initialiser()
                st.session_state["compte_pret"] = True
            notifications.definir_chat_id_visiteur(UTILISATEUR)   # ses alertes partent vers SON Telegram
            if st.session_state.get("jeton") and st.query_params.get("s") != st.session_state["jeton"]:
                st.query_params["s"] = st.session_state["jeton"]   # garde la connexion dans l'adresse
            if "v" in st.query_params:
                del st.query_params["v"]
        except Exception:
            st.error(t("La base en ligne ne répond pas : tu es en mode invité pour le moment."))
            UTILISATEUR = None
    if not UTILISATEUR:
        utiliser_base_invite()
        if COMPTES:
            notifications.definir_chat_id_visiteur("")   # invité : il faut se connecter pour recevoir des alertes
        else:
            _id_saisi = (st.session_state.get("chat_id_visiteur") or "").strip()
            notifications.definir_chat_id_visiteur(_id_saisi if re.fullmatch(CHAT_ID_VALIDE, _id_saisi) else "")

    # Mémoire du navigateur : elle retrouve la visite même après la fermeture de l'onglet
    if UTILISATEUR and st.session_state.get("jeton"):
        memoriser("tb_session", st.session_state["jeton"])
    elif st.session_state.get("oublier_session"):
        memoriser("tb_session", None)
    if not UTILISATEUR:
        memoriser("tb_invite", st.session_state["id_visiteur"])
UTILISATEUR = st.session_state.get("utilisateur") if COMPTES else None


@st.cache_data(ttl=3600, show_spinner=False)
def nom_du_bot():
    """Nom du bot Telegram du site (gardé une heure)."""
    return notifications.nom_du_bot()


# Pour chaque bouton de période : (durée à récupérer, intervalle entre deux points)
PERIODES = {
    "1J": ("1d", "5m"),
    "1S": ("5d", "30m"),
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
COULEUR_MA50 = "#A78BFA"
COULEUR_MA200 = "#F59E0B"
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
    return langue.libelle_condition(alerte, devise_alerte(alerte))


def decrire_alerte(alerte, mesure):
    """Description d'une alerte déclenchée, dans la langue de l'interface."""
    return langue.decrire(alerte, mesure, devise_mesure(alerte))


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
    cle = f"{cle}_{langue.LANGUE}"   # une liste par langue : sinon le libellé affiché ne change pas de langue
    actuel = st.session_state.get("devise_choisie", ORIGINE)
    if cle not in st.session_state:
        st.session_state[cle] = actuel
    st.selectbox(t("Devise d'affichage"), OPTIONS_DEVISE, key=cle, on_change=_memoriser_devise, args=(cle,),
                 label_visibility="collapsed", format_func=t)


# ---------------------------------------------------------------
# Navigation, barre du haut et liste de suivi (disposition de la maquette « refonte moderne »)
# ---------------------------------------------------------------
# Graphiques sans la barre d'outils de Plotly (appareil photo, zoom, déplacement...) qui apparaissait au survol
CONFIG_GRAPHIQUE = {"displayModeBar": False}
PRENOM = "" if os.getenv("MODE_EN_LIGNE") == "1" else "Valentin"   # prénom du message d'accueil (aucun sur le site en ligne)
liste_suivi = db.lister_watchlist()
VUES = ["Une action", "Comparaison", "Portefeuille", "Backtest", "Projection"]
# Pour chaque vue : (nom dans la barre de navigation, icône Material de Streamlit)
NAVIGATION = {
    "Une action": ("Tableau de bord", ":material/space_dashboard:"),
    "Comparaison": ("Comparaison", ":material/show_chart:"),
    "Portefeuille": ("Portefeuille", ":material/donut_large:"),
    "Backtest": ("Backtest", ":material/history:"),
    "Projection": ("Projection", ":material/timeline:"),
}
if st.session_state.get("vue") not in VUES:
    st.session_state["vue"] = VUES[0]

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def nb(valeur, decimales=2):
    """Nombre mis en forme : « 1 234,56 » en français, « 1,234.56 » en anglais."""
    texte = f"{valeur:,.{decimales}f}"
    if langue.LANGUE == "fr":
        texte = texte.replace(",", " ").replace(".", ",")
    return texte


def bourse_ouverte(fuseau, ouverture, fermeture):
    """Vrai si la bourse est ouverte maintenant (horaires en heures locales, du lundi au vendredi, jours fériés ignorés)."""
    maintenant = pd.Timestamp.now(tz=fuseau)
    minutes = maintenant.hour * 60 + maintenant.minute
    return maintenant.weekday() < 5 and ouverture <= minutes < fermeture


def sous_titre_accueil():
    """« Mardi 24 novembre · Paris fermé · New York ouvert »."""
    aujourd_hui = pd.Timestamp.now(tz="Europe/Paris")
    date = t("{jour} {n} {mois}", jour=t(JOURS[aujourd_hui.weekday()]), n=aujourd_hui.day, mois=t(MOIS[aujourd_hui.month - 1]))
    paris = bourse_ouverte("Europe/Paris", 9 * 60, 17 * 60 + 30)
    new_york = bourse_ouverte("America/New_York", 9 * 60 + 30, 16 * 60)
    return " · ".join([
        date,
        t("{place} ouvert", place="Paris") if paris else t("{place} fermé", place="Paris"),
        t("{place} ouvert", place="New York") if new_york else t("{place} fermé", place="New York"),
    ])


@st.cache_data(ttl=86400)
def infos_action(ticker):
    """(nom de la société, place de cotation) d'après la recherche Yahoo, mémorisés un jour ; ("", "") si inconnus."""
    if ticker in INDICES:
        return INDICES[ticker], ""
    for resultat in rechercher_actions(ticker):
        if resultat.get("symbol") == ticker:
            return resultat.get("shortname") or resultat.get("longname") or "", resultat.get("exchDisp") or ""
    return "", ""


def zone_recherche(cle):
    """Recherche d'une action par nom ou ticker ; choisir un résultat l'ajoute à la liste de suivi et l'affiche."""
    if st_searchbox is not None:
        libelle_choisi = st_searchbox(chercher, placeholder=t("Rechercher une action, un indice…"), key=cle)
    else:
        texte_recherche = st.text_input(t("Rechercher"), placeholder=t("Rechercher une action, un indice…"), key=cle,
                                        label_visibility="collapsed") or ""
        propositions = chercher(texte_recherche) if len(texte_recherche.strip()) >= 2 else []
        libelle_choisi = st.selectbox(t("Résultats"), propositions, key=cle + "_resultats",
                                      label_visibility="collapsed") if propositions else None
        if texte_recherche.strip() and not propositions:
            st.caption(t("Aucun résultat."))
    if not libelle_choisi:
        return
    symbole_choisi = recherche.symbole_depuis_libelle(libelle_choisi)
    if symbole_choisi is None:
        st.warning(t("Choix non reconnu : recommence la recherche."))
    elif symbole_choisi in liste_suivi:
        if st.button(t("Ouvrir {ticker}", ticker=symbole_choisi), key=cle + "_ouvrir"):
            st.session_state.update(choix=symbole_choisi, vue="Une action")
            st.rerun()
    elif st.button(t("Ajouter {ticker}", ticker=symbole_choisi), key=cle + "_ajouter", type="primary"):
        if recuperer_cours(symbole_choisi, "5d", "1d").empty:
            st.error(t("Aucune donnée de cours pour {ticker} : essaie une autre valeur.", ticker=symbole_choisi))
        else:
            db.ajouter_ticker(symbole_choisi)
            st.session_state.update(choix=symbole_choisi, vue="Une action")
            st.rerun()


def _changer_reglage(nom):
    """Recopie le choix du bouton (langue) dans la session ; un clic qui désélectionne ne change rien."""
    valeur = st.session_state[f"bouton_{nom}"]
    if valeur is not None:
        st.session_state[nom] = valeur


def _basculer_theme():
    st.session_state["mode"] = "clair" if st.session_state["mode"] == "sombre" else "sombre"


# Barre de navigation : la barre latérale de Streamlit, réduite à une colonne d'icônes
with st.sidebar:
    st.markdown('<div class="tb-logo" aria-hidden="true">B</div>', unsafe_allow_html=True)
    for numero, nom_vue in enumerate(VUES):
        nom_nav, icone = NAVIGATION[nom_vue]
        if st.button(t(nom_nav), key=f"nav_{numero}", icon=icone,
                     type="primary" if st.session_state["vue"] == nom_vue else "tertiary"):
            st.session_state["vue"] = nom_vue
            st.rerun()
vue = st.session_state["vue"]

# Barre du haut : accueil | recherche | devise | langue | thème
with st.container(key="barre_haut"):
    c_salut, c_recherche, c_devise, c_langue, c_theme = st.columns([3.1, 2.7, 1.3, 0.95, 0.45], vertical_alignment="center")
    with c_salut:
        st.markdown(
            f'<div class="tb-salut"><h1>{t("Bonjour {prenom}", prenom=PRENOM).strip()}</h1><div>{sous_titre_accueil()}</div></div>',
            unsafe_allow_html=True,
        )
    with c_recherche:
        zone_recherche("recherche_haut")
    with c_devise:
        selecteur_devise("devise_haut")
    with c_langue:
        st.session_state["bouton_langue"] = st.session_state["langue"]
        st.segmented_control(t("Langue"), ["fr", "en"], key="bouton_langue", label_visibility="collapsed",
                             format_func=str.upper, on_change=_changer_reglage, args=("langue",))
    with c_theme:
        sombre = st.session_state["mode"] == "sombre"
        st.button(t("Thème"), key="bouton_theme", icon=":material/light_mode:" if sombre else ":material/dark_mode:",
                  help=t("Passer en mode clair") if sombre else t("Passer en mode sombre"), on_click=_basculer_theme)

afficher_messages()

# Liste de suivi : une rangée de cartes cliquables, puis la carte « + Ajouter »
if liste_suivi and st.session_state.get("choix") not in liste_suivi:
    st.session_state["choix"] = liste_suivi[0]
choix = st.session_state.get("choix") if liste_suivi else None

PAR_RANGEE = 8
elements_suivi = liste_suivi + ["+"]
for debut in range(0, len(elements_suivi), PAR_RANGEE):
    for colonne, element in zip(st.columns(PAR_RANGEE), elements_suivi[debut:debut + PAR_RANGEE]):
        with colonne:
            if element == "+":
                with st.popover(t("＋ Ajouter"), key="pop_ajout", width="stretch"):
                    zone_recherche("recherche_ajout")
                continue
            resume_l = resume_du_jour(element)
            with st.container(key="carte_" + re.sub(r"\W", "_", element)):
                if resume_l is None:
                    carte_html = style.carte_suivi(element, None, 0, "", infos_action(element)[0], element == choix)
                else:
                    carte_html = style.carte_suivi(
                        element,
                        f"{nb(resume_l[0] * facteur_vers_cible(element))} {symbole_affiche(element)}",
                        resume_l[1],
                        f"{'+' if resume_l[1] >= 0 else '−'}{nb(abs(resume_l[1]))} %",
                        infos_action(element)[0],
                        element == choix,
                    )
                st.markdown(carte_html, unsafe_allow_html=True)
                # Bouton invisible posé sur toute la carte : un clic sur la carte choisit l'action
                if st.button(t("Choisir {ticker}", ticker=element), key=f"choisir_{element}"):
                    st.session_state["choix"] = element   # on reste sur la vue en cours
                    st.rerun()
                # Petite croix en bas à droite de la carte (visible au survol) : retirer l'action, après confirmation
                with st.popover("✕", key=f"retrait_{element}", help=t("Retirer {ticker} de la liste", ticker=element)):
                    st.markdown(t("Retirer **{ticker}** de ta liste ? Ses alertes actives seront aussi supprimées.", ticker=element))
                    if st.button(t("Retirer"), key=f"confirmer_retrait_{element}", type="primary"):
                        db.retirer_ticker(element)   # supprime aussi ses alertes actives
                        if st.session_state.get("choix") == element:
                            st.session_state.pop("choix")
                        st.rerun()


# ---------------------------------------------------------------
# Vue Portefeuille : mes achats, leur valeur et mon gain
# ---------------------------------------------------------------
if vue == "Portefeuille":
    with st.container(border=True, key="vue_0"):   # la vue dans une grande carte
        st.subheader(t("Mon portefeuille"))

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
        if len(totaux) > 1:
            st.info(t("Ton portefeuille mélange des actions en euros et en dollars : il y a donc un total par devise. "
                      "Choisis une devise dans la liste en haut de la page (par exemple « Euro (€) ») pour tout regrouper en un seul total."))
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
                    go.Pie(labels=[l["ticker"] for l in parts], values=[l["valeur"] for l in parts], hole=0.6,
                           marker=dict(colors=[style.TURQUOISE, style.VIOLET, style.JAUNE, style.BLEU, style.VERT, style.ROUGE]))
                )
                fig_pie.update_layout(title=t("Répartition ({d})", d=symbole_dev))
                style.theme_graphique(fig_pie, 380)
                colonne.plotly_chart(fig_pie, use_container_width=True, config=CONFIG_GRAPHIQUE)

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
    with st.container(border=True, key="vue_1"):   # la vue dans une grande carte
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
        st.plotly_chart(fig_comp, use_container_width=True, config=CONFIG_GRAPHIQUE)

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
    st.info(t("Ta liste de suivi est vide : ajoute une action avec la recherche en haut."))
    st.stop()

# ---------------------------------------------------------------
# Vue Backtest : tester une règle d'achat et de vente sur le passé
# ---------------------------------------------------------------
if vue == "Backtest":
    with st.container(border=True, key="vue_2"):   # la vue dans une grande carte
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
        st.plotly_chart(fig_bt, use_container_width=True, config=CONFIG_GRAPHIQUE)

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
    with st.container(border=True, key="vue_3"):   # la vue dans une grande carte
        st.subheader(t("Projection de tendance · {ticker}", ticker=choix))
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
        st.plotly_chart(fig_p, use_container_width=True, config=CONFIG_GRAPHIQUE)

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

# ---------------------------------------------------------------
# Vue Une action (tableau de bord) : grande carte du cours | signaux techniques et alertes,
# puis actualités | portefeuille
# ---------------------------------------------------------------
LIBELLES_PERIODES = {"1J": "1 jour", "1S": "1 semaine", "1M": "1 mois", "1A": "1 an", "5A": "5 ans"}
INDICATEURS = ["MA 50", "MA 200", "Bollinger", "RSI", "MACD"]

col_gauche, col_droite = st.columns([2, 1], gap="medium")
with col_droite:
    carte_signaux = st.container(border=True, key="bloc_signaux")
    carte_alertes = st.container(border=True, key="bloc_alertes")
carte = col_gauche.container(border=True, key="bloc_cours")   # la grande carte : titre, graphique et chiffres clés
with carte:
    c_titre, c_reglages = st.columns([1.1, 1])
    zone_titre = c_titre.container()   # remplie plus bas, quand le cours est connu
    with c_reglages:
        c_periode, c_type = st.columns([3.4, 1.2])
        with c_periode:
            periode_choisie = choix_boutons("Période", list(PERIODES), "1M", "periode")
        with c_type:
            type_graphique = st.segmented_control(
                t("Type de graphique"), ["Courbe", "Chandeliers"], default="Courbe", key="type_graphique",
                label_visibility="collapsed",
                format_func=lambda o: ":material/show_chart:" if o == "Courbe" else ":material/candlestick_chart:",
            ) or "Courbe"
        # Les indicateurs sont calculés sur des clôtures journalières : pas disponibles pour 1J et 1S
        indicateurs_disponibles = periode_choisie not in ("1J", "1S")
        indicateurs_choisis = st.pills(
            t("Indicateurs"), INDICATEURS, selection_mode="multi", key="indicateurs",
            label_visibility="collapsed", disabled=not indicateurs_disponibles,
        ) or []
        if not indicateurs_disponibles:
            st.caption(t("Les indicateurs utilisent des clôtures journalières : choisis une période de 1M ou plus."))

# Une pastille grisée peut rester choisie : on ne tient compte que des pastilles actives
afficher_ma50 = "MA 50" in indicateurs_choisis and indicateurs_disponibles
afficher_ma200 = "MA 200" in indicateurs_choisis and indicateurs_disponibles
afficher_rsi = "RSI" in indicateurs_choisis and indicateurs_disponibles
afficher_boll = "Bollinger" in indicateurs_choisis and indicateurs_disponibles
afficher_macd = "MACD" in indicateurs_choisis and indicateurs_disponibles

periode, intervalle = PERIODES[periode_choisie]
cours = recuperer_cours(choix, periode, intervalle)

if cours.empty:
    st.warning(t("Impossible de récupérer les cours pour le moment. Réessaie dans une minute."))
    st.stop()

symbole = devise(choix)              # devise de cotation : c'est elle qui sert aux alertes
dernier = cours["Close"].iloc[-1]    # dernier cours dans la devise de cotation

# Pour l'affichage (chiffres et graphique), on convertit dans la devise choisie
cours_aff = conv(cours, choix)
symbole_aff = symbole_affiche(choix)
dernier_aff = cours_aff["Close"].iloc[-1]
premier_aff = cours_aff["Close"].iloc[0]
variation_periode = (dernier_aff - premier_aff) / premier_aff * 100

# Titre de la carte : nom, place de cotation, prix en grand, variation dans une étiquette colorée
nom_societe, place = infos_action(choix)
puce = " · ".join(x for x in (choix, place) if x)
hausse_periode = variation_periode >= 0
with zone_titre:
    st.markdown(
        f'<div class="tb-nom"><h2>{html.escape(nom_societe or choix)}</h2><span class="tb-puce">{html.escape(puce)}</span></div>'
        f'<div class="tb-ligne-prix"><span class="tb-gros-prix">{nb(dernier_aff)} {symbole_aff}</span>'
        f'<span class="tb-badge {"hausse" if hausse_periode else "baisse"}">{"▲" if hausse_periode else "▼"} '
        f'{nb(abs(variation_periode))} % · {t(LIBELLES_PERIODES[periode_choisie])}</span></div>',
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
                   line=dict(color=style.TURQUOISE, width=2.5), fill="tonexty",
                   fillgradient=dict(type="vertical", colorscale=[[0, style.rgba(style.TURQUOISE, 0)], [1, style.rgba(style.TURQUOISE, 0.28)]])),
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
        d_seuil = devise_alerte(alerte)
        d_graphique = cible if cible is not None else devise(choix)
        taux_ligne = taux if d_seuil == "$" or d_seuil in taux else taux_du_jour()
        fig.add_hline(
            y=alerte["seuil"] * devises.facteur(d_seuil, d_graphique, taux_ligne),   # ligne placée dans la devise d'affichage
            line_dash="dash",
            line_color=style.JAUNE,
            annotation_text=t("Seuil d'alerte {signe} {x:.2f} {d}", signe=signe, x=alerte["seuil"], d=d_seuil),
            annotation_position="top right",
            annotation_font_color=style.JAUNE,
            row=1,
            col=1,
        )

fig.update_layout(
    yaxis_title=t("Prix ({d})", d=symbole_aff),
    xaxis_rangeslider_visible=False,
)
style.theme_graphique(fig, 320 + 170 * len(zones))
fig.update_layout(
    legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="left", x=0),   # légende sous le graphique
    margin=dict(l=10, r=10, t=10, b=40),
)
with carte:
    st.plotly_chart(fig, use_container_width=True, config=CONFIG_GRAPHIQUE)

    # Les quatre chiffres clés sous le graphique
    chiffres = [
        (t("Début de période"), f"{nb(cours_aff['Open'].iloc[0])} {symbole_aff}"),
        (t("Plus haut"), f"{nb(cours_aff['High'].max())} {symbole_aff}"),
        (t("Plus bas"), f"{nb(cours_aff['Low'].min())} {symbole_aff}"),
        (t("Volume cumulé"), f"{nb(cours['Volume'].sum() / 1e6, 1)} M"),
    ]
    st.markdown(
        '<div class="tb-stats">'
        + "".join(f'<div class="tb-stat"><div>{libelle_c}</div><div>{valeur_c}</div></div>' for libelle_c, valeur_c in chiffres)
        + "</div>",
        unsafe_allow_html=True,
    )

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
# Signaux techniques : l'état actuel, quelle que soit la période affichée
# ---------------------------------------------------------------
with carte_signaux:
    st.markdown(f'<div class="tb-titre"><h2>{t("Signaux techniques")}</h2></div>', unsafe_allow_html=True)
    hist5 = recuperer_cours(choix, "5y", "1d")
    clotures5 = hist5["Close"].dropna() if not hist5.empty else None
    lignes_signaux = []

    # RSI : jauge circulaire
    valeur_rsi = None
    if clotures5 is not None and len(clotures5) > 30:
        serie_r = ind.rsi(clotures5, 14).dropna()
        valeur_rsi = float(serie_r.iloc[-1]) if not serie_r.empty else None
    if valeur_rsi is None:
        bloc_rsi = f'<div class="tb-rsi">{style.anneau(0, "–", style.BORDURE, aria="RSI")}<div><b>RSI</b> · {t("n.d.")}</div></div>'
    else:
        if valeur_rsi <= 30:
            etat, detail, couleur = t("survente"), t("Sous 30 : l'action a beaucoup baissé récemment"), style.JAUNE
        elif valeur_rsi >= 70:
            etat, detail, couleur = t("surchauffe"), t("Au-dessus de 70 : l'action a beaucoup monté récemment"), style.JAUNE
        else:
            etat, detail, couleur = t("neutre"), t("Ni survente (30) ni surchauffe (70)"), style.TURQUOISE
        bloc_rsi = (
            f'<div class="tb-rsi">{style.anneau(valeur_rsi, f"{valeur_rsi:.0f}", couleur, aria=f"RSI {valeur_rsi:.0f} / 100")}'
            f'<div><b>{t("RSI 14 j · {etat}", etat=etat)}</b><div class="tb-discret" style="margin-top:4px">{detail}</div></div></div>'
        )

    # Moyennes mobiles, volume et MACD : une ligne chacun
    if clotures5 is not None and len(clotures5) >= 200:
        m50 = float(ind.moyenne_mobile(clotures5, 50).iloc[-1])
        m200 = float(ind.moyenne_mobile(clotures5, 200).iloc[-1])
        haussier = m50 > m200
        lignes_signaux.append((t("Moyennes mobiles"), "▲ MA50 &gt; MA200" if haussier else "▼ MA50 &lt; MA200",
                               style.VERT if haussier else style.ROUGE))
    else:
        lignes_signaux.append((t("Moyennes mobiles"), t("n.d."), style.TEXTE_DISCRET))
    rapport_vol = ind.rapport_volume(hist5["Volume"], 20) if clotures5 is not None else None
    if rapport_vol is None:
        lignes_signaux.append((t("Volume vs 20 j"), t("n.d."), style.TEXTE_DISCRET))
    else:
        avis = t("élevé") if rapport_vol >= 1.5 else t("faible") if rapport_vol <= 0.6 else t("normal")
        inhabituel = rapport_vol >= 1.5 or rapport_vol <= 0.6
        lignes_signaux.append((t("Volume vs 20 j"), f"{'+' if rapport_vol >= 1 else '−'}{nb(abs(rapport_vol - 1) * 100, 0)} % · {avis}",
                               style.JAUNE if inhabituel else style.TEXTE))
    if clotures5 is not None and len(clotures5) > 40:
        ligne_m5, signal_m5, _ = ind.macd(clotures5)
        elan_haussier = float(ligne_m5.iloc[-1]) > float(signal_m5.iloc[-1])
        lignes_signaux.append(("MACD", t("▲ élan haussier") if elan_haussier else t("▼ élan baissier"),
                               style.VERT if elan_haussier else style.ROUGE))
    st.markdown(
        bloc_rsi + "".join(
            f'<div class="tb-ligne"><span>{nom_s}</span><span style="color:{couleur_s}">{valeur_s}</span></div>'
            for nom_s, valeur_s, couleur_s in lignes_signaux
        ),
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------
# Alertes : actives (toutes les actions), dernières déclenchées, création
# ---------------------------------------------------------------
with carte_alertes:
    texte_non_configure = (t("○ Telegram : connecte-toi") if COMPTES else t("○ Telegram : ajoute ton identifiant") if EN_LIGNE
                           else t("○ Telegram non configuré (fichier .env)"))
    etat_telegram = (f'<span style="color:{style.VERT};font-size:12px">{t("● Telegram connecté")}</span>' if telegram_configure()
                     else f'<span class="tb-discret">{texte_non_configure}</span>')
    st.markdown(f'<div class="tb-titre"><h2>{t("Alertes")}</h2>{etat_telegram}</div>', unsafe_allow_html=True)

    # Site en ligne avec la base Neon : connexion avec Telegram (code à 6 chiffres envoyé par le bot)
    if COMPTES and UTILISATEUR:
        with st.expander(t("Mon compte Telegram")):
            st.caption(t("Connecté avec l'identifiant {id}. Tes alertes sont vérifiées automatiquement toutes les "
                         "15 minutes environ, même quand le site est fermé.", id=UTILISATEUR))
            if st.button(t("Se déconnecter"), key="deconnexion"):
                deconnecter()
    elif COMPTES:
        with st.expander(t("Se connecter avec Telegram")):
            bot = nom_du_bot()
            if not bot:
                st.caption(t("Les notifications Telegram ne sont pas disponibles sur ce site pour le moment."))
            else:
                st.caption(t("Connecte-toi pour retrouver ta liste, ton portefeuille et tes alertes à chaque visite, "
                             "et recevoir tes alertes automatiquement sur Telegram."))
                st.markdown(t("1. Ouvre [@{bot}](https://t.me/{bot}) dans Telegram et appuie sur **Démarrer**.", bot=bot))
                st.markdown(t("2. Envoie /start à [@userinfobot](https://t.me/userinfobot) : il te répond avec ton identifiant (« Id »)."))
                st.text_input(t("3. Ton identifiant Telegram"), key="id_connexion", placeholder="123456789")
                id_connexion = (st.session_state.get("id_connexion") or "").strip()
                if id_connexion and not re.fullmatch(CHAT_ID_VALIDE, id_connexion):
                    st.warning(t("Cet identifiant n'est pas valide : c'est un nombre, par exemple 123456789."))
                elif id_connexion and st.button(t("Recevoir un code"), key="envoyer_code"):
                    if time.time() - st.session_state.get("code_envoye_a", 0) < 30:
                        st.warning(t("Patiente 30 secondes avant de redemander un code."))
                    else:
                        code = f"{secrets.randbelow(10 ** 6):06d}"
                        try:
                            notifications.envoyer_message_a(
                                id_connexion, f"Ton code de connexion au tableau de bord : {code}\n(valable 10 minutes)"
                            )
                            st.session_state["code_connexion"] = {
                                "id": id_connexion, "code": code, "expire": time.time() + 600, "essais": 0,
                            }
                            st.session_state["code_envoye_a"] = time.time()
                            st.success(t("Code envoyé : regarde ton Telegram."))
                        except Exception as erreur:
                            st.error(notifications.expliquer_erreur(erreur))
                attente = st.session_state.get("code_connexion")
                if attente and attente["id"] == id_connexion:
                    st.text_input(t("4. Code reçu sur Telegram"), key="code_saisi", max_chars=6, placeholder="000000")
                    if st.button(t("Me connecter"), key="valider_code", type="primary"):
                        saisi = (st.session_state.get("code_saisi") or "").strip()
                        if time.time() > attente["expire"] or attente["essais"] >= 5:
                            st.session_state.pop("code_connexion", None)
                            st.error(t("Ce code n'est plus valable : demande un nouveau code."))
                        elif saisi == attente["code"]:
                            connecter(id_connexion)
                        else:
                            attente["essais"] += 1
                            st.error(t("Code incorrect."))
    # Site en ligne sans base Neon : le visiteur colle son identifiant pour la durée de sa visite
    elif EN_LIGNE:
        with st.expander(t("Recevoir mes alertes sur Telegram")):
            bot = nom_du_bot()
            if not bot:
                st.caption(t("Les notifications Telegram ne sont pas disponibles sur ce site pour le moment."))
            else:
                st.markdown(t("1. Ouvre [@{bot}](https://t.me/{bot}) dans Telegram et appuie sur **Démarrer**.", bot=bot))
                st.markdown(t("2. Envoie /start à [@userinfobot](https://t.me/userinfobot) : il te répond avec ton identifiant (« Id »)."))
                st.text_input(t("3. Colle ton identifiant ici"), key="chat_id_visiteur", placeholder="123456789")
                id_saisi = (st.session_state.get("chat_id_visiteur") or "").strip()
                if id_saisi and not re.fullmatch(CHAT_ID_VALIDE, id_saisi):
                    st.warning(t("Cet identifiant n'est pas valide : c'est un nombre, par exemple 123456789."))
                elif id_saisi and st.button(t("Envoyer un message de test"), key="test_telegram"):
                    try:
                        notifications.envoyer_message(
                            "Test du tableau de bord financier : tu recevras ici tes alertes."
                        )
                        st.success(t("Message envoyé : regarde ton Telegram."))
                    except Exception as erreur:
                        st.error(notifications.expliquer_erreur(erreur))
                st.caption(t("Ton identifiant n'est gardé que pendant ta visite. Les alertes sont vérifiées "
                             "quand tu cliques sur « Vérifier maintenant »."))
    alertes = db.lister_alertes()
    historique_alertes = db.lister_historique()
    if not alertes and not historique_alertes:
        st.caption(t("Aucune alerte pour le moment."))
    for alerte in alertes:
        c_texte, c_bouton = st.columns([7, 1], vertical_alignment="center")
        c_texte.markdown(
            f'<div class="tb-alerte"><span class="tb-point" style="background:{style.JAUNE}"></span>'
            f'<span class="tb-txt"><b>{alerte["ticker"]}</b> {html.escape(libelle(alerte))}</span>'
            f'<span class="tb-discret">{t("active")}</span></div>',
            unsafe_allow_html=True,
        )
        if c_bouton.button("✕", key=f"suppr_{alerte['id']}", help=t("Supprimer cette alerte"), type="tertiary"):
            db.supprimer_alerte(alerte["id"])
            st.rerun()
    for h in historique_alertes[:2]:   # les deux dernières alertes déclenchées
        date_h = pd.Timestamp(h["date_declenchement"])
        st.markdown(
            f'<div class="tb-alerte" style="margin-top:8px"><span class="tb-point" style="background:{style.VERT}"></span>'
            f'<span class="tb-txt"><b>{h["ticker"]}</b> {html.escape(libelle(h))} · {t("atteinte")}</span>'
            f'<span class="tb-discret">{date_h.day} {t(MOIS_COURTS[date_h.month - 1])}</span></div>',
            unsafe_allow_html=True,
        )

    with st.popover(t("＋ Nouvelle alerte"), type="primary", width="stretch", key="pop_alerte"):
        st.markdown(f"**{t('Nouvelle alerte sur {ticker}', ticker=choix)}**")
        devise_seuil = cible if cible is not None else symbole   # le seuil se saisit dans la devise affichée
        dernier_seuil = float(dernier) * facteur_vers_cible(choix)
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
                t("Seuil ({d})", d=devise_seuil), min_value=0.01, value=round(dernier_seuil, 2), step=1.0, format="%.2f"
            )
        else:
            type_alerte = "variation_jour"
            sens_choisi = st.radio(t("Prévenez-moi quand l'action"), ["monte d'au moins", "baisse d'au moins"], horizontal=True, format_func=t)
            sens = "hausse" if sens_choisi == "monte d'au moins" else "baisse"
            seuil = st.number_input(t("Variation sur la journée (%)"), min_value=0.1, value=5.0, step=0.1, format="%.1f")

        if st.button(t("Créer l'alerte"), type="primary"):
            db.creer_alerte(choix, sens, float(seuil), type_alerte, devise_seuil if type_alerte == "prix" else None)
            ajouter_message("success", t("Alerte créée sur {ticker}.", ticker=choix))

            # On prévient si la condition est déjà vraie : l'alerte partira à la prochaine vérification
            if type_alerte == "prix":
                deja_franchi = (dernier_seuil >= seuil) if sens == "hausse" else (dernier_seuil <= seuil)
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

    c_verifier, c_historique = st.columns(2)
    if alertes and c_verifier.button(t("Vérifier maintenant"), type="tertiary", icon=":material/refresh:"):
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
    if historique_alertes:
        with c_historique.popover(t("Historique"), type="tertiary", icon=":material/history:"):
            st.dataframe(
                [
                    {
                        t("Date"): h["date_declenchement"],
                        t("Action"): h["ticker"],
                        t("Condition"): libelle(h),
                        t("Cours au déclenchement"): f"{h['cours']:.2f} {h.get('devise') or devise(h['ticker'])}"
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
                            "Date": h["date_declenchement"], "Action": h["ticker"], "Condition": libelle(h),
                            "Cours": h["cours"], "Devise": h.get("devise") or devise(h["ticker"]), "Variation du jour (%)": h["variation"],
                        }
                        for h in historique_alertes
                    ]
                ),
                file_name="historique_alertes.csv",
                mime="text/csv",
            )

# ---------------------------------------------------------------
# Rangée du bas : actualités | portefeuille
# ---------------------------------------------------------------
col_actus, col_pf = st.columns([2, 1], gap="medium")

articles = liste_actualites(choix)
scores = [sentiment.score_titre(a["titre"]) for a in articles]
with col_actus.container(border=True, key="bloc_actus"):
    resume_sentiment = sentiment.synthese(scores)
    texte_sentiment = ""
    if resume_sentiment:
        texte_sentiment = t(
            "Sentiment global : {e} · {p} positifs · {n} neutres · {m} négatifs",
            e=f'<b style="color:{style.TEXTE}">{t(resume_sentiment["etiquette"])}</b>', p=resume_sentiment["positifs"],
            n=resume_sentiment["neutres"], m=resume_sentiment["negatifs"],
        )
    st.markdown(
        f'<div class="tb-titre"><h2>{t("Actualités · {ticker}", ticker=choix)}</h2><span class="tb-discret">{texte_sentiment}</span></div>',
        unsafe_allow_html=True,
    )
    if not articles:
        st.caption(t("Aucune actualité disponible pour le moment (la source peut être indisponible)."))
    else:
        cartes_actus = []
        for article, score in list(zip(articles, scores))[:6]:
            etiquette = sentiment.etiquette(score)   # "positif", "neutre" ou "négatif"
            classe = {"positif": "positif", "négatif": "negatif"}.get(etiquette, "neutre")
            ligne = " · ".join(x for x in (article["source"], langue.depuis(actualites.depuis(article["date"]))) if x)
            cartes_actus.append(
                f'<a class="tb-actu" href="{html.escape(article["lien"] or "#")}" target="_blank">'
                f'<span class="tb-sent {classe}">{t(etiquette.capitalize())}</span>'
                f'<span class="tb-txt"><span>{html.escape(article["titre"])}</span><span>{html.escape(ligne)}</span></span></a>'
            )
        st.markdown('<div class="tb-actus">' + "".join(cartes_actus) + "</div>", unsafe_allow_html=True)
        note_actus = t(
            "Articles en général en anglais (Yahoo Finance). Le sentiment est un simple décompte de mots "
            "positifs et négatifs dans le titre : indicatif."
        )
        st.markdown(f'<div class="tb-discret" style="margin-top:8px">{note_actus}</div>', unsafe_allow_html=True)

with col_pf.container(border=True, key="bloc_pf"):
    st.markdown(f'<div class="tb-titre"><h2>{t("Mon portefeuille")}</h2></div>', unsafe_allow_html=True)
    lots_pf = db.lister_positions()
    lignes_pf = []
    if lots_pf:
        cours_pf = {}
        for tk in {lot["ticker"] for lot in lots_pf}:
            resume_t = resume_du_jour(tk)
            cours_pf[tk] = float(resume_t[0]) if resume_t else None
        # Tout est additionné dans une même devise : celle choisie en haut, sinon l'euro
        devise_pf = cible or "€"
        taux_pf = taux if cible is not None else taux_du_jour()
        lignes_pf = [l for l in portefeuille.synthese(lots_pf, cours_pf) if l["valeur"] is not None]
        lignes_pf = portefeuille.convertir_lignes(lignes_pf, devise_pf, lambda de: devises.facteur(de, devise_pf, taux_pf))
    if not lignes_pf:
        st.caption(t("Ton portefeuille est vide : enregistre un achat dans la vue Portefeuille."))
        if st.button(t("Ouvrir le portefeuille"), key="ouvrir_pf"):
            st.session_state["vue"] = "Portefeuille"
            st.rerun()
    else:
        valeurs = {}
        for l in lignes_pf:
            valeurs[l["ticker"]] = valeurs.get(l["ticker"], 0) + l["valeur"]
        total_pf = sum(valeurs.values())
        investi_pf = sum(l["investi"] for l in lignes_pf)
        gain_pf = total_pf - investi_pf
        gain_pct_pf = gain_pf / investi_pf * 100 if investi_pf else 0.0
        couleurs_pf = [style.TURQUOISE, style.VIOLET, style.JAUNE, style.BLEU, style.VERT, style.ROUGE]
        repartition = sorted(valeurs.items(), key=lambda kv: -kv[1])
        parts = [(v / total_pf * 100 if total_pf else 0, couleurs_pf[i % len(couleurs_pf)]) for i, (_, v) in enumerate(repartition)]
        classe_gain = "tb-hausse" if gain_pf >= 0 else "tb-baisse"
        st.markdown(
            f'<div class="tb-pf">{style.donut(parts, aria=t("Répartition du portefeuille"))}'
            f'<div><div class="tb-discret">{t("Valeur totale")}</div><div class="tb-pf-total">{nb(total_pf)} {devise_pf}</div>'
            f'<div class="{classe_gain}" style="font-size:13px">{"▲" if gain_pf >= 0 else "▼"} {nb(abs(gain_pf))} {devise_pf} · '
            f'{"+" if gain_pct_pf >= 0 else "−"}{nb(abs(gain_pct_pf))} %</div></div></div>'
            + "".join(
                f'<div class="tb-pf-ligne"><span><span style="color:{couleur}">●</span> {tk}</span>'
                f'<span class="tb-discret">{nb(pct, 0)} %</span></div>'
                for (tk, _), (pct, couleur) in zip(repartition, parts)
            ),
            unsafe_allow_html=True,
        )

# Pied de page : taux de change utilisé et avertissement
pied = [t("Cours différés d'environ 15 minutes · source : Yahoo Finance")]
if cible is not None:
    if cible == "$":
        pied.append(t("{a} = {x:.4f} {b} · taux actuel", a="1 €", x=devises.facteur("€", "$", taux), b="$"))
    else:
        pied.append(t("{a} = {x:.4f} {b} · taux actuel", a="1 $", x=devises.facteur("$", cible, taux), b=cible))
pied.append(t("Outil d'aide à la décision, pas un conseil financier."))
st.markdown(f'<div class="tb-pied">{" · ".join(pied)}</div>', unsafe_allow_html=True)
