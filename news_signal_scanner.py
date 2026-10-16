#!/usr/bin/env python3
"""
News Signal Scanner

Scans worldwide news for breaking stories in your niche (visa/tax policy
changes, crackdowns, new rules) so you can cover them before competitors do.

Design goals (see conversation context / config for the "why"):
- Worldwide coverage: queries every country in TOPIC_CATEGORIES via Google
  News' global English edition, plus a curated set of high-value markets
  via their *local-language* edition (local press often breaks a policy
  story days before it hits English-language aggregators).
- Low noise: never searches on a bare country/topic name. Every query
  requires a niche term (visa/tax/residency/citizenship) AND a policy
  signal word (crackdown, reform, ban, new rule, deadline...) together -
  this is what filters out generic travel/lifestyle content.
- Interest meter: stories are clustered (same story covered by multiple
  outlets), then scored on source diversity, recency, niche specificity,
  policy-signal strength, and whether any competitor has already covered
  it (first-mover bonus). Highest score = pick that one first.

Data source: Google News RSS search (free, no API key, no auth).

Usage:
    python news_signal_scanner.py                      # worldwide scan, default settings
    python news_signal_scanner.py --local-editions      # also query local-language editions
    python news_signal_scanner.py --countries "portugal,spain,indonesia,uae"
    python news_signal_scanner.py --lookback-hours 48 --min-score 30
"""

import argparse
import json
import os
import re
import sqlite3
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

from google_search_analyzer import TOPIC_CATEGORIES, load_niche_config

DEFAULT_OUTPUT_DIR = "./output"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
REQUEST_TIMEOUT = 15
REQUEST_SLEEP = 1.0  # be polite between requests

# Policy-change signal words. A query must combine one of these with a
# niche term - bare country/topic queries return near-infinite noise
# (travel vlogs, lifestyle content, unrelated local news).
POLICY_SIGNAL_WORDS = [
    "crackdown", "reform", "bill", "ban", "suspend", "suspended",
    "new rule", "new rules", "requirement", "requirements", "deadline",
    "increase", "increases", "change", "changes", "tighten", "tightens",
    "restrict", "restricts", "restriction", "warns", "warning",
    "penalty", "penalties", "fine", "fines", "investigation", "lawsuit",
    "revoked", "revoke", "scrap", "scraps", "overhaul", "cap", "quota",
]

NICHE_TERMS = ["visa", "tax", "residency", "citizenship", "passport"]

# Curated high-value markets where local-language coverage often precedes
# English-language pickup. (hl, gl, ceid) per Google News edition params.
# Kept small and explicit rather than all 47 countries - most countries'
# English-language coverage is sufficient and running every country in
# every local language would blow past reasonable request volume.
LOCAL_EDITIONS = {
    "portugal": ("pt-PT", "PT", "PT:pt-150"),
    "spain": ("es", "ES", "ES:es"),
    "indonesia": ("id", "ID", "ID:id"),
    "thailand": ("th", "TH", "TH:th"),
    "uae": ("ar", "AE", "AE:ar"),
    "malaysia": ("ms", "MY", "MY:ms"),
    "mexico": ("es-419", "MX", "MX:es-419"),
    "italy": ("it", "IT", "IT:it"),
    "germany": ("de", "DE", "DE:de"),
    "france": ("fr", "FR", "FR:fr"),
    "greece": ("el", "GR", "GR:el"),
    "turkey": ("tr", "TR", "TR:tr"),
    "vietnam": ("vi", "VN", "VN:vi"),
    "philippines": ("en-PH", "PH", "PH:en"),
    "panama": ("es-419", "PA", "PA:es-419"),
    "colombia": ("es-419", "CO", "CO:es-419"),
    "brazil": ("pt-BR", "BR", "BR:pt-BR"),
    # Expanded to keep pace with the broader worldwide country list -
    # major expat/tax/residency-relevant markets across every region.
    "japan": ("ja", "JP", "JP:ja"),
    "south korea": ("ko", "KR", "KR:ko"),
    "china": ("zh-CN", "CN", "CN:zh-Hans"),
    "taiwan": ("zh-TW", "TW", "TW:zh-TW"),
    "russia": ("ru", "RU", "RU:ru"),
    "poland": ("pl", "PL", "PL:pl"),
    "netherlands": ("nl", "NL", "NL:nl"),
    "sweden": ("sv", "SE", "SE:sv"),
    "norway": ("no", "NO", "NO:no"),
    "denmark": ("da", "DK", "DK:da"),
    "finland": ("fi", "FI", "FI:fi"),
    "czech republic": ("cs", "CZ", "CZ:cs"),
    "hungary": ("hu", "HU", "HU:hu"),
    "croatia": ("hr", "HR", "HR:hr"),
    "serbia": ("sr", "RS", "RS:sr"),
    "ukraine": ("uk", "UA", "UA:uk"),
    "israel": ("he", "IL", "IL:he"),
    "saudi arabia": ("ar", "SA", "SA:ar"),
    "egypt": ("ar", "EG", "EG:ar"),
    "morocco": ("fr", "MA", "MA:fr"),
    "argentina": ("es-419", "AR", "AR:es-419"),
    "chile": ("es-419", "CL", "CL:es-419"),
    "peru": ("es-419", "PE", "PE:es-419"),
    "ecuador": ("es-419", "EC", "EC:es-419"),
    "costa rica": ("es-419", "CR", "CR:es-419"),
    "uruguay": ("es-419", "UY", "UY:es-419"),
    "india": ("en-IN", "IN", "IN:en"),
    "south africa": ("en-ZA", "ZA", "ZA:en-ZA"),
    "australia": ("en-AU", "AU", "AU:en-AU"),
    "new zealand": ("en-NZ", "NZ", "NZ:en-NZ"),
    "canada": ("en-CA", "CA", "CA:en-CA"),
    "switzerland": ("de", "CH", "CH:de"),
    "austria": ("de", "AT", "AT:de"),
    "romania": ("ro", "RO", "RO:ro"),
    "bulgaria": ("bg", "BG", "BG:bg"),
    "cyprus": ("el", "CY", "CY:el"),
    "malta": ("en-MT", "MT", "MT:en"),
    "singapore": ("en-SG", "SG", "SG:en-SG"),
}

GLOBAL_EDITION = ("en-US", "US", "US:en")


def load_niche_extras(path: str) -> bool:
    """
    Extend load_niche_config() to also override this module's niche/policy
    term lists and local-edition map from the same YAML file - so one
    --niche-config file fully re-scopes both scripts for a second channel
    in a different niche (e.g. no "visa"/"tax" terms, different countries
    worth a local-language edition).

    Mutates NICHE_TERMS/POLICY_SIGNAL_WORDS/LOCAL_EDITIONS in place (slice
    assignment / clear+update) rather than rebinding, consistent with
    load_niche_config()'s TOPIC_CATEGORIES handling.
    """
    import os as _os
    import yaml

    loaded_categories = load_niche_config(path)

    if not _os.path.exists(path):
        return loaded_categories

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if data.get("niche_terms"):
        NICHE_TERMS[:] = data["niche_terms"]
    if data.get("policy_signal_words"):
        POLICY_SIGNAL_WORDS[:] = data["policy_signal_words"]
    if data.get("local_editions"):
        LOCAL_EDITIONS.clear()
        LOCAL_EDITIONS.update({k: tuple(v) for k, v in data["local_editions"].items()})

    return True


# =============================================================================
# QUERY BUILDING
# =============================================================================

def build_country_query(country: str) -> str:
    """
    Compound query: country AND (niche term) AND (policy signal word).
    This pairing is the noise filter - a bare "Indonesia" search returns
    mostly unrelated news; "Indonesia" + "visa" + "crackdown"-type terms
    returns almost exclusively relevant policy stories.
    """
    niche_or = " OR ".join(NICHE_TERMS)
    policy_or = " OR ".join(f'"{w}"' if " " in w else w for w in POLICY_SIGNAL_WORDS)
    return f'"{country}" ({niche_or}) ({policy_or})'


# =============================================================================
# FETCHING
# =============================================================================

def fetch_google_news_rss(query: str, hl: str, gl: str, ceid: str) -> list:
    """
    Fetch and parse a Google News RSS search feed. Returns a list of
    {title, link, source, published (datetime, tz-aware UTC)}.
    """
    params = f"?q={quote_plus(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    url = GOOGLE_NEWS_RSS + params

    items = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read()

        root = ET.fromstring(raw)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_raw = item.findtext("pubDate")
            source_el = item.find("source")
            source = source_el.text.strip() if source_el is not None and source_el.text else "unknown"

            published = None
            if pub_raw:
                try:
                    published = parsedate_to_datetime(pub_raw)
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=timezone.utc)
                except Exception:
                    published = None

            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "published": published,
                })
    except Exception as e:
        print(f"    Error fetching '{query}' ({hl}/{gl}): {e}")

    return items


def scan_worldwide(countries: list, include_local_editions: bool, lookback_hours: int) -> list:
    """
    Run country-level queries across the global edition (always) and, if
    requested, the curated local-language editions. Returns a flat list
    of raw article dicts tagged with the country that matched.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    all_articles = []

    print(f"\nScanning news for {len(countries)} countries "
          f"({'worldwide: global + local editions' if include_local_editions else 'global edition only'})...")

    for country in countries:
        query = build_country_query(country)
        editions = [GLOBAL_EDITION]
        if include_local_editions and country in LOCAL_EDITIONS:
            editions.append(LOCAL_EDITIONS[country])

        for hl, gl, ceid in editions:
            print(f"  {country} [{gl}]...")
            items = fetch_google_news_rss(query, hl, gl, ceid)
            for it in items:
                if it["published"] and it["published"] < cutoff:
                    continue
                it["country"] = country
                it["edition"] = gl
                all_articles.append(it)
            time.sleep(REQUEST_SLEEP)

    return all_articles


# =============================================================================
# CLUSTERING (same story, multiple outlets)
# =============================================================================

STOPWORDS = {
    "the", "a", "an", "in", "on", "of", "to", "for", "and", "or", "is",
    "are", "as", "at", "by", "with", "from", "new", "after", "over",
}


def _title_tokens(title: str) -> set:
    # Google News often appends " - SourceName" to the title; strip it.
    title = re.sub(r"\s+-\s+[^-]+$", "", title)
    words = re.findall(r"[a-zA-Z']+", title.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def cluster_articles(articles: list, similarity_threshold: float = 0.4) -> list:
    """
    Greedy clustering by token-set Jaccard similarity so the same story
    covered by 10 outlets counts as one high-confidence signal, not 10
    separate low-confidence ones.
    """
    clusters = []  # each: {"tokens": set, "articles": [...], "country": str}

    for art in articles:
        tokens = _title_tokens(art["title"])
        if not tokens:
            continue

        best_cluster = None
        best_score = 0.0
        for cluster in clusters:
            if cluster["country"] != art["country"]:
                continue
            union = cluster["tokens"] | tokens
            if not union:
                continue
            jaccard = len(cluster["tokens"] & tokens) / len(union)
            if jaccard > best_score:
                best_score = jaccard
                best_cluster = cluster

        if best_cluster and best_score >= similarity_threshold:
            best_cluster["articles"].append(art)
            best_cluster["tokens"] |= tokens
        else:
            clusters.append({"tokens": tokens, "articles": [art], "country": art["country"]})

    return clusters


# =============================================================================
# INTEREST SCORING
# =============================================================================

def classify_terms(text: str) -> dict:
    text_lower = text.lower()
    matched = {"countries": [], "visa_types": [], "tax_terms": [], "policy_signals": []}
    for category in ("countries", "visa_types", "tax_terms"):
        for term in TOPIC_CATEGORIES[category]:
            if term in text_lower:
                matched[category].append(term)
    for word in POLICY_SIGNAL_WORDS:
        if word in text_lower:
            matched["policy_signals"].append(word)
    return matched


def check_first_mover(db_path: str, matched_terms: dict, lookback_days: int = 45) -> bool:
    """
    True if no competitor (excluding your own channel) has published a
    video in the lookback window whose title mentions the same
    country/visa/tax terms as this news cluster - i.e. you'd be first.
    """
    if not os.path.exists(db_path):
        return True

    search_terms = matched_terms["countries"] + matched_terms["visa_types"] + matched_terms["tax_terms"]
    if not search_terms:
        return True

    since = (datetime.now() - timedelta(days=lookback_days)).isoformat()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT v.title FROM videos v
            JOIN channels c ON v.channel_id = c.channel_id
            WHERE (c.is_my_channel IS NULL OR c.is_my_channel = 0)
              AND v.publish_date >= ?
        ''', (since,))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return True
    conn.close()

    for (title,) in rows:
        title_lower = (title or "").lower()
        if any(term in title_lower for term in search_terms):
            return False
    return True


def compute_country_relevance_scores(competitive_db_path: str, countries: list) -> dict:
    """
    Score each country 0-100 by *proven* audience demand, not news novelty:
    view-weighted mentions of the country in your own video titles (60%,
    since that's direct evidence of what your specific audience watches)
    and in competitor video titles (40%, broader niche-wide evidence).

    This deliberately does NOT cover "nobody's made this video yet"
    countries - there's no view data for a topic nobody's covered, so an
    untested country always scores near 0 here. That's exactly what the
    wildcard bucket (selected separately, ignoring this score) exists for.
    """
    scores = {c: 0.0 for c in countries}
    if not os.path.exists(competitive_db_path):
        return scores

    conn = sqlite3.connect(competitive_db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT v.title, v.view_count FROM videos v
            JOIN channels c ON v.channel_id = c.channel_id
            WHERE c.is_my_channel = 1
        ''')
        my_rows = cursor.fetchall()

        cursor.execute('''
            SELECT v.title, v.view_count FROM videos v
            JOIN channels c ON v.channel_id = c.channel_id
            WHERE c.is_my_channel IS NULL OR c.is_my_channel = 0
        ''')
        comp_rows = cursor.fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return scores
    conn.close()

    def weighted_mentions(rows):
        weights = defaultdict(float)
        for title, views in rows:
            title_lower = (title or "").lower()
            weight = max(1, views or 1)
            for country in countries:
                if country in title_lower:
                    weights[country] += weight
        return weights

    def normalize(weights):
        if not weights:
            return {}
        import math
        logs = {k: math.log10(v + 1) for k, v in weights.items()}
        max_log = max(logs.values()) or 1
        return {k: (v / max_log) * 100 for k, v in logs.items()}

    my_norm = normalize(weighted_mentions(my_rows))
    comp_norm = normalize(weighted_mentions(comp_rows))

    for country in countries:
        scores[country] = 0.6 * my_norm.get(country, 0) + 0.4 * comp_norm.get(country, 0)

    return scores


def score_cluster(cluster: dict, competitive_db_path: str, relevance_scores: dict = None) -> dict:
    articles = cluster["articles"]
    combined_text = " ".join(a["title"] for a in articles)
    matched = classify_terms(combined_text)

    sources = {a["source"] for a in articles}
    source_diversity = len(sources)

    published_times = [a["published"] for a in articles if a["published"]]
    if published_times:
        newest = max(published_times)
        age_hours = max(0.0, (datetime.now(timezone.utc) - newest).total_seconds() / 3600)
    else:
        age_hours = 999

    recency_bonus = max(0.0, 48 - age_hours) * 1.0  # linear decay to 0 at 48h

    niche_specificity = (
        len(set(matched["countries"])) * 5
        + len(set(matched["visa_types"])) * 10
        + len(set(matched["tax_terms"])) * 8
    )
    policy_strength = len(set(matched["policy_signals"])) * 10

    is_first_mover = check_first_mover(competitive_db_path, matched)
    first_mover_bonus = 30 if is_first_mover else -15

    interest_score = (
        source_diversity * 15
        + recency_bonus
        + niche_specificity
        + policy_strength
        + first_mover_bonus
    )

    representative = min(articles, key=lambda a: len(a["title"]))["title"]
    representative = re.sub(r"\s+-\s+[^-]+$", "", representative)

    relevance_score = (relevance_scores or {}).get(cluster["country"], 0.0)
    # Floor of 0.3x so a very strong novelty story isn't fully zeroed out
    # just because the country has no view history yet; ceiling of 1.3x
    # so proven-demand countries get a real boost, not just a tiebreak.
    relevance_multiplier = 0.3 + (relevance_score / 100.0)
    combined_score = interest_score * relevance_multiplier

    return {
        "headline": representative,
        "country": cluster["country"],
        "interest_score": round(interest_score, 1),
        "relevance_score": round(relevance_score, 1),
        "combined_score": round(combined_score, 1),
        "source_count": source_diversity,
        "sources": sorted(sources),
        "age_hours": round(age_hours, 1),
        "matched_countries": sorted(set(matched["countries"])),
        "matched_visa_types": sorted(set(matched["visa_types"])),
        "matched_tax_terms": sorted(set(matched["tax_terms"])),
        "policy_signals": sorted(set(matched["policy_signals"])),
        "is_first_mover": is_first_mover,
        "articles": [
            {
                "title": a["title"],
                "link": a["link"],
                "source": a["source"],
                "published": a["published"].isoformat() if a["published"] else None,
            }
            for a in sorted(articles, key=lambda a: a["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        ],
    }


# =============================================================================
# OUTPUT
# =============================================================================

def save_results(signals: list, wildcards: list, output_dir: str) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = os.path.join(output_dir, f"news_signals_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"mainstream": signals, "wildcards": wildcards}, f, indent=2, ensure_ascii=False)

    db_path = os.path.join(output_dir, "news_signals.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT,
            country TEXT,
            interest_score REAL,
            relevance_score REAL,
            combined_score REAL,
            is_wildcard BOOLEAN,
            source_count INTEGER,
            age_hours REAL,
            is_first_mover BOOLEAN,
            matched_countries TEXT,
            matched_visa_types TEXT,
            matched_tax_terms TEXT,
            policy_signals TEXT,
            top_link TEXT,
            scanned_at TEXT
        )
    ''')
    # Migrate older news_signals.db files (pre-relevance-weighting) in place.
    cursor.execute("PRAGMA table_info(news_signals)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    for column, coltype in (("relevance_score", "REAL"), ("combined_score", "REAL"), ("is_wildcard", "BOOLEAN")):
        if column not in existing_columns:
            cursor.execute(f"ALTER TABLE news_signals ADD COLUMN {column} {coltype}")

    now = datetime.now().isoformat()
    for s in signals:
        cursor.execute('''
            INSERT INTO news_signals
            (headline, country, interest_score, relevance_score, combined_score, is_wildcard,
             source_count, age_hours, is_first_mover,
             matched_countries, matched_visa_types, matched_tax_terms, policy_signals, top_link, scanned_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            s["headline"], s["country"], s["interest_score"], s["relevance_score"], s["combined_score"],
            s.get("is_wildcard", False), s["source_count"], s["age_hours"],
            s["is_first_mover"], json.dumps(s["matched_countries"]), json.dumps(s["matched_visa_types"]),
            json.dumps(s["matched_tax_terms"]), json.dumps(s["policy_signals"]),
            s["articles"][0]["link"] if s["articles"] else None, now
        ))
    conn.commit()
    conn.close()

    md_path = os.path.join(output_dir, f"news_signals_report_{timestamp}.md")
    generate_markdown_report(signals, wildcards, md_path)

    return {"json": json_path, "database": db_path, "markdown": md_path}


def generate_markdown_report(signals: list, wildcards: list, output_path: str):
    lines = []
    lines.append("# News Signal Scan - Cover This Before Competitors Do")
    lines.append(f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    lines.append(f"- **Stories detected:** {len(signals)}")
    lines.append(f"- **First-mover opportunities:** {sum(1 for s in signals if s['is_first_mover'])}")
    lines.append(f"- **Wildcard candidates:** {len(wildcards)}\n")

    lines.append("## Daily Pick - Ranked by Audience-Weighted Score\n")
    lines.append("Ranked by `combined_score` (novelty score weighted by proven view "
                  "demand for that country from your own and competitor channels). "
                  "This is the list to work through for daily uploads.\n")
    lines.append("| # | Score | Relevance | Country | Headline | Sources | Age (h) | First Mover? |")
    lines.append("|---|-------|-----------|---------|----------|---------|---------|--------------|")
    for i, s in enumerate(signals[:40], 1):
        fm = "Yes" if s["is_first_mover"] else "No"
        lines.append(
            f"| {i} | {s['combined_score']:.0f} | {s['relevance_score']:.0f} | {s['country'].title()} | "
            f"{s['headline'][:70]} | {s['source_count']} | {s['age_hours']:.0f} | {fm} |"
        )

    for s in signals[:15]:
        lines.append(f"\n### {s['headline']}\n")
        lines.append(f"- **Combined score:** {s['combined_score']:.0f}  (novelty {s['interest_score']:.0f} x "
                      f"relevance {s['relevance_score']:.0f})  |  **Country:** {s['country'].title()}  |  "
                      f"**Sources:** {s['source_count']}  |  **First mover:** {'Yes' if s['is_first_mover'] else 'No'}")
        if s["policy_signals"]:
            lines.append(f"- **Policy signals:** {', '.join(s['policy_signals'])}")
        lines.append("- **Articles:**")
        for a in s["articles"][:5]:
            lines.append(f"  - [{a['title']}]({a['link']}) - {a['source']}")

    if wildcards:
        lines.append("\n## Wildcard Picks (untested territory - cover one every ~7-10 videos)\n")
        lines.append("These score low on proven relevance simply because nobody's ever "
                      "covered this angle for your audience - there's no view data to "
                      "weight it by. High novelty score means the underlying news itself "
                      "is strong (multiple sources, fresh, policy-significant, uncontested). "
                      "Worth an occasional swing to test for hidden demand.\n")
        lines.append("| # | Novelty Score | Country | Headline | Sources | First Mover? |")
        lines.append("|---|----------------|---------|----------|---------|--------------|")
        for i, s in enumerate(wildcards, 1):
            fm = "Yes" if s["is_first_mover"] else "No"
            lines.append(
                f"| {i} | {s['interest_score']:.0f} | {s['country'].title()} | "
                f"{s['headline'][:70]} | {s['source_count']} | {fm} |"
            )
        for s in wildcards:
            lines.append(f"\n### [Wildcard] {s['headline']}\n")
            lines.append(f"- **Novelty score:** {s['interest_score']:.0f}  |  **Country:** {s['country'].title()}  |  "
                          f"**Proven relevance:** {s['relevance_score']:.0f}/100 (untested)")
            lines.append("- **Articles:**")
            for a in s["articles"][:5]:
                lines.append(f"  - [{a['title']}]({a['link']}) - {a['source']}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def print_summary(signals: list, wildcards: list):
    print("\n" + "=" * 60)
    print("  NEWS SIGNAL SCAN COMPLETE")
    print("=" * 60)
    print(f"\nStories detected: {len(signals)}")
    print(f"First-mover opportunities: {sum(1 for s in signals if s['is_first_mover'])}")
    print(f"Wildcard candidates: {len(wildcards)}")

    print("\nTOP 10 DAILY PICKS (audience-weighted combined score):")
    print("-" * 60)
    for i, s in enumerate(signals[:10], 1):
        fm = " [FIRST MOVER]" if s["is_first_mover"] else ""
        print(f"{i:2}. [{s['combined_score']:.0f}] ({s['country'].title()}) {s['headline'][:60]}{fm}")

    if wildcards:
        print("\nWILDCARD PICKS (untested territory, cover ~1 in 7-10 videos):")
        print("-" * 60)
        for i, s in enumerate(wildcards, 1):
            fm = " [FIRST MOVER]" if s["is_first_mover"] else ""
            print(f"{i:2}. [novelty {s['interest_score']:.0f}] ({s['country'].title()}) {s['headline'][:55]}{fm}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Scan worldwide news for niche policy stories, ranked by an interest meter"
    )
    parser.add_argument("--countries", type=str,
                        help="Comma-separated countries to scan (default: all in TOPIC_CATEGORIES)")
    parser.add_argument("--local-editions", action="store_true",
                        help="Also query curated local-language editions, not just the global English edition")
    parser.add_argument("--lookback-hours", type=int, default=72,
                        help="Only consider articles published within this many hours (default: 72)")
    parser.add_argument("--min-score", type=float, default=20.0,
                        help="Minimum interest (novelty) score to include in the report (default: 20)")
    parser.add_argument("--wildcard-relevance-threshold", type=float, default=15.0,
                        help="Countries scoring below this proven-relevance (0-100) are wildcard-eligible (default: 15)")
    parser.add_argument("--wildcard-min-score", type=float, default=40.0,
                        help="Minimum novelty score for a wildcard candidate - keeps the bucket to genuinely strong, uncontested stories, not just any low-relevance noise (default: 40)")
    parser.add_argument("--wildcard-count", type=int, default=5,
                        help="Max wildcard candidates to surface per scan (default: 5)")
    parser.add_argument("--output", "-o", type=str, default=DEFAULT_OUTPUT_DIR,
                        help="Output directory")
    parser.add_argument("--niche-config", type=str, default="niche_config.yaml",
                        help="Path to a niche config YAML (countries, niche/policy terms, local editions) - "
                             "point a second channel at its own file to run this tool for a different niche")

    args = parser.parse_args()

    if load_niche_extras(args.niche_config):
        print(f"Loaded niche config from {args.niche_config}")

    if args.countries:
        countries = [c.strip().lower() for c in args.countries.split(",")]
    else:
        countries = TOPIC_CATEGORIES["countries"]

    articles = scan_worldwide(countries, args.local_editions, args.lookback_hours)
    print(f"\nTotal articles gathered: {len(articles)}")

    clusters = cluster_articles(articles)
    print(f"Clustered into {len(clusters)} distinct stories")

    competitive_db_path = os.path.join(args.output, "competitive_analysis.db")
    relevance_scores = compute_country_relevance_scores(competitive_db_path, countries)
    signals = [score_cluster(c, competitive_db_path, relevance_scores) for c in clusters]

    # Local-language Google News editions rank by fuzzy relevance, not literal
    # keyword match, so a translated title can pass through with none of our
    # actual niche terms present. Country name and policy words (ruling,
    # dispute, update...) are too generic to prove a story is actually about
    # the niche - almost any legal/policy story mentions a country and one of
    # those words. Require a real content-term match (visa_types or
    # tax_terms, the niche's actual subject vocabulary) instead.
    dropped_no_match = sum(
        1 for s in signals
        if not (s["matched_visa_types"] or s["matched_tax_terms"])
    )
    signals = [
        s for s in signals
        if s["matched_visa_types"] or s["matched_tax_terms"]
    ]
    if dropped_no_match:
        print(f"Dropped {dropped_no_match} clusters with no literal niche-topic term match (country/policy-word-only matches are too generic to prove relevance)")

    signals = [s for s in signals if s["interest_score"] >= args.min_score]

    # Wildcard bucket: strong, uncontested news in countries with no proven
    # view history. Pulled out separately (by raw novelty, ignoring
    # relevance) rather than just discounted to the bottom of the main list -
    # untested demand can't show up in past-performance data by definition.
    wildcards = [
        s for s in signals
        if s["relevance_score"] < args.wildcard_relevance_threshold
        and s["interest_score"] >= args.wildcard_min_score
    ]
    wildcards.sort(key=lambda s: s["interest_score"], reverse=True)
    wildcards = wildcards[:args.wildcard_count]
    wildcard_keys = {(s["headline"], s["country"]) for s in wildcards}
    for s in signals:
        s["is_wildcard"] = (s["headline"], s["country"]) in wildcard_keys

    # Mainstream list: everything, ranked by relevance-weighted combined score
    # (this is what most daily picks should come from).
    mainstream = sorted(signals, key=lambda s: s["combined_score"], reverse=True)

    output_files = save_results(mainstream, wildcards, args.output)
    print_summary(mainstream, wildcards)

    print(f"\nOutput saved to:")
    print(f"  - {output_files['json']}")
    print(f"  - {output_files['database']}")
    print(f"  - {output_files['markdown']}")


if __name__ == "__main__":
    main()
