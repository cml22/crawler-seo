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

from seo_checks import run_audit, ISSUE, WARNING, OPPORTUNITY, HIGH, MEDIUM, LOW

# ──────────────────────────────────────────────
# Configuration de la page
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Crawler SEO — charles-migaud.fr",
    page_icon="🕷️",
    layout="wide",
)

# ──────────────────────────────────────────────
# CSS Custom
# ──────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
        text-align: center;
    }
    .main-header h1 { color: white !important; font-size: 2.2rem; margin-bottom: 0.3rem; }
    .main-header p { color: #a0aec0; font-size: 1rem; }

    .metric-card {
        background: #f8f9fa;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
        transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    .metric-value { font-size: 2rem; font-weight: 700; color: #1a1a2e; }
    .metric-label { font-size: 0.85rem; color: #718096; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-ok { color: #38a169 !important; }
    .metric-warn { color: #d69e2e !important; }
    .metric-error { color: #e53e3e !important; }

    /* Issue badges */
    .badge-issue { background: #fed7d7; color: #c53030; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
    .badge-warning { background: #fefcbf; color: #975a16; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
    .badge-opportunity { background: #c6f6d5; color: #276749; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
    .badge-high { background: #c53030; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .badge-medium { background: #d69e2e; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .badge-low { background: #718096; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }

    section[data-testid="stSidebar"] { background: #f7fafc; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 10px 20px; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🕷️ Crawler SEO</h1>
    <p>Analyse récursive de site web — Issues, Warnings &amp; Opportunities comme Screaming Frog</p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────
if "crawl_running" not in st.session_state:
    st.session_state.crawl_running = False
if "results" not in st.session_state:
    st.session_state.results = None
if "raw_pages" not in st.session_state:
    st.session_state.raw_pages = None
if "seo_issues" not in st.session_state:
    st.session_state.seo_issues = None

# ──────────────────────────────────────────────
# Sidebar — Paramètres
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Paramètres")

    st.subheader("🔗 Source")
    crawl_mode = st.radio(
        "Mode de crawl",
        ["Crawl récursif (BFS)", "Depuis un Sitemap XML"],
    )

    if crawl_mode == "Crawl récursif (BFS)":
        start_url = st.text_input("URL de départ", value="https://charles-migaud.fr")
        max_pages = st.slider("Nombre max de pages", 10, 500, 50, 10)
    else:
        sitemap_source = st.radio("Source du sitemap", ["URL du sitemap", "Upload de fichier"])
        if sitemap_source == "URL du sitemap":
            sitemap_url = st.text_input("URL du sitemap.xml", value="https://charles-migaud.fr/sitemap.xml")
            sitemap_file = None
        else:
            sitemap_url = None
            sitemap_file = st.file_uploader("Uploader un sitemap.xml", type=["xml"])
        max_pages = st.slider("Nombre max de pages", 10, 500, 100, 10)

    st.divider()
    st.subheader("🎯 Options")
    delay = st.slider("Délai entre requêtes (ms)", 0, 2000, 200, 100)

    st.divider()
    crawl_button = st.button(
        "🚀 Lancer le crawl", type="primary", use_container_width=True,
        disabled=st.session_state.crawl_running,
    )

# ──────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────
USER_AGENT = "Mozilla/5.0 (compatible; CrawlerSEO/1.0; +https://crawler.charles-migaud.fr)"
REQUEST_TIMEOUT = 10


# ──────────────────────────────────────────────
# Fonctions utilitaires
# ──────────────────────────────────────────────
def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))


def is_same_domain(url: str, base_netloc: str) -> bool:
    return urlparse(url).netloc == base_netloc


def extract_rich_page_data(url: str, response: requests.Response, depth: int) -> dict:
    """Extraction enrichie : toutes les données nécessaires pour l'audit SEO."""
    data = {
        "URL": url,
        "status_code": response.status_code if isinstance(response.status_code, int) else str(response.status_code),
        "title": "",
        "title_count": 0,
        "meta_description": "",
        "meta_description_count": 0,
        "h1": "",
        "h1_count": 0,
        "h2_list": [],
        "images": [],
        "canonicals": [],
        "meta_robots": "",
        "x_robots_tag": "",
        "response_headers": {},
        "mixed_content": [],
        "internal_outlinks": 0,
        "external_outlinks": 0,
        "nofollow_outlinks": 0,
        "empty_anchor_links": 0,
        "word_count": 0,
        "text_content": "",
        "has_head_tag": True,
        "has_body_tag": True,
        "head_count": 1,
        "body_count": 1,
        "html_size_bytes": len(response.content) if response.content else 0,
        "depth": depth,
    }

    # Headers
    headers_lower = {k.lower(): v for k, v in response.headers.items()}
    data["response_headers"] = headers_lower
    data["x_robots_tag"] = headers_lower.get("x-robots-tag", "")

    content_type = headers_lower.get("content-type", "")
    if "text/html" not in content_type:
        return data

    soup = BeautifulSoup(response.text, "html.parser")
    base_netloc = urlparse(url).netloc
    is_https = urlparse(url).scheme == "https"

    # Head / Body validation
    head_tags = soup.find_all("head")
    body_tags = soup.find_all("body")
    data["has_head_tag"] = len(head_tags) > 0
    data["has_body_tag"] = len(body_tags) > 0
    data["head_count"] = len(head_tags)
    data["body_count"] = len(body_tags)

    # Title
    titles = soup.find_all("title")
    data["title_count"] = len(titles)
    if titles and titles[0].string:
        data["title"] = titles[0].string.strip()

    # Meta Description
    meta_descs = soup.find_all("meta", attrs={"name": "description"})
    data["meta_description_count"] = len(meta_descs)
    if meta_descs and meta_descs[0].get("content"):
        data["meta_description"] = meta_descs[0]["content"].strip()

    # Meta Robots
    meta_robots = soup.find("meta", attrs={"name": "robots"})
    if meta_robots and meta_robots.get("content"):
        data["meta_robots"] = meta_robots["content"].strip()

    # H1
    h1_tags = soup.find_all("h1")
    data["h1_count"] = len(h1_tags)
    if h1_tags:
        data["h1"] = h1_tags[0].get_text(strip=True)

    # H2
    h2_tags = soup.find_all("h2")
    data["h2_list"] = [h2.get_text(strip=True) for h2 in h2_tags]

    # Canonical
    canonical_tags = soup.find_all("link", attrs={"rel": "canonical"})
    data["canonicals"] = [tag.get("href", "") for tag in canonical_tags if tag.get("href")]

    # Images
    img_tags = soup.find_all("img")
    images_data = []
    for img in img_tags:
        img_info = {
            "src": img.get("src", ""),
            "alt": img.get("alt"),  # None si absent, "" si vide
        }
        images_data.append(img_info)
    data["images"] = images_data

    # Mixed content (HTTP resources on HTTPS page)
    if is_https:
        mixed = []
        for tag in soup.find_all(["img", "script", "link", "iframe"]):
            src = tag.get("src") or tag.get("href") or ""
            if src.startswith("http://"):
                mixed.append(src)
        data["mixed_content"] = mixed

    # Links analysis
    internal_out = 0
    external_out = 0
    nofollow_out = 0
    empty_anchor = 0
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        abs_url = urljoin(url, href)
        parsed_link = urlparse(abs_url)

        if parsed_link.scheme not in ("http", "https"):
            continue

        rel = a_tag.get("rel", [])
        if isinstance(rel, list):
            rel = " ".join(rel)

        if is_same_domain(abs_url, base_netloc):
            internal_out += 1
            if "nofollow" in rel.lower():
                nofollow_out += 1
            anchor_text = a_tag.get_text(strip=True)
            if not anchor_text:
                empty_anchor += 1
        else:
            external_out += 1

    data["internal_outlinks"] = internal_out
    data["external_outlinks"] = external_out
    data["nofollow_outlinks"] = nofollow_out
    data["empty_anchor_links"] = empty_anchor

    # Content / Word count
    text = soup.get_text(separator=" ", strip=True)
    data["text_content"] = text[:5000]  # Limiter pour la mémoire
    data["word_count"] = len(text.split())

    return data


def extract_internal_links(url: str, response: requests.Response, base_netloc: str) -> list[str]:
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
    urls = []
    try:
        if source_url:
            resp = requests.get(source_url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            content = resp.content
        elif file_content:
            content = file_content
        else:
            return urls

        root = ET.fromstring(content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for url_elem in root.findall(".//sm:url/sm:loc", ns):
            if url_elem.text:
                urls.append(url_elem.text.strip())
        for sitemap_elem in root.findall(".//sm:sitemap/sm:loc", ns):
            if sitemap_elem.text:
                urls.extend(parse_sitemap(source_url=sitemap_elem.text.strip()))
        if not urls:
            for loc in root.iter("loc"):
                if loc.text:
                    urls.append(loc.text.strip())
    except Exception as e:
        st.error(f"Erreur lors du parsing du sitemap : {e}")
    return urls


def make_error_page(url: str, error_msg: str, depth: int) -> dict:
    return {
        "URL": url,
        "status_code": error_msg,
        "title": "", "title_count": 0,
        "meta_description": "", "meta_description_count": 0,
        "h1": "", "h1_count": 0, "h2_list": [],
        "images": [], "canonicals": [],
        "meta_robots": "", "x_robots_tag": "",
        "response_headers": {}, "mixed_content": [],
        "internal_outlinks": 0, "external_outlinks": 0,
        "nofollow_outlinks": 0, "empty_anchor_links": 0,
        "word_count": 0, "text_content": "",
        "has_head_tag": True, "has_body_tag": True,
        "head_count": 1, "body_count": 1,
        "html_size_bytes": 0, "depth": depth,
    }


def page_to_display_row(page: dict) -> dict:
    """Convertit les données enrichies en ligne pour le tableau d'affichage."""
    return {
        "URL": page["URL"],
        "Status Code": page["status_code"],
        "Title": page["title"],
        "Meta Description": page["meta_description"],
        "H1": page["h1"],
        "H2 Count": len(page.get("h2_list", [])),
        "Word Count": page.get("word_count", 0),
        "Images": len(page.get("images", [])),
        "Internal Links": page.get("internal_outlinks", 0),
        "External Links": page.get("external_outlinks", 0),
        "Canonical": ", ".join(page.get("canonicals", [])) or "—",
        "Depth": page.get("depth", 0),
    }


# ──────────────────────────────────────────────
# Crawl BFS
# ──────────────────────────────────────────────
def crawl_bfs(start_url: str, max_pages: int, delay_ms: int):
    normalized_start = normalize_url(start_url)
    base_netloc = urlparse(normalized_start).netloc

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()
    queue.append((normalized_start, 0))
    visited.add(normalized_start)

    raw_pages: list[dict] = []

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

    while queue and len(raw_pages) < max_pages:
        if stop_button:
            stopped = True
            break

        current_url, depth = queue.popleft()
        progress_bar.progress(min(len(raw_pages) / max_pages, 1.0))
        status_text.markdown(f"🔍 **Analyse de :** `{current_url}`")
        counter_text.markdown(f"📊 Pages analysées : **{len(raw_pages)}** / {max_pages}")

        try:
            response = session.get(current_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            page_data = extract_rich_page_data(current_url, response, depth)
            raw_pages.append(page_data)

            internal_links = extract_internal_links(current_url, response, base_netloc)
            for link in internal_links:
                if link not in visited and len(visited) < max_pages:
                    visited.add(link)
                    queue.append((link, depth + 1))

        except requests.exceptions.Timeout:
            raw_pages.append(make_error_page(current_url, "Timeout", depth))
        except requests.exceptions.ConnectionError:
            raw_pages.append(make_error_page(current_url, "Erreur connexion", depth))
        except requests.exceptions.RequestException as e:
            raw_pages.append(make_error_page(current_url, f"Erreur: {e}", depth))

        if len(raw_pages) % 5 == 0 and raw_pages:
            display_rows = [page_to_display_row(p) for p in raw_pages]
            live_table.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

    progress_bar.progress(1.0)
    status_text.markdown("⛔ **Crawl interrompu.**" if stopped else "✅ **Crawl terminé !**")
    counter_text.markdown(f"📊 Total : **{len(raw_pages)}** pages analysées.")
    live_table.empty()

    return raw_pages


# ──────────────────────────────────────────────
# Crawl Sitemap
# ──────────────────────────────────────────────
def crawl_sitemap(urls: list[str], max_pages: int, delay_ms: int):
    urls = urls[:max_pages]
    raw_pages: list[dict] = []

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

        progress_bar.progress(min(i / len(urls), 1.0))
        status_text.markdown(f"🔍 **Analyse de :** `{url}`")
        counter_text.markdown(f"📊 Pages analysées : **{i}** / {len(urls)}")

        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            raw_pages.append(extract_rich_page_data(url, response, depth=0))
        except requests.exceptions.Timeout:
            raw_pages.append(make_error_page(url, "Timeout", 0))
        except requests.exceptions.ConnectionError:
            raw_pages.append(make_error_page(url, "Erreur connexion", 0))
        except requests.exceptions.RequestException as e:
            raw_pages.append(make_error_page(url, f"Erreur: {e}", 0))

        if len(raw_pages) % 5 == 0 and raw_pages:
            display_rows = [page_to_display_row(p) for p in raw_pages]
            live_table.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

    progress_bar.progress(1.0)
    status_text.markdown("⛔ **Crawl interrompu.**" if stopped else "✅ **Crawl terminé !**")
    counter_text.markdown(f"📊 Total : **{len(raw_pages)}** pages analysées.")
    live_table.empty()

    return raw_pages


# ──────────────────────────────────────────────
# Affichage des résultats
# ──────────────────────────────────────────────
def display_results(raw_pages: list[dict], seo_issues: list[dict]):
    display_rows = [page_to_display_row(p) for p in raw_pages]
    df = pd.DataFrame(display_rows)
    issues_df = pd.DataFrame(seo_issues) if seo_issues else pd.DataFrame()

    # ── Métriques globales ──
    st.markdown("---")
    total = len(df)
    status_codes = df["Status Code"]
    ok_count = status_codes.apply(lambda x: isinstance(x, int) and 200 <= x < 300).sum()
    redirect_count = status_codes.apply(lambda x: isinstance(x, int) and 300 <= x < 400).sum()
    client_error = status_codes.apply(lambda x: isinstance(x, int) and 400 <= x < 500).sum()
    server_error = status_codes.apply(lambda x: isinstance(x, int) and x >= 500).sum()
    other_error = total - ok_count - redirect_count - client_error - server_error

    issue_count = len(issues_df[issues_df["Type"] == ISSUE]) if not issues_df.empty else 0
    warning_count = len(issues_df[issues_df["Type"] == WARNING]) if not issues_df.empty else 0
    opp_count = len(issues_df[issues_df["Type"] == OPPORTUNITY]) if not issues_df.empty else 0

    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">Pages</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-value metric-ok">{ok_count}</div><div class="metric-label">2xx OK</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-value metric-warn">{redirect_count}</div><div class="metric-label">3xx</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-value metric-error">{client_error}</div><div class="metric-label">4xx</div></div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div class="metric-card"><div class="metric-value metric-error">{server_error + other_error}</div><div class="metric-label">5xx/Err</div></div>', unsafe_allow_html=True)
    with c6:
        st.markdown(f'<div class="metric-card"><div class="metric-value metric-error">{issue_count}</div><div class="metric-label">Issues</div></div>', unsafe_allow_html=True)
    with c7:
        st.markdown(f'<div class="metric-card"><div class="metric-value metric-warn">{warning_count}</div><div class="metric-label">Warnings</div></div>', unsafe_allow_html=True)
    with c8:
        st.markdown(f'<div class="metric-card"><div class="metric-value metric-ok">{opp_count}</div><div class="metric-label">Opportunities</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Onglets ──
    tab_issues, tab_all, tab_errors, tab_stats = st.tabs([
        "🔍 Audit SEO (Issues)",
        "📋 Toutes les pages",
        "⚠️ Erreurs HTTP",
        "📊 Statistiques",
    ])

    # ── Onglet Audit SEO ──
    with tab_issues:
        if issues_df.empty:
            st.success("Aucun problème SEO détecté. Félicitations !")
        else:
            st.markdown("### Filtres")
            filter_col1, filter_col2, filter_col3 = st.columns(3)

            with filter_col1:
                type_filter = st.multiselect(
                    "Type",
                    [ISSUE, WARNING, OPPORTUNITY],
                    default=[ISSUE, WARNING, OPPORTUNITY],
                )
            with filter_col2:
                priority_filter = st.multiselect(
                    "Priorité",
                    [HIGH, MEDIUM, LOW],
                    default=[HIGH, MEDIUM, LOW],
                )
            with filter_col3:
                categories = sorted(issues_df["Category"].unique().tolist())
                cat_filter = st.multiselect(
                    "Catégorie",
                    categories,
                    default=categories,
                )

            filtered = issues_df[
                (issues_df["Type"].isin(type_filter))
                & (issues_df["Priority"].isin(priority_filter))
                & (issues_df["Category"].isin(cat_filter))
            ]

            # Résumé par catégorie
            st.markdown("### Résumé par catégorie")
            summary = (
                filtered.groupby(["Category", "Type"])
                .size()
                .reset_index(name="Count")
                .sort_values(["Category", "Type"])
            )
            if not summary.empty:
                # Pivot pour afficher Issues / Warnings / Opportunities en colonnes
                pivot = summary.pivot_table(
                    index="Category", columns="Type", values="Count", fill_value=0, aggfunc="sum"
                ).reset_index()
                # Réordonner les colonnes
                col_order = ["Category"]
                for t in [ISSUE, WARNING, OPPORTUNITY]:
                    if t in pivot.columns:
                        col_order.append(t)
                pivot = pivot[col_order]
                pivot["Total"] = pivot.select_dtypes(include="number").sum(axis=1)
                pivot = pivot.sort_values("Total", ascending=False)
                st.dataframe(pivot, use_container_width=True, hide_index=True)

            # Liste détaillée
            st.markdown("### Détail des problèmes")
            st.markdown(f"**{len(filtered)}** problème(s) trouvé(s)")

            # Trier : High d'abord, puis Issues, puis Warnings, puis Opportunities
            priority_order = {HIGH: 0, MEDIUM: 1, LOW: 2}
            type_order = {ISSUE: 0, WARNING: 1, OPPORTUNITY: 2}
            filtered = filtered.copy()
            filtered["_p_order"] = filtered["Priority"].map(priority_order)
            filtered["_t_order"] = filtered["Type"].map(type_order)
            filtered = filtered.sort_values(["_p_order", "_t_order", "Category"])
            filtered = filtered.drop(columns=["_p_order", "_t_order"])

            st.dataframe(
                filtered,
                use_container_width=True,
                hide_index=True,
                height=600,
                column_config={
                    "URL": st.column_config.LinkColumn("URL", width="medium"),
                    "Guidance": st.column_config.TextColumn("Guidance", width="large"),
                },
            )

            # Export issues CSV
            issues_csv = filtered.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Télécharger l'audit SEO en CSV",
                data=issues_csv,
                file_name="audit_seo_issues.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # ── Onglet Toutes les pages ──
    with tab_all:
        st.dataframe(df, use_container_width=True, hide_index=True, height=500)

    # ── Onglet Erreurs HTTP ──
    with tab_errors:
        errors_df = df[df["Status Code"].apply(lambda x: not (isinstance(x, int) and 200 <= x < 300))]
        if errors_df.empty:
            st.success("Aucune erreur HTTP. Toutes les pages retournent un code 2xx.")
        else:
            st.warning(f"{len(errors_df)} page(s) en erreur ou redirection.")
            st.dataframe(errors_df, use_container_width=True, hide_index=True)

    # ── Onglet Statistiques ──
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

        st.markdown("---")
        col_c, col_d, col_e = st.columns(3)
        with col_c:
            missing_titles = df[df["Title"] == ""]
            st.metric("Titres manquants", len(missing_titles))
        with col_d:
            missing_meta = df[df["Meta Description"] == ""]
            st.metric("Meta desc. manquantes", len(missing_meta))
        with col_e:
            missing_h1 = df[df["H1"] == ""]
            st.metric("H1 manquants", len(missing_h1))

        st.markdown("---")
        col_f, col_g = st.columns(2)
        with col_f:
            st.markdown("**Contenu : nombre de mots par page**")
            word_data = pd.DataFrame([{"URL": p["URL"], "Mots": p["word_count"]} for p in raw_pages])
            word_data = word_data.sort_values("Mots", ascending=True)
            st.bar_chart(word_data.set_index("URL")["Mots"])
        with col_g:
            st.markdown("**Images par page**")
            img_data = pd.DataFrame([{"URL": p["URL"], "Images": len(p.get("images", []))} for p in raw_pages])
            img_data = img_data.sort_values("Images", ascending=False).head(20)
            st.bar_chart(img_data.set_index("URL")["Images"])

    # ── Export global CSV ──
    st.markdown("---")
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Télécharger toutes les pages en CSV",
        data=csv, file_name="crawl_seo.csv", mime="text/csv",
        use_container_width=True,
    )


# ──────────────────────────────────────────────
# Lancement
# ──────────────────────────────────────────────
if crawl_button:
    if crawl_mode == "Crawl récursif (BFS)":
        if not start_url.strip():
            st.error("Veuillez entrer une URL de départ.")
        else:
            parsed = urlparse(start_url.strip())
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                st.error("L'URL doit commencer par http:// ou https://.")
            else:
                st.session_state.crawl_running = True
                raw_pages = crawl_bfs(start_url.strip(), max_pages, delay)
                st.session_state.crawl_running = False

                with st.spinner("Analyse SEO en cours..."):
                    seo_issues = run_audit(raw_pages)

                st.session_state.raw_pages = raw_pages
                st.session_state.seo_issues = seo_issues
    else:
        sitemap_urls = []
        if sitemap_source == "URL du sitemap" and sitemap_url:
            with st.spinner("Parsing du sitemap..."):
                sitemap_urls = parse_sitemap(source_url=sitemap_url.strip())
        elif sitemap_source == "Upload de fichier" and sitemap_file:
            with st.spinner("Parsing du sitemap..."):
                sitemap_urls = parse_sitemap(file_content=sitemap_file.read())

        if sitemap_urls:
            st.info(f"📄 **{len(sitemap_urls)}** URLs trouvées dans le sitemap.")
            st.session_state.crawl_running = True
            raw_pages = crawl_sitemap(sitemap_urls, max_pages, delay)
            st.session_state.crawl_running = False

            with st.spinner("Analyse SEO en cours..."):
                seo_issues = run_audit(raw_pages)

            st.session_state.raw_pages = raw_pages
            st.session_state.seo_issues = seo_issues
        else:
            st.error("Aucune URL trouvée dans le sitemap.")

# Afficher les résultats persistants
if st.session_state.raw_pages and st.session_state.seo_issues is not None:
    display_results(st.session_state.raw_pages, st.session_state.seo_issues)
