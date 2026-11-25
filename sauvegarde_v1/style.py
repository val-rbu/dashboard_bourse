"""Apparence de l'application : couleurs, cartes et thème des graphiques (d'après la maquette).

Rien ici ne calcule de données : ce fichier ne sert qu'à l'habillage.
"""

import streamlit as st

# Deux palettes : sombre (celle de la maquette) et claire.
# appliquer(mode) recopie la palette choisie dans les variables ci-dessous (FOND, CARTE, TURQUOISE...),
# que app.py utilise aussi pour colorer les graphiques.
PALETTES = {
    "sombre": {
        "FOND": "#0B1220", "CARTE": "#121B2E", "CARTE_SURLIGNEE": "#1A2842", "BORDURE": "#22304A",
        "BORDURE_CHAMP": "#2B3B5A", "TEXTE": "#E8EDF7", "TEXTE_DISCRET": "#9FB0CC", "TURQUOISE": "#2DD4BF",
        "VERT": "#34D399", "ROUGE": "#F87171", "JAUNE": "#FBBF24", "TEXTE_BOUTON": "#06201C",
    },
    "clair": {
        "FOND": "#F4F7FB", "CARTE": "#FFFFFF", "CARTE_SURLIGNEE": "#EEF5F8", "BORDURE": "#E2E8F0",
        "BORDURE_CHAMP": "#CBD5E1", "TEXTE": "#0F172A", "TEXTE_DISCRET": "#64748B", "TURQUOISE": "#0D9488",
        "VERT": "#059669", "ROUGE": "#DC2626", "JAUNE": "#D97706", "TEXTE_BOUTON": "#FFFFFF",
    },
}

# Thème Streamlit correspondant (couleurs des boutons, champs, tableaux...)
THEMES_STREAMLIT = {
    "sombre": {"base": "dark", "primaryColor": "#2DD4BF", "backgroundColor": "#0B1220",
               "secondaryBackgroundColor": "#121B2E", "textColor": "#E8EDF7"},
    "clair": {"base": "light", "primaryColor": "#0D9488", "backgroundColor": "#F4F7FB",
              "secondaryBackgroundColor": "#E9EEF5", "textColor": "#0F172A"},
}

MODE = "sombre"
FOND = CARTE = CARTE_SURLIGNEE = BORDURE = BORDURE_CHAMP = TEXTE = TEXTE_DISCRET = ""
TURQUOISE = VERT = ROUGE = JAUNE = TEXTE_BOUTON = ""


def _choisir_palette(mode):
    global MODE
    MODE = mode if mode in PALETTES else "sombre"
    globals().update(PALETTES[MODE])


_choisir_palette("sombre")


def _css():
    """Feuille de style, construite avec les couleurs de la palette choisie."""
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, .stApp, .stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp button, .stApp input, .stApp label {{ font-family: Inter, system-ui, sans-serif; }}
/* Les icônes de Streamlit (flèches, croix...) ont leur propre police : on ne la remplace pas */
[data-testid="stIconMaterial"], .material-symbols-rounded, [class*="material-symbols"] {{ font-family: "Material Symbols Rounded" !important; }}
.stApp a {{ color: {TURQUOISE}; text-decoration: none; }}
.stApp a:hover {{ text-decoration: underline; }}
.stApp {{ background: {FOND}; }}
header[data-testid="stHeader"] {{ background: transparent; }}
/* Contenu calé à gauche et sur toute la largeur (barre latérale ouverte ou fermée) */
.block-container {{ padding: 2.2rem 1.5rem 2rem 1.5rem !important; max-width: none !important; margin: 0 !important; }}

/* Barre latérale = carte "Ma liste de suivi" */
[data-testid="stSidebar"] {{ background: {CARTE}; border-right: 1px solid {BORDURE}; }}
[data-testid="stSidebar"] h2 {{ font-size: 16px; font-weight: 600; }}

/* Cartes (st.container(border=True)) */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
    border-radius: 12px;
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {CARTE}; border-color: {BORDURE} !important; border-radius: 12px;
}}
/* Les cartes imbriquées (tuiles) gardent un fond plus sombre */
div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {FOND};
}}

/* Chiffres clés = tuiles sombres */
[data-testid="stMetric"] {{
    background: {FOND}; border-radius: 10px; padding: 10px 12px; border: 1px solid transparent;
}}
[data-testid="stMetricLabel"] p {{ color: {TEXTE_DISCRET}; font-size: 12px; }}
[data-testid="stMetricValue"] {{ font-weight: 600; font-size: 1.15rem; }}

/* Liste de suivi : chaque action est une carte, avec un bouton invisible posé dessus pour la rendre cliquable */
/* Barre latérale étroite (seulement quand elle est ouverte, pour ne pas gêner la fermeture) */
[data-testid="stSidebar"][data-collapsed="false"] {{ width: 260px !important; min-width: 260px !important; max-width: 260px !important; }}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{ padding-left: 12px; padding-right: 12px; }}
[class*="st-key-carte_"] {{ position: relative; }}
[class*="st-key-carte_"] [data-testid="stElementContainer"]:has(button),
[class*="st-key-carte_"] .element-container:has(button) {{ position: absolute; inset: 0; z-index: 2; margin: 0; }}
[class*="st-key-carte_"] button {{ width: 100%; height: 100%; opacity: 0; cursor: pointer; }}
.tb-liste-titre {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }}
.stApp .tb-liste-titre h2 {{ margin: 0 !important; padding: 0 !important; font-size: 16px !important; font-weight: 600 !important; }}
.tb-liste-titre {{ margin-bottom: 10px; }}
.tb-liste-titre span {{ font-size: 12px; color: {TEXTE_DISCRET}; }}
.tb-ligne {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 10px; border-radius: 10px; border: 1px solid transparent; }}
.tb-ligne:hover {{ background: {CARTE_SURLIGNEE}; }}
.tb-ligne.tb-choisie {{ background: {CARTE_SURLIGNEE}; border-color: {TURQUOISE}; }}
.tb-ticker {{ font-weight: 600; }}
.tb-prix-ligne {{ font-weight: 600; text-align: right; }}
.tb-variation-ligne {{ font-size: 12px; text-align: right; }}

/* Disposition : cours | actualités | alertes, toujours visibles */
@media (min-width: 900px) {{
  [data-testid="stColumn"]:has(.st-key-zone_principale) {{ flex: 2.6 1 0% !important; width: auto !important; min-width: 0; }}
  [data-testid="stColumn"]:has(.st-key-zone_actus) {{ flex: 1.25 1 0% !important; width: auto !important; min-width: 0; }}
  [data-testid="stColumn"]:has(.st-key-zone_alertes) {{ flex: 1.15 1 0% !important; width: auto !important; min-width: 0; }}
}}
[data-testid="stExpander"] summary p {{ white-space: nowrap; }}

/* Actualités */
.tb-actu {{ padding: 8px 0; border-bottom: 1px solid {BORDURE}; }}
.tb-actu a {{ color: {TEXTE} !important; font-weight: 500; line-height: 1.35; }}
.tb-actu a:hover {{ color: {TURQUOISE} !important; text-decoration: none !important; }}
.tb-actu .tb-discret {{ margin-top: 2px; }}
.tb-actu-compacte a {{ font-size: 13px; }}
.tb-actu-compacte .tb-discret {{ font-size: 11px; }}

/* Bouton « Nouvelle alerte » et son panneau déroulant */
[data-testid="stPopover"] button {{ border-radius: 10px; }}
[data-testid="stPopoverBody"] {{ background: {CARTE}; border: 1px solid {BORDURE_CHAMP}; border-radius: 12px; min-width: 320px; }}

/* Onglets du haut */
.st-key-vue button {{ font-size: 15px; padding: 6px 18px; }}

/* Boutons */
.stButton > button {{ border-radius: 10px; border: 1px solid {BORDURE_CHAMP}; background: {CARTE}; min-height: 40px; }}
.stButton > button:hover {{ border-color: {TURQUOISE}; color: {TURQUOISE}; }}
.stButton > button[kind="primary"] {{ background: {TURQUOISE}; color: {TEXTE_BOUTON}; border: 0; font-weight: 600; }}

/* Champs */
[data-baseweb="input"], [data-baseweb="select"] > div {{ border-radius: 10px; }}

/* Titres des cartes : Streamlit transforme les <h2> en titres à lui (la classe est perdue), on les style directement */
[data-testid="stMarkdownContainer"] h2 {{ font-size: 16px !important; font-weight: 600 !important; line-height: 1.4 !important; padding: 0 !important; margin: 0 0 6px 0 !important; letter-spacing: 0; }}
[data-testid="stMarkdownContainer"] h1 {{ font-size: 22px !important; font-weight: 700 !important; padding: 0 !important; }}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {{ margin: 0 !important; }}
[data-testid="stHeadingActionElements"] {{ display: none; }}   /* petit lien d'ancre à côté des titres */

/* Menus dépliants : le libellé commence déjà par « + », on masque l'icône flèche qui s'affichait en texte brut */
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {{ display: none; }}
[data-testid="stExpander"] summary {{ padding: 8px 12px; }}

/* Éléments de l'en-tête (HTML maison) */
.tb-entete {{ display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 4px; }}
.tb-entete h1 {{ margin: 0; padding: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.01em; }}
.tb-pastille {{ font-size: 12px; color: {TEXTE_DISCRET}; border: 1px solid {BORDURE_CHAMP}; border-radius: 999px; padding: 2px 10px; }}
.stApp h2.tb-titre-carte, .tb-titre-carte {{ margin: 0 0 6px 0 !important; padding: 0 !important; font-size: 16px !important; font-weight: 600 !important; line-height: 1.4 !important; }}
.tb-prix {{ font-size: 32px; font-weight: 700; letter-spacing: -0.02em; margin-right: 10px; }}
.tb-hausse {{ color: {VERT}; font-weight: 600; }}
.tb-baisse {{ color: {ROUGE}; font-weight: 600; }}
.tb-discret {{ font-size: 12px; color: {TEXTE_DISCRET}; }}
.tb-tuile-titre {{ font-size: 12px; color: {TEXTE_DISCRET}; margin-bottom: 4px; }}
.tb-tuile-valeur {{ font-size: 22px; font-weight: 700; white-space: nowrap; }}

.tb-barre {{ position: relative; height: 8px; border-radius: 4px; background: {BORDURE}; margin: 8px 0 4px; }}
.tb-barre > div {{ position: absolute; left: 0; top: 0; height: 8px; border-radius: 4px; background: {TURQUOISE}; }}
.tb-bornes {{ display: flex; justify-content: space-between; font-size: 11px; color: {TEXTE_DISCRET}; }}
</style>
"""


def appliquer(mode="sombre"):
    """Choisit la palette ("sombre" ou "clair") et injecte le style dans la page (en haut de app.py)."""
    _choisir_palette(mode)
    st.markdown(_css(), unsafe_allow_html=True)


def tuile(titre, valeur, detail="", classe_detail="tb-discret", barre=None, bornes=None):
    """Petite carte de la maquette (titre discret, grande valeur, détail). Renvoie du HTML.

    barre : pourcentage (0 à 100) d'une jauge ; bornes : (texte gauche, texte droit) sous la jauge.
    """
    html = f'<div class="tb-tuile-titre">{titre}</div><div class="tb-tuile-valeur">{valeur}</div>'
    if barre is not None:
        html += f'<div class="tb-barre"><div style="width:{max(0, min(100, barre)):.0f}%"></div></div>'
    if bornes:
        html += f'<div class="tb-bornes"><span>{bornes[0]}</span><span>{bornes[1]}</span></div>'
    if detail:
        html += f'<div class="{classe_detail}" style="margin-top:6px">{detail}</div>'
    return html


def theme_graphique(fig, hauteur):
    """Donne au graphique Plotly l'allure de la maquette : fond transparent, grille fine horizontale."""
    fig.update_layout(
        template="plotly_dark" if MODE == "sombre" else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color=TEXTE_DISCRET, size=12),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor=CARTE, bordercolor=BORDURE_CHAMP),
        height=hauteur,
    )
    # Graphique avec un titre : le titre va tout en haut, la légende juste en dessous,
    # et on laisse assez de place pour qu'ils ne recouvrent ni l'un l'autre ni le graphique.
    if fig.layout.title.text:
        fig.update_layout(
            title=dict(x=0, xanchor="left", y=1, yref="container", yanchor="top", pad=dict(t=6, l=4),
                       font=dict(size=15, color=TEXTE)),
            margin=dict(t=90),
            legend=dict(y=1.04, yanchor="bottom"),
        )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=BORDURE)
    fig.update_yaxes(gridcolor=BORDURE, zeroline=False)
    return fig


def sparkline(valeurs, couleur, largeur=80, hauteur=24):
    """Petite courbe SVG (sans axes) à partir d'une liste de cours."""
    if len(valeurs) < 2:
        return ""
    bas, haut = min(valeurs), max(valeurs)
    etendue = (haut - bas) or 1.0
    n = len(valeurs) - 1
    points = " ".join(
        f"{i * largeur / n:.1f},{hauteur - 3 - (v - bas) / etendue * (hauteur - 6):.1f}" for i, v in enumerate(valeurs)
    )
    return (
        f'<svg width="{largeur}" height="{hauteur}" viewBox="0 0 {largeur} {hauteur}" aria-hidden="true">'
        f'<polyline points="{points}" fill="none" stroke="{couleur}" stroke-width="1.8" '
        'stroke-linejoin="round" stroke-linecap="round"/></svg>'
    )


def ligne_suivi(ticker, prix, variation, choisie):
    """Carte d'une action dans la liste de suivi (HTML) : ticker à gauche, prix et variation du jour à droite."""
    if prix is None:
        droite = '<div class="tb-variation-ligne tb-discret">indisponible</div>'
    else:
        hausse = variation >= 0
        classe = "tb-hausse" if hausse else "tb-baisse"
        droite = (
            f'<div class="tb-prix-ligne">{prix}</div>'
            f'<div class="tb-variation-ligne {classe}">{"▲" if hausse else "▼"} {variation:+.2f} %</div>'
        )
    return f'<div class="tb-ligne{" tb-choisie" if choisie else ""}"><div class="tb-ticker">{ticker}</div><div>{droite}</div></div>'
