"""Apparence de l'application (d'après la maquette « refonte moderne ») : couleurs, polices, cartes,
barre de navigation et thème des graphiques.

Rien ici ne calcule de données : ce fichier ne sert qu'à l'habillage.
Les sélecteurs CSS visent le code de Streamlit 1.66 : une future version de Streamlit peut en casser une partie.
"""

import streamlit as st

# Deux palettes : sombre (celle de la maquette) et claire.
# appliquer(mode) recopie la palette choisie dans les variables ci-dessous (FOND, CARTE, TURQUOISE...),
# que app.py utilise aussi pour colorer les graphiques.
PALETTES = {
    "sombre": {
        "FOND": "#090D14", "NAV": "#0D121C", "CARTE": "#111723", "TUILE": "#161E2D", "CARTE_SURLIGNEE": "#15302D",
        "BORDURE": "#1F2A3C", "BORDURE_CHAMP": "#2A374D", "TEXTE": "#EEF2F8", "TEXTE_DISCRET": "#8A97AD",
        "TURQUOISE": "#3BE0C3", "VERT": "#3DDC97", "ROUGE": "#FF7A7A", "JAUNE": "#F5B544", "VIOLET": "#A78BFA",
        "BLEU": "#60A5FA", "TEXTE_BOUTON": "#062019", "FOND_HAUSSE": "#12302A", "FOND_BAISSE": "#2A1519",
        "TEXTE_NEUTRE": "#C3CCDA",
    },
    "clair": {
        "FOND": "#F3F6FA", "NAV": "#FFFFFF", "CARTE": "#FFFFFF", "TUILE": "#EDF1F7", "CARTE_SURLIGNEE": "#E2F6F2",
        "BORDURE": "#E3E8EF", "BORDURE_CHAMP": "#CBD5E1", "TEXTE": "#0F172A", "TEXTE_DISCRET": "#5B6B82",
        "TURQUOISE": "#0D9488", "VERT": "#047857", "ROUGE": "#DC2626", "JAUNE": "#B45309", "VIOLET": "#7C3AED",
        "BLEU": "#2563EB", "TEXTE_BOUTON": "#FFFFFF", "FOND_HAUSSE": "#DCFCE7", "FOND_BAISSE": "#FEE2E2",
        "TEXTE_NEUTRE": "#475569",
    },
}

# Thème Streamlit correspondant (couleurs des boutons, champs, tableaux...)
THEMES_STREAMLIT = {
    "sombre": {"base": "dark", "primaryColor": "#3BE0C3", "backgroundColor": "#090D14",
               "secondaryBackgroundColor": "#161E2D", "textColor": "#EEF2F8"},
    "clair": {"base": "light", "primaryColor": "#0D9488", "backgroundColor": "#F3F6FA",
              "secondaryBackgroundColor": "#E9EEF5", "textColor": "#0F172A"},
}

MODE = "sombre"
FOND = NAV = CARTE = TUILE = CARTE_SURLIGNEE = BORDURE = BORDURE_CHAMP = TEXTE = TEXTE_DISCRET = ""
TURQUOISE = VERT = ROUGE = JAUNE = VIOLET = BLEU = TEXTE_BOUTON = FOND_HAUSSE = FOND_BAISSE = TEXTE_NEUTRE = ""


def _choisir_palette(mode):
    global MODE
    MODE = mode if mode in PALETTES else "sombre"
    globals().update(PALETTES[MODE])


_choisir_palette("sombre")


def rgba(couleur_hex, opacite):
    """« #3BE0C3 » + 0.3 -> « rgba(59,224,195,0.3) » (pour les dégradés des graphiques)."""
    h = couleur_hex.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{opacite})"


def _css():
    """Feuille de style, construite avec les couleurs de la palette choisie."""
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

/* ---------- Base ---------- */
html, body, .stApp, .stApp p, .stApp button, .stApp input, .stApp label, .stApp li {{ font-family: Inter, system-ui, sans-serif; }}
[data-testid="stIconMaterial"], .material-symbols-rounded, [class*="material-symbols"] {{ font-family: "Material Symbols Rounded" !important; }}
.stApp {{ background: {FOND}; color: {TEXTE}; }}
.stApp a {{ color: {TURQUOISE}; text-decoration: none; }}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stAppDeployButton"] {{ display: none; }}
.block-container {{ padding: 2.6rem 1.75rem 2rem 1.75rem !important; max-width: none !important; }}
.tb-num {{ font-family: "Space Grotesk", Inter, sans-serif; }}
.tb-discret {{ font-size: 12px; color: {TEXTE_DISCRET}; }}
.tb-hausse {{ color: {VERT}; font-weight: 600; }}
.tb-baisse {{ color: {ROUGE}; font-weight: 600; }}
[data-testid="stHeadingActionElements"] {{ display: none; }}
/* Streamlit remonte chaque bloc de texte de 16 px (marge négative) : nos cartes HTML débordaient
   alors sur la ligne du dessous. On annule cette marge pour tous nos blocs (classes « tb-... »). */
[data-testid="stMarkdownContainer"]:has(> [class^="tb-"]) {{ margin-bottom: 0 !important; }}
/* Pas d'effet « grisé » sur la page pendant qu'elle se met à jour */
[data-stale="true"] {{ opacity: 1 !important; transition: none !important; }}
.stApp h1, .stApp h2, .stApp h3 {{ font-family: "Space Grotesk", Inter, sans-serif; letter-spacing: -0.01em; }}
[data-testid="stMarkdownContainer"] h3 {{ font-size: 20px !important; }}

/* ---------- Barre de navigation (la barre latérale de Streamlit devient une colonne d'icônes) ---------- */
[data-testid="stSidebar"] {{ background: {NAV}; border-right: 1px solid {BORDURE}; }}
[data-testid="stSidebar"][data-collapsed="false"] {{ width: 84px !important; min-width: 84px !important; max-width: 84px !important; }}
[data-testid="stSidebarHeader"], [data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
[data-testid="stSidebarContent"] {{ padding: 0 !important; overflow: visible !important; }}
[data-testid="stSidebarUserContent"] {{ padding: 20px 0 !important; width: 100% !important; }}
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {{ align-items: center; gap: 8px; }}
.tb-logo {{ width: 40px; height: 40px; border-radius: 12px; background: {TURQUOISE}; color: {TEXTE_BOUTON};
  display: flex; align-items: center; justify-content: center; font-family: "Space Grotesk"; font-weight: 700; font-size: 18px; margin: 0 auto 18px; }}
[class*="st-key-nav_"] button {{ width: 48px !important; height: 48px; min-height: 48px; padding: 0; border-radius: 14px;
  border: 0 !important; background: transparent; color: {TEXTE_DISCRET}; }}
/* Le nom de l'onglet : une bulle à droite de l'icône, visible au survol (hors du flux, donc l'icône reste centrée) */
[class*="st-key-nav_"] button {{ position: relative; overflow: visible; }}
[class*="st-key-nav_"] button [data-testid="stMarkdownContainer"] {{ position: absolute; left: calc(100% + 12px); top: 50%;
  transform: translateY(-50%); opacity: 0; pointer-events: none; transition: opacity .12s; z-index: 1000;
  background: {TEXTE}; border-radius: 8px; padding: 5px 10px; white-space: nowrap; width: max-content; max-width: none; }}
[class*="st-key-nav_"] button [data-testid="stMarkdownContainer"] p {{ margin: 0; color: {FOND}; font-size: 12px; font-weight: 600;
  overflow: visible; text-overflow: clip; max-width: none; white-space: nowrap; }}
[class*="st-key-nav_"] button:hover [data-testid="stMarkdownContainer"] {{ opacity: 1; }}
[data-testid="stSidebar"] {{ z-index: 999991; }}
[class*="st-key-nav_"] button [data-testid="stIconMaterial"] {{ font-size: 24px; margin: 0; }}
[class*="st-key-nav_"] button:hover {{ background: {TUILE}; color: {TEXTE}; }}
[class*="st-key-nav_"] button[kind="primary"], [class*="st-key-nav_"] [data-testid="stBaseButton-primary"] {{ background: {CARTE_SURLIGNEE} !important; color: {TURQUOISE} !important; }}

/* ---------- Barre du haut ---------- */
.tb-salut h1 {{ margin: 0 !important; padding: 0 !important; font-size: 26px !important; font-weight: 700 !important; color: {TEXTE}; }}
.tb-salut div {{ color: {TEXTE_DISCRET}; font-size: 13px; margin-top: 2px; }}
.st-key-barre_haut [data-baseweb="input"], .st-key-barre_haut [data-baseweb="select"] > div {{
  background: {CARTE} !important; border: 1px solid {BORDURE} !important; border-radius: 12px !important; min-height: 44px; }}
.st-key-barre_haut input {{ background: transparent !important; }}
.st-key-bouton_theme button {{ width: 44px; height: 44px; min-height: 44px; padding: 0; border-radius: 12px;
  background: {CARTE}; border: 1px solid {BORDURE}; color: {JAUNE}; }}
.st-key-bouton_theme button [data-testid="stMarkdownContainer"] {{ display: none; }}
.st-key-bouton_theme [data-testid="stIconMaterial"] {{ font-size: 22px; margin: 0; }}
[data-testid="stButtonGroup"] button {{ border-radius: 9px; }}

/* ---------- Liste de suivi : une rangée de cartes cliquables ---------- */
[class*="st-key-carte_"] {{ position: relative; }}
/* Bouton invisible « Choisir » : posé sur toute la carte, un clic n'importe où choisit l'action */
[class*="st-key-carte_"] [data-testid="stElementContainer"]:is([class*="st-key-choisir_"], :has([class*="st-key-choisir_"])) {{
  position: absolute; inset: 0; z-index: 2; margin: 0; width: 100% !important; height: 100% !important; }}
[class*="st-key-choisir_"] .stButton, [class*="st-key-choisir_"] .stButton > div, .stButton[class*="st-key-choisir_"] {{ width: 100% !important; height: 100% !important; }}
[class*="st-key-choisir_"] button {{ width: 100% !important; height: 100% !important; min-height: 100%; opacity: 0; cursor: pointer; }}
/* Croix « Retirer » en bas à droite, au-dessus du bouton invisible, visible au survol de la carte */
[class*="st-key-carte_"] [data-testid="stElementContainer"]:is([class*="st-key-retrait_"], :has([class*="st-key-retrait_"])) {{
  position: absolute; right: 6px; bottom: 6px; z-index: 3; width: auto !important; margin: 0; }}
[class*="st-key-retrait_"] button {{ width: 26px; height: 26px; min-height: 26px; padding: 0; border-radius: 8px; border: 0 !important;
  background: transparent !important; color: {TEXTE_DISCRET}; font-size: 12px; opacity: 0; transition: opacity .12s; }}
[class*="st-key-retrait_"] button [data-testid="stIconMaterial"] {{ display: none; }}   /* pas de flèche de menu */
[class*="st-key-carte_"]:hover [class*="st-key-retrait_"] button, [class*="st-key-retrait_"] button[aria-expanded="true"] {{ opacity: 1; }}
[class*="st-key-retrait_"] button:hover {{ color: {ROUGE}; background: {FOND_BAISSE} !important; }}
@media (hover: none) {{ [class*="st-key-retrait_"] button {{ opacity: .7; }} }}   /* téléphone : pas de survol, croix toujours visible */
.tb-suivi {{ background: {CARTE}; border: 1px solid {BORDURE}; border-radius: 16px; padding: 12px 14px; display: flex; flex-direction: column; gap: 3px; min-height: 84px; box-sizing: border-box; }}
[class*="st-key-carte_"]:hover .tb-suivi {{ border-color: {BORDURE_CHAMP}; }}
.tb-suivi.tb-choisie {{ background: {CARTE_SURLIGNEE}; border-color: {TURQUOISE}; }}
.tb-suivi-haut {{ display: flex; justify-content: space-between; font-weight: 600; font-size: 13px; gap: 6px; }}
.tb-suivi-prix {{ font-family: "Space Grotesk"; font-size: 19px; font-weight: 600; white-space: nowrap; }}
.tb-suivi-nom {{ color: {TEXTE_DISCRET}; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.st-key-pop_ajout button {{ min-height: 84px; width: 100%; border: 1px dashed {BORDURE_CHAMP} !important; background: transparent !important;
  border-radius: 16px; color: {TEXTE_DISCRET}; }}
[data-testid="stPopoverBody"] {{ background: {CARTE}; border: 1px solid {BORDURE_CHAMP}; border-radius: 14px; min-width: 320px; }}

/* ---------- Cartes ---------- */
div[data-testid="stVerticalBlockBorderWrapper"] {{ background: {CARTE}; border: 1px solid {BORDURE} !important; border-radius: 20px; padding: 8px 10px; }}
div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlockBorderWrapper"] {{ background: {TUILE}; border-radius: 14px; padding: 2px 4px; }}
.tb-titre {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 6px; }}
.tb-titre h2 {{ margin: 0 !important; padding: 0 !important; font-size: 15px !important; font-weight: 600 !important; font-family: Inter, sans-serif !important; }}
[data-testid="stMetric"] {{ background: {TUILE}; border-radius: 14px; padding: 12px 14px; }}
[data-testid="stMetricLabel"] p {{ color: {TEXTE_DISCRET}; font-size: 12px; }}
[data-testid="stMetricValue"] {{ font-family: "Space Grotesk"; font-weight: 600; font-size: 1.35rem; }}

/* ---------- Grande carte du cours ---------- */
.tb-nom {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
.tb-nom h2 {{ margin: 0 !important; padding: 0 !important; font-size: 18px !important; font-weight: 600 !important; font-family: Inter, sans-serif !important; }}
.tb-puce {{ font-size: 12px; color: {TEXTE_DISCRET}; background: {TUILE}; border-radius: 6px; padding: 2px 8px; }}
.tb-ligne-prix {{ display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-top: 8px; }}
.tb-gros-prix {{ font-family: "Space Grotesk"; font-size: 40px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.1; }}
.tb-badge {{ font-weight: 600; border-radius: 8px; padding: 3px 8px; font-size: 13px; white-space: nowrap; }}
.tb-badge.hausse {{ color: {VERT}; background: {FOND_HAUSSE}; }}
.tb-badge.baisse {{ color: {ROUGE}; background: {FOND_BAISSE}; }}
.st-key-indicateurs button {{ border-radius: 999px !important; }}
.tb-stats {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
.tb-stat {{ background: {TUILE}; border-radius: 14px; padding: 12px 14px; }}
.tb-stat div:first-child {{ color: {TEXTE_DISCRET}; font-size: 12px; }}
.tb-stat div:last-child {{ font-family: "Space Grotesk"; font-size: 20px; font-weight: 600; margin-top: 4px; white-space: nowrap; }}

/* ---------- Signaux, alertes ---------- */
.tb-rsi {{ display: flex; align-items: center; gap: 16px; }}
.tb-rsi b {{ font-weight: 600; }}
.tb-ligne {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; background: {TUILE};
  border-radius: 12px; padding: 10px 12px; font-size: 13px; margin-top: 8px; }}
.tb-ligne > span:first-child {{ color: {TEXTE_DISCRET}; }}
.tb-ligne > span:last-child {{ font-weight: 600; text-align: right; }}
.tb-alerte {{ display: flex; align-items: center; gap: 10px; background: {TUILE}; border-radius: 12px; padding: 10px 12px; font-size: 13px; min-height: 40px; box-sizing: border-box; }}
.tb-alerte .tb-txt {{ flex: 1; }}
.tb-point {{ width: 8px; height: 8px; border-radius: 50%; flex: 0 0 8px; }}
[class*="st-key-suppr_"] button {{ min-height: 40px; color: {TEXTE_DISCRET}; }}
.st-key-pop_alerte button {{ min-height: 44px; border-radius: 12px; font-weight: 700; }}

/* ---------- Actualités ---------- */
.tb-actus {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
.tb-actu {{ display: flex; gap: 12px; background: {TUILE}; border-radius: 14px; padding: 12px 14px; color: {TEXTE} !important; }}
.tb-actu:hover {{ outline: 1px solid {BORDURE_CHAMP}; }}
.tb-actu .tb-txt {{ display: flex; flex-direction: column; gap: 4px; }}
.tb-actu .tb-txt span:first-child {{ font-size: 13px; font-weight: 500; line-height: 1.35; }}
.tb-actu .tb-txt span:last-child {{ font-size: 11px; color: {TEXTE_DISCRET}; }}
.tb-sent {{ flex: 0 0 auto; align-self: flex-start; font-size: 11px; font-weight: 600; border-radius: 6px; padding: 2px 8px; }}
.tb-sent.positif {{ background: {FOND_HAUSSE}; color: {VERT}; }}
.tb-sent.negatif {{ background: {FOND_BAISSE}; color: {ROUGE}; }}
.tb-sent.neutre {{ background: {BORDURE}; color: {TEXTE_NEUTRE}; }}

/* ---------- Portefeuille (carte du tableau de bord) ---------- */
.tb-pf {{ display: flex; align-items: center; gap: 18px; }}
.tb-pf-total {{ font-family: "Space Grotesk"; font-size: 26px; font-weight: 700; }}
.tb-pf-ligne {{ display: flex; justify-content: space-between; font-size: 13px; margin-top: 6px; }}

/* ---------- Divers ---------- */
.stButton > button {{ border-radius: 12px; }}
[data-baseweb="input"], [data-baseweb="select"] > div {{ border-radius: 12px; }}
[data-testid="stExpander"] details {{ border-radius: 14px; }}
.tb-pied {{ color: {TEXTE_DISCRET}; font-size: 12px; margin-top: 8px; }}
@media (max-width: 900px) {{
  .tb-actus {{ grid-template-columns: minmax(0, 1fr); }}
  .tb-stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}
</style>
"""


def appliquer(mode="sombre"):
    """Choisit la palette ("sombre" ou "clair") et injecte le style dans la page (en haut de app.py)."""
    _choisir_palette(mode)
    st.markdown(_css(), unsafe_allow_html=True)


def carte_suivi(ticker, prix, variation, texte_variation, nom, choisie):
    """Carte d'une action de la liste de suivi (HTML) : ticker et variation du jour, prix, nom de la société.

    prix et texte_variation sont déjà mis en forme ; variation (nombre) choisit la couleur. prix None : indisponible.
    """
    if prix is None:
        variation_html = '<span class="tb-discret">n.d.</span>'
        prix = "—"
    else:
        classe = "tb-hausse" if variation >= 0 else "tb-baisse"
        variation_html = f'<span class="{classe}">{texte_variation}</span>'
    return (
        f'<div class="tb-suivi{" tb-choisie" if choisie else ""}">'
        f'<div class="tb-suivi-haut"><span>{ticker}</span>{variation_html}</div>'
        f'<div class="tb-suivi-prix">{prix}</div><div class="tb-suivi-nom">{nom or "&nbsp;"}</div></div>'
    )


def anneau(valeur, texte, couleur, taille=96, aria=""):
    """Jauge circulaire (SVG) remplie à `valeur` % (0 à 100), avec un texte au centre."""
    valeur = max(0.0, min(100.0, float(valeur)))
    return (
        f'<svg role="img" aria-label="{aria}" width="{taille}" height="{taille}" viewBox="0 0 36 36" style="flex: 0 0 auto">'
        f'<circle cx="18" cy="18" r="15.9" fill="none" stroke="{BORDURE}" stroke-width="3.2"></circle>'
        f'<circle cx="18" cy="18" r="15.9" fill="none" stroke="{couleur}" stroke-width="3.2" '
        f'stroke-dasharray="{valeur:.1f} {100 - valeur:.1f}" stroke-linecap="round" transform="rotate(-90 18 18)"></circle>'
        f'<text x="18" y="20.6" text-anchor="middle" fill="{TEXTE}" font-size="8" font-family="Space Grotesk" '
        f'font-weight="700">{texte}</text></svg>'
    )


def donut(parts, taille=104, aria=""):
    """Anneau de répartition (SVG). parts : liste de (pourcentage, couleur), dont la somme vaut 100."""
    cercles, deja = [], 0.0
    for pct, couleur in parts:
        cercles.append(
            f'<circle cx="18" cy="18" r="15.9" fill="none" stroke="{couleur}" stroke-width="4" '
            f'stroke-dasharray="{pct:.2f} {100 - pct:.2f}" stroke-dashoffset="{-deja:.2f}" transform="rotate(-90 18 18)"></circle>'
        )
        deja += pct
    return (f'<svg role="img" aria-label="{aria}" width="{taille}" height="{taille}" viewBox="0 0 36 36" '
            f'style="flex: 0 0 auto">{"".join(cercles)}</svg>')


def theme_graphique(fig, hauteur):
    """Donne au graphique Plotly l'allure de la maquette : fond transparent, grille fine horizontale."""
    fig.update_layout(
        template="plotly_dark" if MODE == "sombre" else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color=TEXTE_DISCRET, size=12),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor=CARTE, bordercolor=BORDURE_CHAMP, font=dict(color=TEXTE)),
        height=hauteur,
    )
    # Graphique avec un titre : le titre va tout en haut, la légende juste en dessous,
    # et on laisse assez de place pour qu'ils ne recouvrent ni l'un l'autre ni le graphique.
    if fig.layout.title.text:
        fig.update_layout(
            title=dict(x=0, xanchor="left", y=1, yref="container", yanchor="top", pad=dict(t=6, l=4),
                       font=dict(size=15, color=TEXTE, family="Space Grotesk, Inter, sans-serif")),
            margin=dict(t=90),
            legend=dict(y=1.04, yanchor="bottom"),
        )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=BORDURE)
    fig.update_yaxes(gridcolor=BORDURE, zeroline=False)
    return fig
