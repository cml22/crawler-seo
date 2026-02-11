"""
Crawler SEO Récursif — Style Screaming Frog
Déployable sur Streamlit Cloud
"""

import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse

# ──────────────────────────────────────────────
# Configuration de la page
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Crawler SEO — charles-migaud.fr",
    page_icon="🕷️",
    layout="wide",
)

st.title("🕷️ Crawler SEO Récursif")
st.markdown(
    "Analyse les pages d'un site web comme **Screaming Frog** : "
    "status codes, titres, meta descriptions, H1 et profondeur de crawl."
)

# ──────────────────────────────────────────────
# Sidebar — Paramètres
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("Paramètres du crawl")
    start_url = st.text_input(
        "URL de départ",
        value="https://charles-migaud.fr",
        help="L'URL à partir de laquelle le crawl démarre.",
    )
    max_pages = st.slider(
        "Nombre max de pages",
        min_value=10,
        max_value=500,
        value=50,
        step=10,
        help="Le crawler s'arrête une fois cette limite atteinte.",
    )
    crawl_button = st.button("🚀 Lancer le crawl", type="primary", use_container_width=True)

# ──────────────────────────────────────────────
# Fonctions utilitaires
# ──────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (compatible; CrawlerSEO/1.0; +https://crawler.charles-migaud.fr)"
)
REQUEST_TIMEOUT = 10  # secondes


def normalize_url(url: str) -> str:
    """Normalise une URL : supprime le fragment, les trailing slashes inutiles."""
    parsed = urlparse(url)
    # Supprimer le fragment (#)
    # Normaliser le path : au minimum "/"
    path = parsed.path.rstrip("/") or "/"
    normalized = urlunparse(
        (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, "")
    )
    return normalized


def is_same_domain(url: str, base_netloc: str) -> bool:
    """Vérifie que l'URL appartient au même domaine que l'URL de départ."""
    parsed = urlparse(url)
    return parsed.netloc == base_netloc


def extract_page_data(url: str, response: requests.Response, depth: int) -> dict:
    """Extrait les données SEO d'une page HTML."""
    data = {
        "URL": url,
        "Status Code": response.status_code,
        "Title": "",
        "Meta Description": "",
        "H1": "",
        "Depth": depth,
    }

    # Ne parser que le HTML
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return data

    soup = BeautifulSoup(response.text, "html.parser")

    # Title
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        data["Title"] = title_tag.string.strip()

    # Meta Description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        data["Meta Description"] = meta_desc["content"].strip()

    # H1
    h1_tag = soup.find("h1")
    if h1_tag:
        data["H1"] = h1_tag.get_text(strip=True)

    return data


def extract_internal_links(
    url: str, response: requests.Response, base_netloc: str
) -> list[str]:
    """Extrait tous les liens internes d'une page HTML."""
    links = []
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return links

    soup = BeautifulSoup(response.text, "html.parser")

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # Construire l'URL absolue
        absolute_url = urljoin(url, href)
        # Normaliser
        normalized = normalize_url(absolute_url)
        # Garder uniquement les liens HTTP(S) du même domaine
        parsed = urlparse(normalized)
        if parsed.scheme in ("http", "https") and is_same_domain(normalized, base_netloc):
            links.append(normalized)

    return links


# ──────────────────────────────────────────────
# Logique de crawl BFS
# ──────────────────────────────────────────────
def crawl(start_url: str, max_pages: int):
    """
    Crawl récursif en largeur (BFS).
    Retourne une liste de dictionnaires avec les données SEO de chaque page.
    """
    normalized_start = normalize_url(start_url)
    base_netloc = urlparse(normalized_start).netloc

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()  # (url, depth)
    queue.append((normalized_start, 0))
    visited.add(normalized_start)

    results: list[dict] = []

    # Éléments d'interface pour le suivi en temps réel
    progress_bar = st.progress(0)
    status_text = st.empty()
    counter_text = st.empty()

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    while queue and len(results) < max_pages:
        current_url, depth = queue.popleft()

        # Mise à jour de l'interface
        progress = len(results) / max_pages
        progress_bar.progress(progress)
        status_text.markdown(f"**Analyse de :** `{current_url}`")
        counter_text.markdown(
            f"Pages analysées : **{len(results)}** / {max_pages}"
        )

        try:
            response = session.get(current_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            page_data = extract_page_data(current_url, response, depth)
            results.append(page_data)

            # Extraire les liens internes et les ajouter à la queue
            internal_links = extract_internal_links(current_url, response, base_netloc)
            for link in internal_links:
                if link not in visited and len(visited) < max_pages:
                    visited.add(link)
                    queue.append((link, depth + 1))

        except requests.exceptions.Timeout:
            results.append(
                {
                    "URL": current_url,
                    "Status Code": "Timeout",
                    "Title": "",
                    "Meta Description": "",
                    "H1": "",
                    "Depth": depth,
                }
            )
        except requests.exceptions.ConnectionError:
            results.append(
                {
                    "URL": current_url,
                    "Status Code": "Erreur connexion",
                    "Title": "",
                    "Meta Description": "",
                    "H1": "",
                    "Depth": depth,
                }
            )
        except requests.exceptions.RequestException as e:
            results.append(
                {
                    "URL": current_url,
                    "Status Code": f"Erreur: {e}",
                    "Title": "",
                    "Meta Description": "",
                    "H1": "",
                    "Depth": depth,
                }
            )

    # Finaliser la barre de progression
    progress_bar.progress(1.0)
    status_text.markdown("**Crawl terminé !**")
    counter_text.markdown(f"Total : **{len(results)}** pages analysées.")

    return results


# ──────────────────────────────────────────────
# Lancement du crawl
# ──────────────────────────────────────────────
if crawl_button:
    if not start_url.strip():
        st.error("Veuillez entrer une URL de départ.")
    else:
        # Valider l'URL
        parsed = urlparse(start_url.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            st.error("L'URL doit commencer par http:// ou https:// et contenir un domaine valide.")
        else:
            with st.spinner("Initialisation du crawl…"):
                results = crawl(start_url.strip(), max_pages)

            if results:
                df = pd.DataFrame(results)
                st.subheader(f"Résultats — {len(df)} pages")
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Export CSV
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Télécharger en CSV",
                    data=csv,
                    file_name="crawl_seo.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            else:
                st.warning("Aucune page n'a pu être analysée.")
