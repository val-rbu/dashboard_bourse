"""Étape 3 : tableau de bord financier avec liste de suivi sauvegardée et alertes à seuil.

Pour lancer l'application, dans le terminal :
    streamlit run app.py

Fichiers du projet :
    app.py          l'interface (ce fichier)
    data.py         récupération des cours
    database.py     base SQLite (liste de suivi, alertes, historique)
    verificateur.py vérification des alertes
"""

import streamlit as st
import plotly.graph_objects as go

import database as db
from data import devise
from data import recuperer_cours as _recuperer_cours
from notifications import telegram_configure
from verificateur import verifier_alertes, decrire

# ---------------------------------------------------------------
# Réglages de la page
# ---------------------------------------------------------------
st.set_page_config(page_title="Tableau de bord financier", layout="wide")

# Crée la base de données au premier lancement (ne fait rien si elle existe déjà)
db.initialiser()

# Pour chaque bouton de période : (durée à récupérer, intervalle entre deux points)
PERIODES = {
    "1J": ("1d", "5m"),
    "1M": ("1mo", "1d"),
    "1A": ("1y", "1d"),
    "5A": ("5y", "1wk"),
}


# ---------------------------------------------------------------
# Données (avec une mémoire de 5 minutes pour limiter les demandes)
# ---------------------------------------------------------------
@st.cache_data(ttl=300)
def recuperer_cours(ticker, periode, intervalle):
    return _recuperer_cours(ticker, periode, intervalle)


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

if choix is None:
    st.info("Ta liste de suivi est vide : ajoute une action dans la colonne de gauche.")
    st.stop()

col_periode, col_type = st.columns(2)
with col_periode:
    periode_choisie = st.radio("Période", list(PERIODES), index=1, horizontal=True)
with col_type:
    type_graphique = st.radio("Type de graphique", ["Courbe", "Chandeliers"], horizontal=True)

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
# Le graphique
# ---------------------------------------------------------------
fig = go.Figure()
if type_graphique == "Courbe":
    fig.add_trace(go.Scatter(x=cours.index, y=cours["Close"], mode="lines", name="Cours"))
else:
    fig.add_trace(
        go.Candlestick(
            x=cours.index,
            open=cours["Open"],
            high=cours["High"],
            low=cours["Low"],
            close=cours["Close"],
            name="Cours",
        )
    )

# Une ligne pointillée jaune pour chaque alerte active sur cette action
for alerte in db.lister_alertes(choix):
    signe = "≥" if alerte["sens"] == "hausse" else "≤"
    fig.add_hline(
        y=alerte["seuil"],
        line_dash="dash",
        line_color="#FBBF24",
        annotation_text=f"Alerte {signe} {alerte['seuil']:.2f}",
        annotation_position="top left",
    )

fig.update_layout(
    title=f"{choix} · {periode_choisie}",
    xaxis_title="Date",
    yaxis_title=f"Prix ({symbole})",
    template="plotly_dark",
    xaxis_rangeslider_visible=False,
    height=520,
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------
# Les alertes
# ---------------------------------------------------------------
st.divider()
col_form, col_actives = st.columns(2)

with col_form:
    st.subheader(f"Nouvelle alerte sur {choix}")
    with st.form("formulaire_alerte"):
        sens_choisi = st.radio(
            "Prévenez-moi quand le cours est", ["au-dessus de", "en dessous de"], horizontal=True
        )
        seuil = st.number_input(
            f"Seuil ({symbole})", min_value=0.01, value=round(float(dernier), 2), step=1.0, format="%.2f"
        )
        valide = st.form_submit_button("Créer l'alerte")

    if valide:
        sens = "hausse" if sens_choisi == "au-dessus de" else "baisse"
        db.creer_alerte(choix, sens, float(seuil))
        ajouter_message("success", f"Alerte créée sur {choix}.")
        deja_franchi = (dernier >= seuil) if sens == "hausse" else (dernier <= seuil)
        if deja_franchi:
            ajouter_message(
                "info",
                "Ce seuil est déjà franchi par le cours actuel : l'alerte se déclenchera "
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
        signe = "≥" if alerte["sens"] == "hausse" else "≤"
        c_texte.write(f"**{alerte['ticker']}**  {signe}  {alerte['seuil']:.2f} {devise(alerte['ticker'])}")
        if c_bouton.button("✕", key=f"suppr_{alerte['id']}", help="Supprimer cette alerte"):
            db.supprimer_alerte(alerte["id"])
            st.rerun()

    if alertes and st.button("Vérifier les alertes maintenant"):
        declenchees, echecs = verifier_alertes()
        for alerte, cours_actuel, information in declenchees:
            ajouter_message("warning", f"Alerte déclenchée · {decrire(alerte, cours_actuel)} ({information})")
        for alerte, cours_actuel, explication in echecs:
            ajouter_message(
                "error",
                f"Seuil franchi · {decrire(alerte, cours_actuel)}, mais le message Telegram n'est pas parti : "
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
historique = db.lister_historique()
if historique:
    st.dataframe(
        [
            {
                "Date": h["date_declenchement"],
                "Action": h["ticker"],
                "Condition": f"{'≥' if h['sens'] == 'hausse' else '≤'} {h['seuil']:.2f} {devise(h['ticker'])}",
                "Cours au déclenchement": f"{h['cours']:.2f} {devise(h['ticker'])}",
            }
            for h in historique
        ],
        hide_index=True,
        use_container_width=True,
    )
else:
    st.caption("Aucune alerte déclenchée pour le moment.")

st.caption("Outil d'aide à la décision, ne constitue pas un conseil financier.")
