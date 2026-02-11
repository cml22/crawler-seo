"""
Moteur d'audit SEO — Détection d'issues, warnings et opportunities
Inspiré de Screaming Frog (sous-ensemble des 300+ checks)
"""

from urllib.parse import urlparse

# ──────────────────────────────────────────────
# Types et priorités
# ──────────────────────────────────────────────
ISSUE = "Issue"
WARNING = "Warning"
OPPORTUNITY = "Opportunity"

HIGH = "High"
MEDIUM = "Medium"
LOW = "Low"


def create_issue(
    category: str,
    check_name: str,
    issue_type: str,
    priority: str,
    url: str,
    description: str,
    guidance: str,
) -> dict:
    """Crée un dictionnaire représentant un problème SEO détecté."""
    return {
        "Category": category,
        "Check": check_name,
        "Type": issue_type,
        "Priority": priority,
        "URL": url,
        "Description": description,
        "Guidance": guidance,
    }


# ──────────────────────────────────────────────
# RESPONSE CODES
# ──────────────────────────────────────────────
def check_response_codes(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    status = page.get("status_code")

    if not isinstance(status, int):
        issues.append(create_issue(
            "Response Codes", "No Response", ISSUE, HIGH, url,
            f"La page n'a pas répondu : {status}",
            "Vérifiez que le serveur est accessible et que l'URL est correcte.",
        ))
        return issues

    if 300 <= status < 400:
        issues.append(create_issue(
            "Response Codes", f"Redirection {status}", WARNING, MEDIUM, url,
            f"La page retourne une redirection {status}.",
            "Les redirections ajoutent de la latence. Mettez à jour les liens internes pour pointer directement vers l'URL finale.",
        ))
    elif status == 404:
        issues.append(create_issue(
            "Response Codes", "404 Not Found", ISSUE, HIGH, url,
            "La page retourne une erreur 404.",
            "Supprimez ou corrigez les liens pointant vers cette URL. Mettez en place une redirection 301 si le contenu a été déplacé.",
        ))
    elif status == 410:
        issues.append(create_issue(
            "Response Codes", "410 Gone", ISSUE, MEDIUM, url,
            "La page retourne un code 410 (supprimée définitivement).",
            "Supprimez les liens internes pointant vers cette URL.",
        ))
    elif 400 <= status < 500:
        issues.append(create_issue(
            "Response Codes", f"Client Error {status}", ISSUE, HIGH, url,
            f"La page retourne une erreur client {status}.",
            "Vérifiez l'URL et les permissions d'accès.",
        ))
    elif status >= 500:
        issues.append(create_issue(
            "Response Codes", f"Server Error {status}", ISSUE, HIGH, url,
            f"La page retourne une erreur serveur {status}.",
            "Contactez l'administrateur du serveur. Les erreurs 5xx empêchent l'indexation.",
        ))

    return issues


# ──────────────────────────────────────────────
# SECURITY
# ──────────────────────────────────────────────
def check_security(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    parsed = urlparse(url)
    headers = page.get("response_headers", {})

    # HTTP URLs
    if parsed.scheme == "http":
        issues.append(create_issue(
            "Security", "HTTP URL", ISSUE, HIGH, url,
            "La page est servie en HTTP (non sécurisé).",
            "Migrez vers HTTPS. Les navigateurs affichent un avertissement et Google privilégie les sites HTTPS.",
        ))

    # Mixed content
    mixed_content = page.get("mixed_content", [])
    if mixed_content:
        issues.append(create_issue(
            "Security", "Mixed Content", ISSUE, HIGH, url,
            f"{len(mixed_content)} ressource(s) chargée(s) en HTTP sur une page HTTPS.",
            "Mettez à jour les URLs des ressources pour utiliser HTTPS.",
        ))

    # Missing HSTS
    if "strict-transport-security" not in headers:
        issues.append(create_issue(
            "Security", "Missing HSTS Header", WARNING, MEDIUM, url,
            "L'en-tête Strict-Transport-Security est absent.",
            "Ajoutez l'en-tête HSTS pour forcer les connexions HTTPS.",
        ))

    # Missing Content-Security-Policy
    if "content-security-policy" not in headers:
        issues.append(create_issue(
            "Security", "Missing Content-Security-Policy Header", WARNING, LOW, url,
            "L'en-tête Content-Security-Policy est absent.",
            "Ajoutez une CSP pour réduire les risques d'attaques XSS.",
        ))

    # Missing X-Content-Type-Options
    if "x-content-type-options" not in headers:
        issues.append(create_issue(
            "Security", "Missing X-Content-Type-Options Header", WARNING, LOW, url,
            "L'en-tête X-Content-Type-Options est absent.",
            "Ajoutez 'X-Content-Type-Options: nosniff' pour empêcher le MIME-type sniffing.",
        ))

    # Missing X-Frame-Options
    if "x-frame-options" not in headers:
        issues.append(create_issue(
            "Security", "Missing X-Frame-Options Header", WARNING, LOW, url,
            "L'en-tête X-Frame-Options est absent.",
            "Ajoutez cet en-tête pour empêcher le clickjacking.",
        ))

    return issues


# ──────────────────────────────────────────────
# URL
# ──────────────────────────────────────────────
def check_url(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    parsed = urlparse(url)
    path = parsed.path

    # Multiple slashes
    if "//" in path:
        issues.append(create_issue(
            "URL", "Multiple Slashes", ISSUE, MEDIUM, url,
            "L'URL contient des doubles slashes dans le chemin.",
            "Corrigez l'URL pour n'avoir qu'un seul slash entre chaque segment.",
        ))

    # Contains a space
    if " " in url or "%20" in url:
        issues.append(create_issue(
            "URL", "Contains A Space", ISSUE, MEDIUM, url,
            "L'URL contient un espace.",
            "Remplacez les espaces par des tirets dans les URLs.",
        ))

    # Uppercase
    if path != path.lower():
        issues.append(create_issue(
            "URL", "Uppercase", WARNING, LOW, url,
            "L'URL contient des majuscules.",
            "Utilisez des URLs en minuscules pour éviter les problèmes de duplicate content.",
        ))

    # Parameters
    if parsed.query:
        issues.append(create_issue(
            "URL", "Parameters", WARNING, LOW, url,
            f"L'URL contient des paramètres de requête : ?{parsed.query}",
            "Vérifiez que les paramètres sont nécessaires et que les URLs avec paramètres sont correctement canonicalisées.",
        ))

    # Underscores
    if "_" in path:
        issues.append(create_issue(
            "URL", "Underscores", OPPORTUNITY, LOW, url,
            "L'URL contient des underscores.",
            "Google recommande d'utiliser des tirets (-) plutôt que des underscores (_) dans les URLs.",
        ))

    # Over 115 characters
    if len(url) > 115:
        issues.append(create_issue(
            "URL", "Over 115 Characters", OPPORTUNITY, LOW, url,
            f"L'URL fait {len(url)} caractères (> 115).",
            "Les URLs courtes sont plus faciles à partager et à comprendre pour les utilisateurs.",
        ))

    # Non ASCII
    try:
        url.encode("ascii")
    except UnicodeEncodeError:
        issues.append(create_issue(
            "URL", "Non ASCII Characters", WARNING, MEDIUM, url,
            "L'URL contient des caractères non-ASCII.",
            "Utilisez des caractères ASCII dans les URLs pour une meilleure compatibilité.",
        ))

    return issues


# ──────────────────────────────────────────────
# PAGE TITLES
# ──────────────────────────────────────────────
def check_page_title(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    title = page.get("title", "")
    title_count = page.get("title_count", 0)
    h1 = page.get("h1", "")

    if not title:
        issues.append(create_issue(
            "Page Titles", "Missing", ISSUE, HIGH, url,
            "La page n'a pas de balise <title>.",
            "Chaque page doit avoir un titre unique et descriptif. Le titre est un facteur de ranking important.",
        ))
        return issues

    if title_count > 1:
        issues.append(create_issue(
            "Page Titles", "Multiple", ISSUE, MEDIUM, url,
            f"La page contient {title_count} balises <title>.",
            "Une seule balise <title> doit être présente dans le <head>.",
        ))

    title_len = len(title)
    if title_len > 60:
        issues.append(create_issue(
            "Page Titles", "Over 60 Characters", OPPORTUNITY, MEDIUM, url,
            f"Le titre fait {title_len} caractères (> 60). Il sera tronqué dans les SERPs.",
            "Gardez le titre sous 60 caractères pour qu'il s'affiche entièrement dans Google.",
        ))
    elif title_len < 30:
        issues.append(create_issue(
            "Page Titles", "Below 30 Characters", OPPORTUNITY, LOW, url,
            f"Le titre fait seulement {title_len} caractères (< 30).",
            "Un titre trop court peut manquer de contexte. Visez 30-60 caractères.",
        ))

    if title and h1 and title.strip().lower() == h1.strip().lower():
        issues.append(create_issue(
            "Page Titles", "Same as H1", OPPORTUNITY, LOW, url,
            "Le titre est identique au H1.",
            "Différenciez légèrement le titre et le H1 pour maximiser la couverture sémantique.",
        ))

    return issues


# ──────────────────────────────────────────────
# META DESCRIPTION
# ──────────────────────────────────────────────
def check_meta_description(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    meta_desc = page.get("meta_description", "")
    meta_desc_count = page.get("meta_description_count", 0)

    if not meta_desc:
        issues.append(create_issue(
            "Meta Description", "Missing", OPPORTUNITY, MEDIUM, url,
            "La page n'a pas de meta description.",
            "Ajoutez une meta description unique et engageante (70-155 caractères) pour améliorer le CTR dans les SERPs.",
        ))
        return issues

    if meta_desc_count > 1:
        issues.append(create_issue(
            "Meta Description", "Multiple", ISSUE, MEDIUM, url,
            f"La page contient {meta_desc_count} meta descriptions.",
            "Une seule meta description doit être présente.",
        ))

    desc_len = len(meta_desc)
    if desc_len > 155:
        issues.append(create_issue(
            "Meta Description", "Over 155 Characters", OPPORTUNITY, LOW, url,
            f"La meta description fait {desc_len} caractères (> 155). Elle sera tronquée.",
            "Gardez la meta description sous 155 caractères.",
        ))
    elif desc_len < 70:
        issues.append(create_issue(
            "Meta Description", "Below 70 Characters", OPPORTUNITY, LOW, url,
            f"La meta description fait seulement {desc_len} caractères (< 70).",
            "Une meta description trop courte est une opportunité manquée. Visez 70-155 caractères.",
        ))

    return issues


# ──────────────────────────────────────────────
# H1
# ──────────────────────────────────────────────
def check_h1(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    h1 = page.get("h1", "")
    h1_count = page.get("h1_count", 0)

    if not h1:
        issues.append(create_issue(
            "H1", "Missing", ISSUE, HIGH, url,
            "La page n'a pas de balise H1.",
            "Chaque page doit avoir un H1 unique décrivant le sujet principal de la page.",
        ))
        return issues

    if h1_count > 1:
        issues.append(create_issue(
            "H1", "Multiple", WARNING, MEDIUM, url,
            f"La page contient {h1_count} balises H1.",
            "Il est recommandé de n'avoir qu'un seul H1 par page.",
        ))

    if len(h1) > 70:
        issues.append(create_issue(
            "H1", "Over 70 Characters", OPPORTUNITY, LOW, url,
            f"Le H1 fait {len(h1)} caractères (> 70).",
            "Gardez le H1 concis et descriptif.",
        ))

    return issues


# ──────────────────────────────────────────────
# H2
# ──────────────────────────────────────────────
def check_h2(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    h2_list = page.get("h2_list", [])
    h1 = page.get("h1", "")

    if not h2_list:
        issues.append(create_issue(
            "H2", "Missing", WARNING, LOW, url,
            "La page n'a pas de balise H2.",
            "Les H2 aident à structurer le contenu et améliorent la lisibilité pour les utilisateurs et les moteurs de recherche.",
        ))

    for h2 in h2_list:
        if len(h2) > 70:
            issues.append(create_issue(
                "H2", "Over 70 Characters", OPPORTUNITY, LOW, url,
                f"Un H2 fait {len(h2)} caractères : \"{h2[:50]}...\"",
                "Gardez les H2 concis.",
            ))

    # Non-sequential: H2 sans H1
    if h2_list and not h1:
        issues.append(create_issue(
            "H2", "Non-sequential", WARNING, MEDIUM, url,
            "La page a des H2 mais pas de H1.",
            "La hiérarchie des headings doit commencer par un H1.",
        ))

    return issues


# ──────────────────────────────────────────────
# IMAGES
# ──────────────────────────────────────────────
def check_images(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    images = page.get("images", [])

    for img in images:
        src = img.get("src", "N/A")
        alt = img.get("alt")

        if alt is None:
            issues.append(create_issue(
                "Images", "Missing Alt Attribute", ISSUE, MEDIUM, url,
                f"Image sans attribut alt : {src[:80]}",
                "Ajoutez un attribut alt à toutes les images pour l'accessibilité et le SEO.",
            ))
        elif alt == "":
            issues.append(create_issue(
                "Images", "Missing Alt Text", ISSUE, MEDIUM, url,
                f"Image avec alt vide : {src[:80]}",
                "Ajoutez un texte alt descriptif (sauf pour les images purement décoratives).",
            ))
        elif len(alt) > 100:
            issues.append(create_issue(
                "Images", "Alt Text Over 100 Characters", OPPORTUNITY, LOW, url,
                f"Alt text trop long ({len(alt)} car.) : \"{alt[:50]}...\"",
                "Gardez le texte alt concis et descriptif (< 100 caractères).",
            ))

    return issues


# ──────────────────────────────────────────────
# CANONICALS
# ──────────────────────────────────────────────
def check_canonicals(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    canonicals = page.get("canonicals", [])

    if not canonicals:
        issues.append(create_issue(
            "Canonicals", "Missing", WARNING, MEDIUM, url,
            "La page n'a pas de balise canonical.",
            "Ajoutez une balise rel=\"canonical\" pour indiquer la version préférée de l'URL aux moteurs de recherche.",
        ))
    elif len(canonicals) > 1:
        issues.append(create_issue(
            "Canonicals", "Multiple Conflicting", ISSUE, HIGH, url,
            f"La page contient {len(canonicals)} balises canonical différentes.",
            "Une seule balise canonical doit être présente. Plusieurs canonicals conflictuels perturbent les moteurs de recherche.",
        ))
    else:
        canonical = canonicals[0]
        # Canonical pointe vers une autre URL
        if canonical and canonical != url:
            issues.append(create_issue(
                "Canonicals", "Canonicalised", WARNING, MEDIUM, url,
                f"La page est canonicalisée vers : {canonical}",
                "Vérifiez que cette canonicalisation est intentionnelle.",
            ))
        # Canonical relative
        if canonical and not canonical.startswith("http"):
            issues.append(create_issue(
                "Canonicals", "Canonical Is Relative", WARNING, LOW, url,
                f"La canonical est relative : {canonical}",
                "Utilisez des URLs absolues pour les balises canonical.",
            ))

    return issues


# ──────────────────────────────────────────────
# DIRECTIVES (meta robots, X-Robots-Tag)
# ──────────────────────────────────────────────
def check_directives(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    meta_robots = page.get("meta_robots", "").lower()
    x_robots = page.get("x_robots_tag", "").lower()
    combined = f"{meta_robots} {x_robots}"

    if "noindex" in combined:
        issues.append(create_issue(
            "Directives", "Noindex", WARNING, HIGH, url,
            "La page contient une directive noindex.",
            "Vérifiez que cette page ne doit effectivement pas être indexée. Si c'est une erreur, retirez la directive.",
        ))

    if "nofollow" in combined:
        issues.append(create_issue(
            "Directives", "Nofollow", WARNING, MEDIUM, url,
            "La page contient une directive nofollow.",
            "Les liens de cette page ne transmettent pas de PageRank. Vérifiez que c'est intentionnel.",
        ))

    if "none" in combined:
        issues.append(create_issue(
            "Directives", "None", WARNING, HIGH, url,
            "La page contient une directive 'none' (équivalent noindex, nofollow).",
            "Cette page ne sera ni indexée ni suivie. Vérifiez que c'est intentionnel.",
        ))

    if "nosnippet" in combined:
        issues.append(create_issue(
            "Directives", "NoSnippet", WARNING, LOW, url,
            "La page contient une directive nosnippet.",
            "Aucun extrait ne sera affiché dans les SERPs. Cela peut réduire le CTR.",
        ))

    return issues


# ──────────────────────────────────────────────
# LINKS
# ──────────────────────────────────────────────
def check_links(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    depth = page.get("depth", 0)
    internal_outlinks = page.get("internal_outlinks", 0)
    external_outlinks = page.get("external_outlinks", 0)
    nofollow_outlinks = page.get("nofollow_outlinks", 0)
    empty_anchor_links = page.get("empty_anchor_links", 0)

    if depth > 3:
        issues.append(create_issue(
            "Links", "Pages With High Crawl Depth", OPPORTUNITY, MEDIUM, url,
            f"La page est à une profondeur de {depth} clics depuis la page d'accueil.",
            "Les pages importantes devraient être accessibles en 3 clics maximum. Améliorez le maillage interne.",
        ))

    if internal_outlinks == 0:
        issues.append(create_issue(
            "Links", "Pages Without Internal Outlinks", WARNING, MEDIUM, url,
            "La page ne contient aucun lien interne sortant.",
            "Ajoutez des liens internes pour aider les utilisateurs et les moteurs de recherche à naviguer.",
        ))

    if external_outlinks > 100:
        issues.append(create_issue(
            "Links", "Pages With High External Outlinks", WARNING, LOW, url,
            f"La page contient {external_outlinks} liens externes.",
            "Un nombre excessif de liens externes peut diluer le PageRank.",
        ))

    if nofollow_outlinks > 0:
        issues.append(create_issue(
            "Links", "Internal Nofollow Outlinks", WARNING, LOW, url,
            f"La page contient {nofollow_outlinks} lien(s) interne(s) en nofollow.",
            "Évitez le nofollow sur les liens internes pour permettre la circulation du PageRank.",
        ))

    if empty_anchor_links > 0:
        issues.append(create_issue(
            "Links", "Internal Outlinks With No Anchor Text", OPPORTUNITY, MEDIUM, url,
            f"{empty_anchor_links} lien(s) interne(s) sans texte d'ancre.",
            "Ajoutez un texte d'ancre descriptif pour aider les utilisateurs et les moteurs de recherche.",
        ))

    return issues


# ──────────────────────────────────────────────
# CONTENT
# ──────────────────────────────────────────────
def check_content(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    word_count = page.get("word_count", 0)
    text_content = page.get("text_content", "").lower()

    if word_count < 100 and page.get("status_code") == 200:
        issues.append(create_issue(
            "Content", "Low Content Pages", OPPORTUNITY, MEDIUM, url,
            f"La page ne contient que {word_count} mots.",
            "Les pages avec peu de contenu peuvent avoir du mal à se positionner. Enrichissez le contenu si pertinent.",
        ))

    if "lorem ipsum" in text_content:
        issues.append(create_issue(
            "Content", "Lorem Ipsum Placeholder", WARNING, HIGH, url,
            "La page contient du texte Lorem Ipsum (placeholder).",
            "Remplacez le texte placeholder par du contenu réel avant la mise en production.",
        ))

    return issues


# ──────────────────────────────────────────────
# VALIDATION HTML
# ──────────────────────────────────────────────
def check_validation(page: dict) -> list[dict]:
    issues = []
    url = page["URL"]
    has_head = page.get("has_head_tag", True)
    has_body = page.get("has_body_tag", True)
    head_count = page.get("head_count", 1)
    body_count = page.get("body_count", 1)
    html_size = page.get("html_size_bytes", 0)

    if not has_head:
        issues.append(create_issue(
            "Validation", "Missing <head> Tag", ISSUE, HIGH, url,
            "La page n'a pas de balise <head>.",
            "La balise <head> est essentielle pour les métadonnées de la page.",
        ))

    if head_count > 1:
        issues.append(create_issue(
            "Validation", "Multiple <head> Tags", ISSUE, MEDIUM, url,
            f"La page contient {head_count} balises <head>.",
            "Une seule balise <head> doit être présente.",
        ))

    if not has_body:
        issues.append(create_issue(
            "Validation", "Missing <body> Tag", ISSUE, HIGH, url,
            "La page n'a pas de balise <body>.",
            "La balise <body> est essentielle pour le contenu de la page.",
        ))

    if body_count > 1:
        issues.append(create_issue(
            "Validation", "Multiple <body> Tags", ISSUE, MEDIUM, url,
            f"La page contient {body_count} balises <body>.",
            "Une seule balise <body> doit être présente.",
        ))

    if html_size > 15_000_000:
        issues.append(create_issue(
            "Validation", "HTML Document Over 15mb", ISSUE, HIGH, url,
            f"Le document HTML fait {html_size / 1_000_000:.1f} Mo (> 15 Mo).",
            "Les documents très volumineux sont lents à charger et à parser par les moteurs de recherche.",
        ))

    return issues


# ──────────────────────────────────────────────
# DUPLICATES (cross-page checks)
# ──────────────────────────────────────────────
def check_duplicates(all_pages: list[dict]) -> list[dict]:
    """Vérifie les doublons de titres et meta descriptions sur l'ensemble du site."""
    issues = []

    # Duplicate titles
    titles = {}
    for page in all_pages:
        title = page.get("title", "")
        if title:
            titles.setdefault(title, []).append(page["URL"])

    for title, urls in titles.items():
        if len(urls) > 1:
            for url in urls:
                issues.append(create_issue(
                    "Page Titles", "Duplicate", OPPORTUNITY, MEDIUM, url,
                    f"Titre dupliqué sur {len(urls)} pages : \"{title[:60]}\"",
                    "Chaque page devrait avoir un titre unique pour éviter la cannibalisation.",
                ))

    # Duplicate meta descriptions
    metas = {}
    for page in all_pages:
        meta = page.get("meta_description", "")
        if meta:
            metas.setdefault(meta, []).append(page["URL"])

    for meta, urls in metas.items():
        if len(urls) > 1:
            for url in urls:
                issues.append(create_issue(
                    "Meta Description", "Duplicate", OPPORTUNITY, MEDIUM, url,
                    f"Meta description dupliquée sur {len(urls)} pages : \"{meta[:60]}...\"",
                    "Chaque page devrait avoir une meta description unique.",
                ))

    # Duplicate H1
    h1s = {}
    for page in all_pages:
        h1 = page.get("h1", "")
        if h1:
            h1s.setdefault(h1, []).append(page["URL"])

    for h1, urls in h1s.items():
        if len(urls) > 1:
            for url in urls:
                issues.append(create_issue(
                    "H1", "Duplicate", OPPORTUNITY, LOW, url,
                    f"H1 dupliqué sur {len(urls)} pages : \"{h1[:60]}\"",
                    "Chaque page devrait avoir un H1 unique.",
                ))

    return issues


# ──────────────────────────────────────────────
# MOTEUR PRINCIPAL
# ──────────────────────────────────────────────
PER_PAGE_CHECKS = [
    check_response_codes,
    check_security,
    check_url,
    check_page_title,
    check_meta_description,
    check_h1,
    check_h2,
    check_images,
    check_canonicals,
    check_directives,
    check_links,
    check_content,
    check_validation,
]


def run_audit(all_pages: list[dict]) -> list[dict]:
    """
    Lance tous les checks SEO sur l'ensemble des pages crawlées.
    Retourne la liste complète des issues détectées.
    """
    all_issues = []

    # Checks par page
    for page in all_pages:
        for check_fn in PER_PAGE_CHECKS:
            all_issues.extend(check_fn(page))

    # Checks cross-page (doublons)
    all_issues.extend(check_duplicates(all_pages))

    return all_issues
