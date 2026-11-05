"""Actualités d'une action : mise en forme des données renvoyées par yfinance.

yfinance renvoie les articles sous deux formes selon sa version :
- ancienne : {"title", "link", "publisher", "providerPublishTime"}
- récente  : {"content": {"title", "summary", "pubDate", "provider", "canonicalUrl", ...}}
`normaliser` accepte les deux et renvoie toujours la même structure, ce qui isole
le reste de l'application des changements de yfinance.

Ce fichier ne dépend ni de Streamlit ni d'Internet.
"""

from datetime import datetime, timezone


def _lire_date(valeur):
    """Convertit une date de yfinance (texte ISO ou secondes) en datetime UTC, ou None."""
    try:
        if isinstance(valeur, (int, float)):
            return datetime.fromtimestamp(valeur, tz=timezone.utc)
        if isinstance(valeur, str) and valeur:
            return datetime.fromisoformat(valeur.replace("Z", "+00:00"))
    except (ValueError, OSError, OverflowError):
        pass
    return None


def _lien_valide(lien):
    """Ne garde que de vrais liens web (on écarte tout le reste, par prudence)."""
    return isinstance(lien, str) and lien.startswith(("https://", "http://"))


def _extraire_un_article(article):
    """Renvoie un dictionnaire normalisé pour un article, ou None s'il est inutilisable."""
    if not isinstance(article, dict):
        return None
    contenu = article.get("content") if isinstance(article.get("content"), dict) else article

    titre = contenu.get("title")
    if not isinstance(titre, str) or not titre.strip():
        return None

    # Le lien se cache à des endroits différents selon la version
    lien = None
    for cle in ("canonicalUrl", "clickThroughUrl"):
        candidat = contenu.get(cle)
        if isinstance(candidat, dict) and _lien_valide(candidat.get("url")):
            lien = candidat["url"]
            break
    if lien is None and _lien_valide(contenu.get("link")):
        lien = contenu["link"]
    if lien is None:
        return None   # sans lien, l'article ne sert à rien ici

    fournisseur = contenu.get("provider")
    if isinstance(fournisseur, dict):
        source = fournisseur.get("displayName")
    else:
        source = contenu.get("publisher")

    date = _lire_date(contenu.get("pubDate") or contenu.get("providerPublishTime"))
    resume = contenu.get("summary")

    return {
        "titre": titre.strip(),
        "lien": lien,
        "source": source if isinstance(source, str) and source else None,
        "date": date,
        "resume": resume.strip() if isinstance(resume, str) and resume.strip() else None,
    }


def normaliser(articles_bruts, limite=8):
    """Transforme la liste brute de yfinance en liste propre, du plus récent au plus ancien.

    Les articles sans titre ou sans lien, et les doublons de titre, sont ignorés.
    """
    propres = []
    titres_vus = set()
    for brut in articles_bruts or []:
        article = _extraire_un_article(brut)
        if article is None or article["titre"].lower() in titres_vus:
            continue
        titres_vus.add(article["titre"].lower())
        propres.append(article)

    plancher = datetime.min.replace(tzinfo=timezone.utc)
    propres.sort(key=lambda a: a["date"] or plancher, reverse=True)
    return propres[:limite]


def depuis(date, maintenant=None):
    """Âge d'un article en texte court : « il y a 3 h », « il y a 2 j », « le 28/10 »."""
    if date is None:
        return ""
    maintenant = maintenant or datetime.now(timezone.utc)
    secondes = (maintenant - date).total_seconds()
    if secondes < 0:
        secondes = 0
    if secondes < 3600:
        return f"il y a {max(1, int(secondes // 60))} min"
    if secondes < 86400:
        return f"il y a {int(secondes // 3600)} h"
    if secondes < 7 * 86400:
        return f"il y a {int(secondes // 86400)} j"
    return f"le {date:%d/%m}"


def lien_markdown(titre, lien):
    """Texte Markdown d'un lien cliquable. On neutralise les crochets et parenthèses du titre
    ou de l'adresse, qui casseraient la mise en forme (et les « $ » qui déclencheraient des formules)."""
    titre = titre.replace("[", "(").replace("]", ")")
    for caractere in ("\\", "*", "_", "`", "$", "~"):   # caractères que Markdown interpréterait
        titre = titre.replace(caractere, "\\" + caractere)
    lien = lien.replace("(", "%28").replace(")", "%29").replace(" ", "%20")
    return f"[{titre}]({lien})"
