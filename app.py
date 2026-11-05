"""Étape 9 : tableau de bord financier (indicateurs, alertes, comparaison, portefeuille, actualités).

Pour lancer l'application, dans le terminal :
    streamlit run app.py

Fichiers du projet :
    app.py          l'interface (ce fichier)
    data.py         récupération des cours
    indicateurs.py  moyennes mobiles et RSI
    comparaison.py  courbes de base 100
    actualites.py   mise en forme des actualités
    portefeuille.py calculs de valeur et de gain
    database.py     base SQLite (liste de suivi, alertes, historique)
    verificateur.py vérification des alertes
    notifications.py envoi des messages Telegram
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import actualites
import comparaison
import database as db
import indicateurs as ind
import portefeuille
from data import actualites_brutes, devise
from data import recuperer_cours as _recuperer_cours
from notifications import telegram_configure
from verificateur import condition_remplie, decrire, libelle_condition, mesurer, verifier_alertes

# ---------------------------------------------------------------
# Réglages de la page
# ---------------------------------------------------------------
st.set_page_config(page_title="Tableau de bord financier", layout="wide")

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
PERIODES_COMPARAISON = {k: v for k, v in PERIODES.items() if k != "1J"}

# Indices de référence proposés dans la vue Comparaison (symboles Yahoo Finance)
INDICES = {"^FCHI": "CAC 40", "^GSPC": "S&P 500"}

# Couleurs des courbes d'indicateurs
COULEUR_MA50 = "#F59E0B"
COULEUR_MA200 = "#A78BFA"
COULEUR_RSI = "#2DD4BF"


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


@st.cache_data(ttl=300)
def resume_du_jour(ticker):
    """Renvoie (dernier cours, variation en % par rapport à la veille), ou None."""
    cours = recuperer_cours(ticker, "5d", "1d")
    if len(cours) < 2:
        return None
    dernier = cours["Close"].iloc[-1]
    precedent = cours["Close"].iloc[-2]
    return dernier, (dernier - precedent) / precedent * 100


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
# Colonne de gauche : la liste de suivi
# ---------------------------------------------------------------
liste_suivi = db.lister_watchlist()

with st.sidebar:
    vue = st.radio("Vue", ["Une action", "Comparaison", "Portefeuille"], horizontal=True)
    st.header("Ma liste de suivi")

    nouveau = st.text_input("Ajouter une action (ticker)", placeholder="ex. NVDA ou AIR.PA")
    if st.button("Ajouter"):
        ticker_saisi = nouveau.strip().upper()
        if not ticker_saisi:
            st.warning("Saisis un ticker.")
        elif ticker_saisi in liste_suivi:
            st.info(f"{ticker_saisi} est déjà dans la liste.")
        elif recuperer_cours(ticker_saisi, "5d", "1d").empty:
            st.error(f"Aucune donnée trouvée pour {ticker_saisi}. Vérifie le ticker.")
        else:
            db.ajouter_ticker(ticker_saisi)
            st.rerun()


    def libelle(ticker):
        """Texte affiché dans la liste : ticker, dernier cours et variation."""
        resume = resume_du_jour(ticker)
        if resume is None:
            return ticker
        dernier, variation = resume
        fleche = "▲" if variation >= 0 else "▼"
        return f"{ticker}   {dernier:.2f} {devise(ticker)}   {fleche} {variation:+.2f} %"


    if liste_suivi:
        choix = st.radio("Action affichée", liste_suivi, format_func=libelle)
        if st.button(f"Retirer {choix}"):
            db.retirer_ticker(choix)   # supprime aussi ses alertes actives
            st.rerun()
    else:
        choix = None


# ---------------------------------------------------------------
# Zone principale : en-tête
# ---------------------------------------------------------------
st.title("Tableau de bord financier")
st.caption("Cours différés d'environ 15 minutes · source : yfinance")
afficher_messages()

# ---------------------------------------------------------------
# Vue Portefeuille : mes achats, leur valeur et mon gain
# ---------------------------------------------------------------
if vue == "Portefeuille":
    st.subheader("Mon portefeuille")

    if liste_suivi:
        c_t, c_q, c_p, c_b = st.columns([2, 2, 2, 2])
        ticker_achat = c_t.selectbox("Action", liste_suivi)
        resume_achat = resume_du_jour(ticker_achat)
        quantite_achat = c_q.number_input("Quantité", min_value=0.0001, value=1.0, step=1.0, format="%.4f")
        prix_achat = c_p.number_input(
            f"Prix d'achat ({devise(ticker_achat)})",
            min_value=0.01,
            value=round(float(resume_achat[0]), 2) if resume_achat else 1.0,
            step=1.0,
            format="%.2f",
        )
        c_b.write("")   # petit espace pour aligner le bouton avec les champs
        if c_b.button("Ajouter l'achat"):
            db.ajouter_position(ticker_achat, float(quantite_achat), float(prix_achat))
            ajouter_message("success", f"Achat de {quantite_achat:g} {ticker_achat} enregistré.")
            st.rerun()
    else:
        st.info("Ajoute d'abord une action à ta liste de suivi pour pouvoir l'acheter ici.")

    lots = db.lister_positions()
    if not lots:
        st.info("Ton portefeuille est vide : enregistre un achat ci-dessus.")
        st.stop()

    # Dernier cours de chaque action détenue
    cours_actuels = {}
    for t in {lot["ticker"] for lot in lots}:
        resume_t = resume_du_jour(t)
        cours_actuels[t] = float(resume_t[0]) if resume_t else None

    lignes = portefeuille.synthese(lots, cours_actuels)
    totaux = portefeuille.totaux_par_devise(lignes)

    # Les totaux, une ligne par devise
    for symbole_dev, t in totaux.items():
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Valeur actuelle ({symbole_dev})", f"{t['valeur']:,.2f}".replace(",", " "))
        m2.metric(f"Investi ({symbole_dev})", f"{t['investi']:,.2f}".replace(",", " "))
        m3.metric(f"Gain ou perte ({symbole_dev})", f"{t['gain']:+,.2f}".replace(",", " "), f"{t['gain_pct']:+.2f} %")

    st.dataframe(
        [
            {
                "Action": l["ticker"],
                "Quantité": f"{l['quantite']:g}",
                "Prix d'achat moyen": f"{l['pru']:.2f} {l['devise']}",
                "Cours actuel": f"{l['cours']:.2f} {l['devise']}" if l["cours"] is not None else "indisponible",
                "Valeur": f"{l['valeur']:.2f} {l['devise']}" if l["valeur"] is not None else "-",
                "Gain ou perte": (
                    f"{l['gain']:+.2f} {l['devise']} ({l['gain_pct']:+.1f} %)" if l["gain"] is not None else "-"
                ),
            }
            for l in lignes
        ],
        hide_index=True,
        use_container_width=True,
    )

    # Répartition : un graphique par devise (on ne mélange pas € et $)
    if totaux:
        colonnes_pie = st.columns(len(totaux))
        for colonne, symbole_dev in zip(colonnes_pie, totaux):
            parts = [l for l in lignes if l["devise"] == symbole_dev and l["valeur"] is not None]
            fig_pie = go.Figure(
                go.Pie(labels=[l["ticker"] for l in parts], values=[l["valeur"] for l in parts], hole=0.45)
            )
            fig_pie.update_layout(title=f"Répartition ({symbole_dev})", template="plotly_dark", height=380)
            colonne.plotly_chart(fig_pie, use_container_width=True)

    with st.expander("Détail des achats"):
        for lot in lots:
            c_texte, c_bouton = st.columns([6, 1])
            c_texte.write(
                f"**{lot['ticker']}** · {lot['quantite']:g} à {lot['prix_achat']:.2f} {devise(lot['ticker'])} "
                f"· {lot['date_achat'][:10]}"
            )
            if c_bouton.button("✕", key=f"suppr_lot_{lot['id']}", help="Supprimer cet achat"):
                db.supprimer_position(lot["id"])
                st.rerun()

    st.caption(
        "Valeurs au dernier cours connu (différé), sans frais ni conversion euro/dollar : "
        "chaque devise est totalisée séparément. Aide à la décision, pas un conseil financier."
    )
    st.stop()

# ---------------------------------------------------------------
# Vue Comparaison : plusieurs actions et indices en base 100
# ---------------------------------------------------------------
if vue == "Comparaison":
    def nom_affiche(symbole_yahoo):
        return INDICES.get(symbole_yahoo, symbole_yahoo)

    st.subheader("Comparaison de performance")
    selection = st.multiselect(
        "Actions et indices à comparer",
        liste_suivi + list(INDICES),
        default=liste_suivi[:2] + ["^GSPC"],
        format_func=nom_affiche,
    )
    periode_comp = st.radio("Période", list(PERIODES_COMPARAISON), index=1, horizontal=True, key="periode_comp")

    if len(selection) < 2:
        st.info("Choisis au moins deux actions ou indices à comparer.")
        st.stop()

    periode_c, intervalle_c = PERIODES_COMPARAISON[periode_comp]
    clotures = {}
    indisponibles = []
    for symbole_yahoo in selection:
        donnees = recuperer_cours(symbole_yahoo, periode_c, intervalle_c)
        if donnees.empty:
            indisponibles.append(symbole_yahoo)
        else:
            clotures[nom_affiche(symbole_yahoo)] = donnees["Close"]
    if indisponibles:
        st.warning("Données indisponibles pour : " + ", ".join(indisponibles))

    courbes = comparaison.base_100(clotures)
    if courbes.empty or len(courbes.columns) < 2:
        st.warning("Pas assez de données communes pour comparer. Réessaie dans une minute.")
        st.stop()

    fig_comp = go.Figure()
    for nom in courbes.columns:
        fig_comp.add_trace(go.Scatter(x=courbes.index, y=courbes[nom], mode="lines", name=nom))
    fig_comp.add_hline(y=100, line_dash="dot", line_color="#9FB0CC")
    fig_comp.update_layout(
        title=f"Performance comparée (base 100) · {periode_comp}",
        yaxis_title="Base 100 au départ",
        template="plotly_dark",
        height=520,
    )
    st.plotly_chart(fig_comp, use_container_width=True)

    # Classement, de la meilleure à la moins bonne performance
    performances = (courbes.iloc[-1] - 100).sort_values(ascending=False)
    st.dataframe(
        [{"Valeur": nom, "Performance": f"{perf:+.1f} %"} for nom, perf in performances.items()],
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        f"Départ commun : {courbes.index[0]:%d/%m/%Y}. Les performances sont calculées sur les cours, "
        "dans la devise de chaque valeur, sans dividendes. Aide à la décision, pas un conseil financier."
    )
    st.stop()

if choix is None:
    st.info("Ta liste de suivi est vide : ajoute une action dans la colonne de gauche.")
    st.stop()

col_periode, col_type = st.columns(2)
with col_periode:
    periode_choisie = st.radio("Période", list(PERIODES), index=1, horizontal=True)
with col_type:
    type_graphique = st.radio("Type de graphique", ["Courbe", "Chandeliers"], horizontal=True)

# Les indicateurs sont calculés sur des clôtures journalières : pas disponibles pour 1J
indicateurs_disponibles = periode_choisie != "1J"
col_ma50, col_ma200, col_rsi = st.columns(3)
with col_ma50:
    veut_ma50 = st.checkbox("Moyenne mobile 50 jours", disabled=not indicateurs_disponibles)
with col_ma200:
    veut_ma200 = st.checkbox("Moyenne mobile 200 jours", disabled=not indicateurs_disponibles)
with col_rsi:
    veut_rsi = st.checkbox("RSI (14 jours)", disabled=not indicateurs_disponibles)
if not indicateurs_disponibles:
    st.caption("Les indicateurs utilisent des clôtures journalières : choisis une période de 1M ou plus.")

# Une case grisée peut rester cochée : on ne tient compte que des cases actives
afficher_ma50 = veut_ma50 and indicateurs_disponibles
afficher_ma200 = veut_ma200 and indicateurs_disponibles
afficher_rsi = veut_rsi and indicateurs_disponibles

periode, intervalle = PERIODES[periode_choisie]
cours = recuperer_cours(choix, periode, intervalle)

if cours.empty:
    st.warning("Impossible de récupérer les cours pour le moment. Réessaie dans une minute.")
    st.stop()

# Les quatre chiffres clés au-dessus du graphique
symbole = devise(choix)
dernier = cours["Close"].iloc[-1]
premier = cours["Close"].iloc[0]
variation_periode = (dernier - premier) / premier * 100

c1, c2, c3, c4 = st.columns(4)
c1.metric("Dernier cours", f"{dernier:.2f} {symbole}", f"{variation_periode:+.2f} % sur la période")
c2.metric("Plus haut", f"{cours['High'].max():.2f} {symbole}")
c3.metric("Plus bas", f"{cours['Low'].min():.2f} {symbole}")
c4.metric("Volume cumulé", f"{cours['Volume'].sum() / 1e6:.1f} M")

# ---------------------------------------------------------------
# Calcul des indicateurs
# ---------------------------------------------------------------
# Une moyenne sur 200 jours a besoin de 200 jours d'historique AVANT la première date
# affichée. On calcule donc les indicateurs sur 5 ans de clôtures journalières, puis on
# ne garde que la partie visible sur le graphique.
serie_ma50 = serie_ma200 = serie_rsi = None
if afficher_ma50 or afficher_ma200 or afficher_rsi:
    historique = recuperer_cours(choix, "5y", "1d")["Close"].dropna()
    if historique.empty:
        st.warning("Historique indisponible : les indicateurs ne peuvent pas être calculés.")
        afficher_ma50 = afficher_ma200 = afficher_rsi = False
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

# ---------------------------------------------------------------
# Le graphique
# ---------------------------------------------------------------
avec_rsi = serie_rsi is not None and not serie_rsi.empty

if avec_rsi:
    # Deux zones superposées : le cours en haut, le RSI en bas
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.72, 0.28])
else:
    fig = make_subplots(rows=1, cols=1)

if type_graphique == "Courbe":
    fig.add_trace(go.Scatter(x=cours.index, y=cours["Close"], mode="lines", name="Cours"), row=1, col=1)
else:
    fig.add_trace(
        go.Candlestick(
            x=cours.index,
            open=cours["Open"],
            high=cours["High"],
            low=cours["Low"],
            close=cours["Close"],
            name="Cours",
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

if avec_rsi:
    fig.add_trace(
        go.Scatter(x=serie_rsi.index, y=serie_rsi, mode="lines", name="RSI", line=dict(color=COULEUR_RSI, width=1.6)),
        row=2,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="#9FB0CC", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#9FB0CC", row=2, col=1)
    fig.update_yaxes(range=[0, 100], title_text="RSI", row=2, col=1)

# Une ligne pointillée jaune pour chaque alerte de prix active sur cette action
for alerte in db.lister_alertes(choix):
    if alerte["type"] == "prix":
        signe = "≥" if alerte["sens"] == "hausse" else "≤"
        fig.add_hline(
            y=alerte["seuil"],
            line_dash="dash",
            line_color="#FBBF24",
            annotation_text=f"Alerte {signe} {alerte['seuil']:.2f}",
            annotation_position="top left",
            row=1,
            col=1,
        )

fig.update_layout(
    title=f"{choix} · {periode_choisie}",
    xaxis_title="Date" if not avec_rsi else None,
    yaxis_title=f"Prix ({symbole})",
    template="plotly_dark",
    xaxis_rangeslider_visible=False,
    height=700 if avec_rsi else 520,
)
st.plotly_chart(fig, use_container_width=True)

if avec_rsi:
    rsi_actuel = serie_rsi.iloc[-1]
    st.caption(f"RSI actuel : {rsi_actuel:.0f} · {ind.interpreter_rsi(rsi_actuel)}.")
if afficher_ma200 and (serie_ma200 is None or serie_ma200.empty):
    st.caption("MA200 indisponible : cette action n'a pas encore 200 jours d'historique.")

# ---------------------------------------------------------------
# Les actualités
# ---------------------------------------------------------------
st.divider()
st.subheader(f"Actualités · {choix}")
articles = liste_actualites(choix)
if not articles:
    st.caption("Aucune actualité disponible pour le moment (la source peut être indisponible).")
for article in articles:
    st.markdown(f"**{actualites.lien_markdown(article['titre'], article['lien'])}**")
    ligne = " · ".join(x for x in (article["source"], actualites.depuis(article["date"])) if x)
    if ligne:
        st.caption(ligne)
if articles:
    st.caption("Articles en général rédigés en anglais, fournis par Yahoo Finance : cliquer sur un titre ouvre l'article d'origine.")

# ---------------------------------------------------------------
# Les alertes
# ---------------------------------------------------------------
st.divider()
col_form, col_actives = st.columns(2)

with col_form:
    st.subheader(f"Nouvelle alerte sur {choix}")

    type_choisi = st.radio(
        "Type d'alerte", ["Prix", "Variation du jour (%)", "RSI", "Croisement MA50/MA200"], horizontal=True
    )

    if type_choisi == "RSI":
        type_alerte = "rsi"
        sens_choisi = st.radio("Prévenez-moi quand l'action est", ["en surchauffe (RSI au-dessus de)", "en survente (RSI en dessous de)"])
        sens = "hausse" if sens_choisi.startswith("en surchauffe") else "baisse"
        seuil = st.number_input(
            "Seuil du RSI", min_value=1.0, max_value=99.0, value=70.0 if sens == "hausse" else 30.0, step=1.0, format="%.0f"
        )
    elif type_choisi == "Croisement MA50/MA200":
        type_alerte = "croisement_ma"
        sens_choisi = st.radio("Prévenez-moi quand", ["la MA50 passe au-dessus de la MA200", "la MA50 passe sous la MA200"])
        sens = "hausse" if "au-dessus" in sens_choisi else "baisse"
        seuil = 0.0
        st.caption("Alerte envoyée si le croisement a eu lieu pendant les 5 dernières séances.")
    elif type_choisi == "Prix":
        type_alerte = "prix"
        sens_choisi = st.radio("Prévenez-moi quand le cours est", ["au-dessus de", "en dessous de"], horizontal=True)
        sens = "hausse" if sens_choisi == "au-dessus de" else "baisse"
        seuil = st.number_input(
            f"Seuil ({symbole})", min_value=0.01, value=round(float(dernier), 2), step=1.0, format="%.2f"
        )
    else:
        type_alerte = "variation_jour"
        sens_choisi = st.radio("Prévenez-moi quand l'action", ["monte d'au moins", "baisse d'au moins"], horizontal=True)
        sens = "hausse" if sens_choisi == "monte d'au moins" else "baisse"
        seuil = st.number_input("Variation sur la journée (%)", min_value=0.1, value=5.0, step=0.5, format="%.1f")

    if st.button("Créer l'alerte"):
        db.creer_alerte(choix, sens, float(seuil), type_alerte)
        ajouter_message("success", f"Alerte créée sur {choix}.")

        # On prévient si la condition est déjà vraie : l'alerte partira à la prochaine vérification
        if type_alerte == "prix":
            deja_franchi = (dernier >= seuil) if sens == "hausse" else (dernier <= seuil)
        elif type_alerte in ("rsi", "croisement_ma"):
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
                "Cette condition est déjà remplie actuellement : l'alerte se déclenchera "
                "à la prochaine vérification.",
            )
        st.rerun()

with col_actives:
    st.subheader("Alertes actives")
    alertes = db.lister_alertes()
    if not alertes:
        st.caption("Aucune alerte pour le moment.")
    for alerte in alertes:
        c_texte, c_bouton = st.columns([5, 1])
        c_texte.write(f"**{alerte['ticker']}**  {libelle_condition(alerte)}")
        if c_bouton.button("✕", key=f"suppr_{alerte['id']}", help="Supprimer cette alerte"):
            db.supprimer_alerte(alerte["id"])
            st.rerun()

    if alertes and st.button("Vérifier les alertes maintenant"):
        declenchees, echecs = verifier_alertes()
        for alerte, mesure, information in declenchees:
            ajouter_message("warning", f"Alerte déclenchée · {decrire(alerte, mesure)} ({information})")
        for alerte, mesure, explication in echecs:
            ajouter_message(
                "error",
                f"Seuil franchi · {decrire(alerte, mesure)}, mais le message Telegram n'est pas parti : "
                f"{explication} L'alerte reste active.",
            )
        if not declenchees and not echecs:
            ajouter_message("success", "Vérification faite : aucun seuil n'est franchi.")
        st.rerun()

    if telegram_configure():
        st.caption("Notifications Telegram : activées.")
    else:
        st.caption("Notifications Telegram : non configurées (fichier .env à créer).")

# ---------------------------------------------------------------
# Historique
# ---------------------------------------------------------------
st.subheader("Alertes déclenchées")
historique_alertes = db.lister_historique()
if historique_alertes:
    st.dataframe(
        [
            {
                "Date": h["date_declenchement"],
                "Action": h["ticker"],
                "Condition": libelle_condition(h),
                "Cours au déclenchement": f"{h['cours']:.2f} {devise(h['ticker'])}"
                + (f" ({h['variation']:+.2f} %)" if h["variation"] is not None else ""),
            }
            for h in historique_alertes
        ],
        hide_index=True,
        use_container_width=True,
    )
else:
    st.caption("Aucune alerte déclenchée pour le moment.")

st.caption("Outil d'aide à la décision, ne constitue pas un conseil financier.")
