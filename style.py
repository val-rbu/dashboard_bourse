"""Apparence de l'application : couleurs, cartes et thème des graphiques (d'après la maquette).

Rien ici ne calcule de données : ce fichier ne sert qu'à l'habillage.
"""

import streamlit as st

# Palette de la maquette
FOND = "#0B1220"
CARTE = "#121B2E"
CARTE_SURLIGNEE = "#1A2842"
BORDURE = "#22304A"
BORDURE_CHAMP = "#2B3B5A"
TEXTE = "#E8EDF7"
TEXTE_DISCRET = "#9FB0CC"
TURQUOISE = "#2DD4BF"
VERT = "#34D399"
ROUGE = "#F87171"
JAUNE = "#FBBF24"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, .stApp, [data-testid="stSidebar"] * {{ font-family: Inter, system-ui, sans-serif; }}
.stApp {{ background: {FOND}; }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.2rem; max-width: 1400px; }}

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
[data-testid="stSidebar"] {{ min-width: 340px; }}
[class*="st-key-carte_"] {{ position: relative; }}
[class*="st-key-carte_"] [data-testid="stElementContainer"]:has(button),
[class*="st-key-carte_"] .element-container:has(button) {{ position: absolute; inset: 0; z-index: 2; margin: 0; }}
[class*="st-key-carte_"] button {{ width: 100%; height: 100%; opacity: 0; cursor: pointer; }}
.tb-liste-titre {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }}
.tb-liste-titre h2 {{ margin: 0; padding: 0; font-size: 16px; font-weight: 600; }}
.tb-liste-titre span {{ font-size: 12px; color: {TEXTE_DISCRET}; }}
.tb-ligne {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px; border-radius: 10px; border: 1px solid transparent; }}
.tb-ligne:hover {{ background: {CARTE_SURLIGNEE}; }}
.tb-ligne.tb-choisie {{ background: {CARTE_SURLIGNEE}; border-color: {TURQUOISE}; }}
.tb-ticker {{ font-weight: 600; }}
.tb-prix-ligne {{ font-weight: 600; text-align: right; }}
.tb-variation-ligne {{ font-size: 12px; text-align: right; }}

/* Onglets du haut */
.st-key-vue button {{ font-size: 15px; padding: 6px 18px; }}

/* Boutons */
.stButton > button {{ border-radius: 10px; border: 1px solid {BORDURE_CHAMP}; background: {CARTE}; min-height: 40px; }}
.stButton > button:hover {{ border-color: {TURQUOISE}; color: {TURQUOISE}; }}
.stButton > button[kind="primary"] {{ background: {TURQUOISE}; color: #06201C; border: 0; font-weight: 600; }}

/* Champs */
[data-baseweb="input"], [data-baseweb="select"] > div {{ border-radius: 10px; }}

/* Éléments de l'en-tête (HTML maison) */
.tb-entete {{ display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 4px; }}
.tb-entete h1 {{ margin: 0; padding: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.01em; }}
.tb-pastille {{ font-size: 12px; color: {TEXTE_DISCRET}; border: 1px solid {BORDURE_CHAMP}; border-radius: 999px; padding: 2px 10px; }}
.tb-titre-carte {{ margin: 0; font-size: 16px; font-weight: 600; }}
.tb-prix {{ font-size: 32px; font-weight: 700; letter-spacing: -0.02em; margin-right: 10px; }}
.tb-hausse {{ color: {VERT}; font-weight: 600; }}
.tb-baisse {{ color: {ROUGE}; font-weight: 600; }}
.tb-discret {{ font-size: 12px; color: {TEXTE_DISCRET}; }}
.tb-tuile-titre {{ font-size: 12px; color: {TEXTE_DISCRET}; margin-bottom: 4px; }}
.tb-tuile-valeur {{ font-size: 24px; font-weight: 700; }}
.tb-barre {{ position: relative; height: 8px; border-radius: 4px; background: {BORDURE}; margin: 8px 0 4px; }}
.tb-barre > div {{ position: absolute; left: 0; top: 0; height: 8px; border-radius: 4px; background: {TURQUOISE}; }}
.tb-bornes {{ display: flex; justify-content: space-between; font-size: 11px; color: {TEXTE_DISCRET}; }}
</style>
"""


def appliquer():
    """Injecte le style dans la page (à appeler une fois, en haut de app.py)."""
    st.markdown(CSS, unsafe_allow_html=True)


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
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color=TEXTE_DISCRET, size=12),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor=CARTE, bordercolor=BORDURE_CHAMP),
        height=hauteur,
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


def ligne_suivi(ticker, prix, variation, valeurs, choisie):
    """Carte d'une action dans la liste de suivi (HTML). prix : texte déjà formaté ; variation : en %."""
    if prix is None:
        droite = '<div class="tb-variation-ligne tb-discret">indisponible</div>'
        courbe = ""
    else:
        hausse = variation >= 0
        couleur = VERT if hausse else ROUGE
        classe = "tb-hausse" if hausse else "tb-baisse"
        courbe = sparkline(valeurs, couleur)
        droite = (
            f'<div class="tb-prix-ligne">{prix}</div>'
            f'<div class="tb-variation-ligne {classe}">{"▲" if hausse else "▼"} {variation:+.2f} %</div>'
        )
    return (
        f'<div class="tb-ligne{" tb-choisie" if choisie else ""}">'
        f'<div class="tb-ticker">{ticker}</div>{courbe}<div>{droite}</div></div>'
    )
