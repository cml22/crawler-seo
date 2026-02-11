"""
Crawler SEO Récursif — Style Screaming Frog
Déployable sur Streamlit Cloud
"""

import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse
import time
import io

# ──────────────────────────────────────────────
# Configuration de la page
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Crawler SEO — charles-migaud.fr",
    page_icon="🕷️",
    layout="wide",
)

# ──────────────────────────────────────────────
# CSS Custom pour une meilleure interface
# ──────────────────────────────────────────────
st.markdown("""
<style>
    /* Header principal */
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
        text-align: center;
    }
    .main-header h1 {
        color: white !important;
        font-size: 2.2rem;
        margin-bottom: 0.3rem;
    }
    .main-header p {
        color: #a0aec0;
        font-size: 1rem;
    }

    /* Cartes métriques */
    .metric-card {
        background: #f8f9fa;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1a1a2e;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #718096;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-ok { color: #38a169 !important; }
    .metric-warn { color: #d69e2e !important; }
    .metric-error { color: #e53e3e !important; }

    /* Status badges dans le tableau */
    .status-ok { color: #38a169; font-weight: 600; }
    .status-redirect { color: #d69e2e; font-weight: 600; }
    .status-error { color: #e53e3e; font-weight: 600; }

    /* Bouton stop */
    .stButton > button[kind="secondary"] {
        border-color: #e53e3e;
        color: #e53e3e;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #f7fafc;
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🕷️ Crawler SEO</h1>
    <p>Analyse récursive de site web — Status codes, titres, meta descriptions, H1, profondeur</p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Session state — pour le bouton Stop
# ──────────────────────────────────────────────
if "crawl_running" not in st.session_state:
    st.session_state.crawl_running = False
if "crawl_stopped" not in st.session_state:
    st.session_state.crawl_stopped = False
if "results" not in st.session_state:
    st.session_state.results = None

# ──────────────────────────────────────────────
# Sidebar — Paramètres
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Paramètres")

    st.subheader("🔗 Source")
    crawl_mode = st.radio(
        "Mode de crawl",
        ["Crawl récursif (BFS)", "Depuis un Sitemap XML"],
        help="Choisissez entre un crawl récursif ou l'import d'un sitemap.",
    )

    if crawl_mode == "Crawl récursif (BFS)":
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
    else:
        sitemap_source = st.radio(
            "Source du sitemap",
            ["URL du sitemap", "Upload de fichier"],
        )
        if sitemap_source == "URL du sitemap":
            sitemap_url = st.text_input(
                "URL du sitemap.xml",
                value="https://charles-migaud.fr/sitemap.xml",
                help="L'URL complète du fichier sitemap.xml",
            )
            sitemap_file = None
        else:
            sitemap_url = None
            sitemap_file = st.file_uploader(
                "Uploader un sitemap.xml",
                type=["xml"],
                help="Glissez-déposez votre fichier sitemap.xml ici.",
            )
        max_pages = st.slider(
            "Nombre max de pages",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            help="Limite le nombre d'URLs du sitemap à analyser.",
        )

    st.divider()
    st.subheader("🎯 Options")
    delay = st.slider(
        "Délai entre requêtes (ms)",
        min_value=0,
        max_value=2000,
        value=200,
        step=100,
        help="Politesse : délai entre chaque requête pour ne pas surcharger le serveur.",
    )

    st.divider()
    crawl_button = st.button(
        "🚀 Lancer le crawl",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.crawl_running,
    )

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

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return data

    soup = BeautifulSoup(response.text, "html.parser")

    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        data["Title"] = title_tag.string.strip()

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        data["Meta Description"] = meta_desc["content"].strip()

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
        absolute_url = urljoin(url, href)
        normalized = normalize_url(absolute_url)
        parsed = urlparse(normalized)
        if parsed.scheme in ("http", "https") and is_same_domain(normalized, base_netloc):
            links.append(normalized)

    return links


def parse_sitemap(source_url: str = None, file_content: bytes = None) -> list[str]:
    """Parse un sitemap XML et retourne la liste des URLs."""
    urls = []
    try:
        if source_url:
            resp = requests.get(source_url, timeout=REQUEST_TIMEOUT,
                                headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            content = resp.content
        elif file_content:
            content = file_content
        else:
            return urls

        root = ET.fromstring(content)
        # Gérer les namespaces XML du sitemap
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Chercher les <url><loc> (sitemap standard)
        for url_elem in root.findall(".//sm:url/sm:loc", ns):
            if url_elem.text:
                urls.append(url_elem.text.strip())

        # Chercher les <sitemap><loc> (sitemap index)
        for sitemap_elem in root.findall(".//sm:sitemap/sm:loc", ns):
            if sitemap_elem.text:
                sub_urls = parse_sitemap(source_url=sitemap_elem.text.strip())
                urls.extend(sub_urls)

        # Fallback sans namespace
        if not urls:
            for loc in root.iter("loc"):
                if loc.text:
                    urls.append(loc.text.strip())

    except Exception as e:
        st.error(f"Erreur lors du parsing du sitemap : {e}")

    return urls


def make_error_row(url: str, error_msg: str, depth: int) -> dict:
    """Crée une ligne d'erreur pour le tableau de résultats."""
    return {
        "URL": url,
        "Status Code": error_msg,
        "Title": "",
        "Meta Description": "",
        "H1": "",
        "Depth": depth,
    }


# ──────────────────────────────────────────────
# Crawl BFS (récursif)
# ──────────────────────────────────────────────
def crawl_bfs(start_url: str, max_pages: int, delay_ms: int):
    """Crawl récursif en largeur (BFS) avec bouton stop."""
    normalized_start = normalize_url(start_url)
    base_netloc = urlparse(normalized_start).netloc

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()
    queue.append((normalized_start, 0))
    visited.add(normalized_start)

    results: list[dict] = []

    # Interface de suivi
    col_progress, col_stop = st.columns([4, 1])
    with col_progress:
        progress_bar = st.progress(0)
    with col_stop:
        stop_button = st.button("⛔ Stop", type="secondary", use_container_width=True)

    status_text = st.empty()
    counter_text = st.empty()
    live_table = st.empty()

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    stopped = False

    while queue and len(results) < max_pages:
        # Vérifier si l'utilisateur a cliqué Stop
        if stop_button:
            stopped = True
            break

        current_url, depth = queue.popleft()

        progress = len(results) / max_pages
        progress_bar.progress(min(progress, 1.0))
        status_text.markdown(f"🔍 **Analyse de :** `{current_url}`")
        counter_text.markdown(
            f"📊 Pages analysées : **{len(results)}** / {max_pages}"
        )

        try:
            response = session.get(current_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            page_data = extract_page_data(current_url, response, depth)
            results.append(page_data)

            internal_links = extract_internal_links(current_url, response, base_netloc)
            for link in internal_links:
                if link not in visited and len(visited) < max_pages:
                    visited.add(link)
                    queue.append((link, depth + 1))

        except requests.exceptions.Timeout:
            results.append(make_error_row(current_url, "Timeout", depth))
        except requests.exceptions.ConnectionError:
            results.append(make_error_row(current_url, "Erreur connexion", depth))
        except requests.exceptions.RequestException as e:
            results.append(make_error_row(current_url, f"Erreur: {e}", depth))

        # Aperçu en direct toutes les 5 pages
        if len(results) % 5 == 0 and results:
            live_table.dataframe(
                pd.DataFrame(results),
                use_container_width=True,
                hide_index=True,
            )

        # Délai de politesse
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

    # Finalisation
    progress_bar.progress(1.0)
    if stopped:
        status_text.markdown("⛔ **Crawl interrompu par l'utilisateur.**")
    else:
        status_text.markdown("✅ **Crawl terminé !**")
    counter_text.markdown(f"📊 Total : **{len(results)}** pages analysées.")
    live_table.empty()

    return results


# ──────────────────────────────────────────────
# Crawl depuis Sitemap
# ──────────────────────────────────────────────
def crawl_sitemap(urls: list[str], max_pages: int, delay_ms: int):
    """Analyse les URLs extraites d'un sitemap."""
    urls = urls[:max_pages]
    results: list[dict] = []

    col_progress, col_stop = st.columns([4, 1])
    with col_progress:
        progress_bar = st.progress(0)
    with col_stop:
        stop_button = st.button("⛔ Stop", type="secondary", use_container_width=True)

    status_text = st.empty()
    counter_text = st.empty()
    live_table = st.empty()

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    stopped = False

    for i, url in enumerate(urls):
        if stop_button:
            stopped = True
            break

        progress = i / len(urls)
        progress_bar.progress(min(progress, 1.0))
        status_text.markdown(f"🔍 **Analyse de :** `{url}`")
        counter_text.markdown(
            f"📊 Pages analysées : **{i}** / {len(urls)}"
        )

        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            page_data = extract_page_data(url, response, depth=0)
            results.append(page_data)
        except requests.exceptions.Timeout:
            results.append(make_error_row(url, "Timeout", 0))
        except requests.exceptions.ConnectionError:
            results.append(make_error_row(url, "Erreur connexion", 0))
        except requests.exceptions.RequestException as e:
            results.append(make_error_row(url, f"Erreur: {e}", 0))

        if len(results) % 5 == 0 and results:
            live_table.dataframe(
                pd.DataFrame(results),
                use_container_width=True,
                hide_index=True,
            )

        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

    progress_bar.progress(1.0)
    if stopped:
        status_text.markdown("⛔ **Crawl interrompu par l'utilisateur.**")
    else:
        status_text.markdown("✅ **Crawl terminé !**")
    counter_text.markdown(f"📊 Total : **{len(results)}** pages analysées.")
    live_table.empty()

    return results


# ──────────────────────────────────────────────
# Affichage des résultats
# ──────────────────────────────────────────────
def display_results(results: list[dict]):
    """Affiche les résultats avec métriques et tableau."""
    df = pd.DataFrame(results)

    # ── Métriques en haut ──
    st.markdown("---")
    total = len(df)
    status_codes = df["Status Code"]

    ok_count = status_codes.apply(lambda x: isinstance(x, int) and 200 <= x < 300).sum()
    redirect_count = status_codes.apply(lambda x: isinstance(x, int) and 300 <= x < 400).sum()
    client_error = status_codes.apply(lambda x: isinstance(x, int) and 400 <= x < 500).sum()
    server_error = status_codes.apply(lambda x: isinstance(x, int) and x >= 500).sum()
    other_error = total - ok_count - redirect_count - client_error - server_error

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total}</div>
            <div class="metric-label">Pages totales</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value metric-ok">{ok_count}</div>
            <div class="metric-label">2xx OK</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value metric-warn">{redirect_count}</div>
            <div class="metric-label">3xx Redirections</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value metric-error">{client_error}</div>
            <div class="metric-label">4xx Erreurs client</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value metric-error">{server_error + other_error}</div>
            <div class="metric-label">5xx / Autres erreurs</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Onglets : Tableau complet / Erreurs / Stats ──
    tab_all, tab_errors, tab_stats = st.tabs(["📋 Toutes les pages", "⚠️ Erreurs uniquement", "📊 Statistiques"])

    with tab_all:
        st.dataframe(df, use_container_width=True, hide_index=True, height=500)

    with tab_errors:
        errors_df = df[
            df["Status Code"].apply(
                lambda x: not (isinstance(x, int) and 200 <= x < 300)
            )
        ]
        if errors_df.empty:
            st.success("Aucune erreur trouvée ! Toutes les pages retournent un code 2xx.")
        else:
            st.warning(f"{len(errors_df)} page(s) en erreur ou redirection.")
            st.dataframe(errors_df, use_container_width=True, hide_index=True)

    with tab_stats:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Répartition des Status Codes**")
            status_counts = df["Status Code"].value_counts().reset_index()
            status_counts.columns = ["Status Code", "Nombre"]
            st.bar_chart(status_counts, x="Status Code", y="Nombre")

        with col_b:
            st.markdown("**Pages par profondeur (Depth)**")
            if "Depth" in df.columns:
                depth_counts = df["Depth"].value_counts().sort_index().reset_index()
                depth_counts.columns = ["Profondeur", "Nombre"]
                st.bar_chart(depth_counts, x="Profondeur", y="Nombre")

        # Titres manquants / Meta descriptions manquantes
        st.markdown("---")
        col_c, col_d = st.columns(2)
        with col_c:
            missing_titles = df[df["Title"] == ""]
            st.metric("Titres manquants", len(missing_titles))
            if not missing_titles.empty:
                st.dataframe(
                    missing_titles[["URL", "Status Code"]],
                    use_container_width=True,
                    hide_index=True,
                )
        with col_d:
            missing_meta = df[df["Meta Description"] == ""]
            st.metric("Meta descriptions manquantes", len(missing_meta))
            if not missing_meta.empty:
                st.dataframe(
                    missing_meta[["URL", "Status Code"]],
                    use_container_width=True,
                    hide_index=True,
                )

    # ── Export CSV ──
    st.markdown("---")
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Télécharger les résultats en CSV",
        data=csv,
        file_name="crawl_seo.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ──────────────────────────────────────────────
# Lancement du crawl
# ──────────────────────────────────────────────
if crawl_button:
    if crawl_mode == "Crawl récursif (BFS)":
        if not start_url.strip():
            st.error("Veuillez entrer une URL de départ.")
        else:
            parsed = urlparse(start_url.strip())
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                st.error("L'URL doit commencer par http:// ou https:// et contenir un domaine valide.")
            else:
                st.session_state.crawl_running = True
                results = crawl_bfs(start_url.strip(), max_pages, delay)
                st.session_state.crawl_running = False
                st.session_state.results = results

    else:  # Mode Sitemap
        sitemap_urls = []
        if sitemap_source == "URL du sitemap" and sitemap_url:
            with st.spinner("Téléchargement et parsing du sitemap..."):
                sitemap_urls = parse_sitemap(source_url=sitemap_url.strip())
        elif sitemap_source == "Upload de fichier" and sitemap_file:
            with st.spinner("Parsing du sitemap uploadé..."):
                sitemap_urls = parse_sitemap(file_content=sitemap_file.read())

        if sitemap_urls:
            st.info(f"📄 **{len(sitemap_urls)}** URLs trouvées dans le sitemap.")
            st.session_state.crawl_running = True
            results = crawl_sitemap(sitemap_urls, max_pages, delay)
            st.session_state.crawl_running = False
            st.session_state.results = results
        else:
            st.error("Aucune URL trouvée dans le sitemap. Vérifiez la source.")

# Afficher les résultats (persistants via session_state)
if st.session_state.results:
    display_results(st.session_state.results)
