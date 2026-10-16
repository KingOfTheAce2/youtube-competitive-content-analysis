#!/usr/bin/env python3
"""
Google Search Demand Analyzer

Gathers search demand data from Google to identify video topic opportunities.
Combines with YouTube competitive analysis for comprehensive content strategy.

Data sources:
- Google Autocomplete API (free, no auth)
- Google Trends (via pytrends)
- "People Also Ask" patterns
- Related searches

Usage:
    python google_search_analyzer.py --channel @YourChannel
    python google_search_analyzer.py --keywords "expat taxes, golden visa, digital nomad"
    python google_search_analyzer.py --from-youtube  # Uses your YouTube channel topics
"""

import argparse
import json
import os
import re
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus

import requests

# Optional imports - will work without them but with reduced functionality
try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False
    print("Note: Install pytrends for Google Trends data: pip install pytrends")


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_OUTPUT_DIR = "./output"
AUTOCOMPLETE_URL = "https://suggestqueries.google.com/complete/search"
GOOGLE_TRENDS_REGIONS = ["US", "GB", "DE", "AU", "CA"]  # Key expat source countries

# Topic categories for classification
TOPIC_CATEGORIES = {
    'countries': [
        # Near-worldwide sovereign-state coverage (UN members + a handful of
        # commonly-referenced territories) so the news scanner and search
        # analyzer aren't limited to a hand-picked "usual suspects" list -
        # a policy story can break anywhere.
        'afghanistan', 'albania', 'algeria', 'andorra', 'angola',
        'antigua and barbuda', 'argentina', 'armenia', 'australia', 'austria',
        'azerbaijan', 'bahamas', 'bahrain', 'bangladesh', 'barbados',
        'belarus', 'belgium', 'belize', 'benin', 'bhutan', 'bolivia',
        'bosnia and herzegovina', 'botswana', 'brazil', 'brunei', 'bulgaria',
        'burkina faso', 'burundi', 'cabo verde', 'cambodia', 'cameroon',
        'canada', 'central african republic', 'chad', 'chile', 'china',
        'colombia', 'comoros', 'congo', 'costa rica', 'croatia', 'cuba',
        'cyprus', 'czech republic', 'denmark', 'djibouti', 'dominica',
        'dominican republic', 'dubai', 'ecuador', 'egypt', 'el salvador',
        'equatorial guinea', 'eritrea', 'estonia', 'eswatini', 'ethiopia',
        'fiji', 'finland', 'france', 'gabon', 'gambia', 'georgia', 'germany',
        'ghana', 'greece', 'grenada', 'guatemala', 'guinea', 'guinea-bissau',
        'guyana', 'haiti', 'honduras', 'hungary', 'iceland', 'india',
        'indonesia', 'iran', 'iraq', 'ireland', 'israel', 'italy',
        'ivory coast', 'jamaica', 'japan', 'jordan', 'kazakhstan', 'kenya',
        'kiribati', 'kosovo', 'kuwait', 'kyrgyzstan', 'laos', 'latvia',
        'lebanon', 'lesotho', 'liberia', 'libya', 'liechtenstein',
        'lithuania', 'luxembourg', 'madagascar', 'malawi', 'malaysia',
        'maldives', 'mali', 'malta', 'marshall islands', 'mauritania',
        'mauritius', 'mexico', 'micronesia', 'moldova', 'monaco', 'mongolia',
        'montenegro', 'morocco', 'mozambique', 'myanmar', 'namibia', 'nauru',
        'nepal', 'netherlands', 'new zealand', 'nicaragua', 'niger',
        'nigeria', 'north korea', 'north macedonia', 'norway', 'oman',
        'pakistan', 'palau', 'palestine', 'panama', 'papua new guinea',
        'paraguay', 'peru', 'philippines', 'poland', 'portugal', 'qatar',
        'romania', 'russia', 'rwanda', 'saint kitts and nevis', 'saint lucia',
        'saint vincent and the grenadines', 'samoa', 'san marino',
        'sao tome and principe', 'saudi arabia', 'senegal', 'serbia',
        'seychelles', 'sierra leone', 'singapore', 'slovakia', 'slovenia',
        'solomon islands', 'somalia', 'south africa', 'south korea',
        'south sudan', 'spain', 'sri lanka', 'sudan', 'suriname', 'sweden',
        'switzerland', 'syria', 'taiwan', 'tajikistan', 'tanzania',
        'thailand', 'timor-leste', 'togo', 'tonga', 'trinidad and tobago',
        'tunisia', 'turkey', 'turkmenistan', 'tuvalu', 'uganda', 'uk',
        'ukraine', 'uae', 'united states', 'uruguay', 'uzbekistan',
        'vanuatu', 'vatican city', 'venezuela', 'vietnam', 'yemen',
        'zambia', 'zimbabwe',
    ],
    'visa_types': [
        'golden visa', 'digital nomad visa', 'investor visa', 'd7 visa',
        'beckham law', 'nhr', 'non-habitual resident', 'retirement visa',
        'freelancer visa', 'startup visa', 'entrepreneur visa', 'work permit',
        'residence permit', 'permanent residency', 'citizenship', 'passport',
        'second passport', 'citizenship by investment', 'naturalization'
    ],
    'tax_terms': [
        'tax residency', 'tax resident', 'territorial tax', 'worldwide tax',
        'double taxation', 'tax treaty', 'feie', 'foreign earned income',
        'foreign tax credit', 'fbar', 'fatca', 'cfc', 'gilti', 'pfic',
        'exit tax', 'wealth tax', 'capital gains', 'inheritance tax',
        'estate tax', 'property tax', 'vat', 'corporate tax', 'flat tax',
        'tax haven', 'tax free', 'zero tax', 'low tax', 'tax optimization'
    ],
    'expat_lifestyle': [
        'cost of living', 'expat life', 'moving abroad', 'relocate',
        'retire abroad', 'work remotely', 'digital nomad', 'location independent',
        'expat community', 'healthcare abroad', 'banking abroad', 'real estate',
        'property investment', 'rental income', 'passive income', 'remote work'
    ]
}


# =============================================================================
# GOOGLE AUTOCOMPLETE
# =============================================================================

def get_google_autocomplete(query: str, country: str = "us", language: str = "en") -> list:
    """
    Get Google autocomplete suggestions for a query.
    Free API, no authentication required.
    """
    params = {
        "client": "firefox",  # Returns JSON
        "q": query,
        "hl": language,
        "gl": country,
    }

    try:
        response = requests.get(AUTOCOMPLETE_URL, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if len(data) > 1:
                return data[1]  # Suggestions are in second element
    except Exception as e:
        print(f"  Autocomplete error for '{query}': {e}")

    return []


def expand_query_with_modifiers(base_query: str) -> list:
    """
    Expand a base query with common search modifiers to find more suggestions.
    """
    modifiers = [
        "",  # Base query
        "how to",
        "what is",
        "why",
        "best",
        "cheapest",
        "easiest",
        "fastest",
        "can i",
        "do i need",
        "is it worth",
        "vs",
        "for americans",
        "for expats",
        "2025",
        "requirements",
        "cost",
        "pros and cons",
    ]

    # Also add alphabet expansion for deeper suggestions
    alphabet = list("abcdefghijklmnopqrstuvwxyz")

    expanded = []
    for mod in modifiers:
        if mod:
            expanded.append(f"{mod} {base_query}")
        else:
            expanded.append(base_query)

    # Add alphabet expansion
    for letter in alphabet[:10]:  # First 10 letters
        expanded.append(f"{base_query} {letter}")

    return expanded


def gather_autocomplete_suggestions(seed_keywords: list, countries: list = None) -> dict:
    """
    Gather autocomplete suggestions for seed keywords across multiple countries.
    """
    if countries is None:
        countries = ["us", "gb", "de"]

    all_suggestions = defaultdict(lambda: {"count": 0, "sources": [], "queries": []})

    print(f"\nGathering autocomplete suggestions for {len(seed_keywords)} keywords...")

    for keyword in seed_keywords:
        print(f"  Processing: {keyword}")
        expanded_queries = expand_query_with_modifiers(keyword)

        for query in expanded_queries[:15]:  # Limit to avoid rate limiting
            for country in countries:
                suggestions = get_google_autocomplete(query, country)

                for suggestion in suggestions:
                    suggestion_lower = suggestion.lower().strip()
                    all_suggestions[suggestion_lower]["count"] += 1
                    all_suggestions[suggestion_lower]["sources"].append(country)
                    if query not in all_suggestions[suggestion_lower]["queries"]:
                        all_suggestions[suggestion_lower]["queries"].append(query)

                time.sleep(0.1)  # Rate limiting

    return dict(all_suggestions)


# =============================================================================
# GOOGLE TRENDS
# =============================================================================

def get_google_trends_data(keywords: list, timeframe: str = "today 12-m") -> dict:
    """
    Get Google Trends data for keywords.
    Requires pytrends: pip install pytrends
    """
    if not PYTRENDS_AVAILABLE:
        return {"error": "pytrends not installed", "data": {}}

    print(f"\nFetching Google Trends data for {len(keywords)} keywords...")

    try:
        pytrends = TrendReq(hl='en-US', tz=360)

        # Google Trends allows max 5 keywords at once
        trends_data = {}

        for i in range(0, len(keywords), 5):
            batch = keywords[i:i+5]
            print(f"  Processing batch: {batch}")

            try:
                pytrends.build_payload(batch, cat=0, timeframe=timeframe, geo='', gprop='')

                # Interest over time
                interest = pytrends.interest_over_time()
                if not interest.empty:
                    for kw in batch:
                        if kw in interest.columns:
                            trends_data[kw] = {
                                "avg_interest": float(interest[kw].mean()),
                                "max_interest": float(interest[kw].max()),
                                "current_interest": float(interest[kw].iloc[-1]) if len(interest) > 0 else 0,
                                "trend": "rising" if interest[kw].iloc[-1] > interest[kw].mean() else "stable"
                            }

                # Related queries
                related = pytrends.related_queries()
                for kw in batch:
                    if kw in related and related[kw]['rising'] is not None:
                        rising = related[kw]['rising'].head(10).to_dict('records')
                        trends_data.setdefault(kw, {})["rising_queries"] = rising
                    if kw in related and related[kw]['top'] is not None:
                        top = related[kw]['top'].head(10).to_dict('records')
                        trends_data.setdefault(kw, {})["top_queries"] = top

                time.sleep(1)  # Rate limiting

            except Exception as e:
                print(f"  Error processing batch {batch}: {e}")
                continue

        return {"data": trends_data, "timeframe": timeframe}

    except Exception as e:
        return {"error": str(e), "data": {}}


def get_trending_searches_by_region(regions: list = None) -> dict:
    """
    Get currently trending searches by region.
    """
    if not PYTRENDS_AVAILABLE:
        return {}

    if regions is None:
        regions = GOOGLE_TRENDS_REGIONS

    print(f"\nFetching trending searches for regions: {regions}")

    trending = {}

    try:
        pytrends = TrendReq(hl='en-US', tz=360)

        for region in regions:
            try:
                df = pytrends.trending_searches(pn=region.lower())
                trending[region] = df[0].tolist()[:20]
                time.sleep(0.5)
            except Exception as e:
                print(f"  Could not get trends for {region}: {e}")
                trending[region] = []

    except Exception as e:
        print(f"  Trends error: {e}")

    return trending


# =============================================================================
# TREND-CYCLE HISTORY TRACKING
# =============================================================================
# Goal: catch topics that were popular before, faded, and are climbing again
# (e.g. a visa crackdown story that resurfaces every 1-2 years) *before*
# competitors notice the re-ignition. This works two ways:
#   1. One-shot: pull a long (multi-year) monthly time series from Google
#      Trends and detect peak -> trough -> recovery patterns directly.
#   2. Cumulative: every run also appends today's snapshot, so re-running
#      this tool over months builds first-party history even for topics
#      pytrends' long lookback doesn't cover well.

def get_trends_time_series(keywords: list, timeframe: str = "today 5-y") -> dict:
    """
    Get a full historical interest-over-time series per keyword (monthly
    granularity for 5y timeframe). Used to detect cyclical re-ignition
    without needing months of accumulated local runs.
    """
    if not PYTRENDS_AVAILABLE:
        return {}

    print(f"\nFetching {timeframe} trend history for {len(keywords)} keywords...")

    pytrends = TrendReq(hl='en-US', tz=360)
    series_by_keyword = {}

    for i in range(0, len(keywords), 5):
        batch = keywords[i:i + 5]
        try:
            pytrends.build_payload(batch, cat=0, timeframe=timeframe, geo='', gprop='')
            interest = pytrends.interest_over_time()
            if not interest.empty:
                for kw in batch:
                    if kw in interest.columns:
                        series_by_keyword[kw] = [
                            (idx.strftime("%Y-%m-%d"), float(val))
                            for idx, val in interest[kw].items()
                        ]
            time.sleep(1)
        except Exception as e:
            print(f"  Error fetching history for {batch}: {e}")
            continue

    return series_by_keyword


def save_trends_history(db_path: str, series_by_keyword: dict, timeframe: str):
    """
    Persist trend time series points to the database (idempotent per
    keyword/period/timeframe so repeat runs update rather than duplicate).
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trends_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            period_date TEXT NOT NULL,
            interest_value REAL,
            timeframe TEXT NOT NULL,
            recorded_at TEXT,
            UNIQUE(keyword, period_date, timeframe)
        )
    ''')

    now = datetime.now().isoformat()
    for keyword, points in series_by_keyword.items():
        for period_date, value in points:
            cursor.execute('''
                INSERT INTO trends_history (keyword, period_date, interest_value, timeframe, recorded_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(keyword, period_date, timeframe) DO UPDATE SET
                    interest_value = excluded.interest_value,
                    recorded_at = excluded.recorded_at
            ''', (keyword, period_date, value, timeframe, now))

    conn.commit()
    conn.close()


def append_current_snapshot(db_path: str, trends_data: dict):
    """
    Append today's current-interest reading per keyword under a distinct
    'daily' timeframe tag, so repeated runs over time build first-party
    history independent of what Google Trends' own lookback returns.
    """
    if not trends_data:
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trends_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            period_date TEXT NOT NULL,
            interest_value REAL,
            timeframe TEXT NOT NULL,
            recorded_at TEXT,
            UNIQUE(keyword, period_date, timeframe)
        )
    ''')

    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().isoformat()
    for keyword, data in trends_data.items():
        current = data.get("current_interest")
        if current is None:
            continue
        cursor.execute('''
            INSERT INTO trends_history (keyword, period_date, interest_value, timeframe, recorded_at)
            VALUES (?, ?, ?, 'daily_snapshot', ?)
            ON CONFLICT(keyword, period_date, timeframe) DO UPDATE SET
                interest_value = excluded.interest_value,
                recorded_at = excluded.recorded_at
        ''', (keyword, today, current, now))

    conn.commit()
    conn.close()


def detect_cyclical_topics(db_path: str, min_points: int = 12) -> list:
    """
    Analyze stored trend history per keyword to find peak -> trough ->
    recovery patterns: topics that were popular before, faded, and are
    climbing again now. These are strong candidates to cover early, since
    most competitors only react to *current* popularity, not cycles.
    """
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT DISTINCT keyword FROM trends_history")
        keywords = [r[0] for r in cursor.fetchall()]
    except sqlite3.OperationalError:
        conn.close()
        return []

    results = []

    for keyword in keywords:
        cursor.execute('''
            SELECT period_date, interest_value FROM trends_history
            WHERE keyword = ?
            ORDER BY period_date ASC
        ''', (keyword,))
        rows = cursor.fetchall()

        if len(rows) < min_points:
            continue

        values = [v for _, v in rows]
        dates = [d for d, _ in rows]

        overall_max = max(values)
        if overall_max <= 0:
            continue

        # Recent window = last ~3 months of data points, prior window =
        # the 3 months before that (used to measure current momentum).
        recent = values[-3:]
        prior = values[-6:-3] if len(values) >= 6 else values[:max(1, len(values) - 3)]

        recent_avg = sum(recent) / len(recent)
        prior_avg = sum(prior) / len(prior) if prior else 0

        # Find the most recent trough (local minimum) before the recent window
        pre_recent = values[:-3] if len(values) > 3 else values
        trough = min(pre_recent) if pre_recent else 0

        # Was this topic previously a significant peak (>=60% of its all-time
        # max) at some point, i.e. it has a genuine cycle rather than just
        # being a flat, slowly growing topic?
        had_prior_peak = any(v >= overall_max * 0.6 for v in values[:-3])

        is_rising = recent_avg > prior_avg * 1.2 and recent_avg > trough * 1.3
        is_reignition = had_prior_peak and is_rising and trough < overall_max * 0.4

        if is_reignition:
            results.append({
                "keyword": keyword,
                "all_time_max": overall_max,
                "trough_value": trough,
                "recent_avg": round(recent_avg, 1),
                "prior_avg": round(prior_avg, 1),
                "recovery_pct": round((recent_avg / trough - 1) * 100, 1) if trough > 0 else None,
                "latest_date": dates[-1],
                "data_points": len(values),
            })

    conn.close()

    results.sort(key=lambda x: (x["recovery_pct"] or 0), reverse=True)
    return results


# =============================================================================
# QUESTION PATTERN EXTRACTION
# =============================================================================

def extract_questions(suggestions: dict) -> list:
    """
    Extract question-based searches from suggestions.
    These are perfect for YouTube "People Also Ask" style videos.
    """
    question_starters = [
        'how', 'what', 'why', 'when', 'where', 'who', 'which',
        'can i', 'can you', 'do i', 'do you', 'is it', 'are there',
        'should i', 'will i', 'does', 'am i', 'have i'
    ]

    questions = []

    for suggestion, data in suggestions.items():
        suggestion_lower = suggestion.lower()
        for starter in question_starters:
            if suggestion_lower.startswith(starter):
                questions.append({
                    "question": suggestion,
                    "frequency": data["count"],
                    "type": starter.split()[0],
                    "sources": list(set(data["sources"]))
                })
                break

    # Sort by frequency
    questions.sort(key=lambda x: x["frequency"], reverse=True)

    return questions


def extract_comparison_searches(suggestions: dict) -> list:
    """
    Extract comparison searches (vs, or, compared to).
    Great for comparison video content.
    """
    comparison_patterns = [' vs ', ' or ', ' compared to ', ' versus ', ' better than ']

    comparisons = []

    for suggestion, data in suggestions.items():
        for pattern in comparison_patterns:
            if pattern in suggestion.lower():
                comparisons.append({
                    "query": suggestion,
                    "frequency": data["count"],
                    "pattern": pattern.strip()
                })
                break

    comparisons.sort(key=lambda x: x["frequency"], reverse=True)

    return comparisons


# =============================================================================
# TOPIC CLASSIFICATION
# =============================================================================

def classify_search(query: str) -> dict:
    """
    Classify a search query into topic categories.
    """
    query_lower = query.lower()

    classification = {
        "countries": [],
        "visa_types": [],
        "tax_terms": [],
        "expat_lifestyle": [],
        "is_question": any(query_lower.startswith(q) for q in ['how', 'what', 'why', 'when', 'where', 'can', 'do', 'is', 'should']),
        "is_comparison": any(p in query_lower for p in [' vs ', ' or ', ' versus ']),
        "has_year": bool(re.search(r'202[4-9]|2030', query_lower)),
    }

    for category, terms in TOPIC_CATEGORIES.items():
        for term in terms:
            if term in query_lower:
                classification[category].append(term)

    return classification


def analyze_search_patterns(suggestions: dict) -> dict:
    """
    Analyze search patterns to identify content opportunities.
    """
    patterns = {
        "by_category": defaultdict(list),
        "by_country": defaultdict(int),
        "by_visa_type": defaultdict(int),
        "by_tax_term": defaultdict(int),
        "questions": [],
        "comparisons": [],
        "trending_modifiers": defaultdict(int),
    }

    for suggestion, data in suggestions.items():
        classification = classify_search(suggestion)

        # Categorize
        for country in classification["countries"]:
            patterns["by_country"][country] += data["count"]

        for visa in classification["visa_types"]:
            patterns["by_visa_type"][visa] += data["count"]

        for tax in classification["tax_terms"]:
            patterns["by_tax_term"][tax] += data["count"]

        # Extract modifiers
        if "2025" in suggestion.lower() or "2024" in suggestion.lower():
            patterns["trending_modifiers"]["year"] += 1
        if "best" in suggestion.lower():
            patterns["trending_modifiers"]["best"] += 1
        if "cheapest" in suggestion.lower() or "cheap" in suggestion.lower():
            patterns["trending_modifiers"]["cheapest"] += 1
        if "how to" in suggestion.lower():
            patterns["trending_modifiers"]["how_to"] += 1

    # Extract questions and comparisons
    patterns["questions"] = extract_questions(suggestions)
    patterns["comparisons"] = extract_comparison_searches(suggestions)

    # Convert defaultdicts to regular dicts for JSON serialization
    patterns["by_country"] = dict(sorted(patterns["by_country"].items(), key=lambda x: x[1], reverse=True))
    patterns["by_visa_type"] = dict(sorted(patterns["by_visa_type"].items(), key=lambda x: x[1], reverse=True))
    patterns["by_tax_term"] = dict(sorted(patterns["by_tax_term"].items(), key=lambda x: x[1], reverse=True))
    patterns["trending_modifiers"] = dict(patterns["trending_modifiers"])

    return patterns


# =============================================================================
# VIDEO OPPORTUNITY SCORING
# =============================================================================

def score_video_opportunities(suggestions: dict, patterns: dict, your_topics: list = None) -> list:
    """
    Score and rank video opportunities based on search demand and gaps.
    """
    opportunities = []

    for suggestion, data in suggestions.items():
        classification = classify_search(suggestion)

        # Base score from frequency
        score = data["count"] * 10

        # Bonus for questions (high intent)
        if classification["is_question"]:
            score += 20

        # Bonus for comparisons (decision stage)
        if classification["is_comparison"]:
            score += 15

        # Bonus for current year
        if classification["has_year"]:
            score += 10

        # Bonus for specific countries/visas/tax terms
        specificity_score = (
            len(classification["countries"]) * 5 +
            len(classification["visa_types"]) * 10 +
            len(classification["tax_terms"]) * 8
        )
        score += specificity_score

        # Check if it's a gap (you don't cover it)
        is_gap = True
        if your_topics:
            for topic in your_topics:
                if topic.lower() in suggestion.lower():
                    is_gap = False
                    break

        if is_gap:
            score += 25  # Bonus for gaps

        # Determine content type
        if classification["is_question"]:
            content_type = "explainer"
        elif classification["is_comparison"]:
            content_type = "comparison"
        elif any(term in suggestion.lower() for term in ['how to', 'guide', 'tutorial']):
            content_type = "tutorial"
        elif any(term in suggestion.lower() for term in ['best', 'top', 'ranking']):
            content_type = "listicle"
        else:
            content_type = "informational"

        opportunities.append({
            "query": suggestion,
            "score": score,
            "frequency": data["count"],
            "content_type": content_type,
            "is_gap": is_gap,
            "classification": classification,
            "sources": list(set(data["sources"]))
        })

    # Sort by score
    opportunities.sort(key=lambda x: x["score"], reverse=True)

    return opportunities


# =============================================================================
# INTEGRATION WITH YOUTUBE ANALYZER
# =============================================================================

def get_channel_topics_from_db(db_path: str, channel_id: str = None) -> list:
    """
    Extract topics from your channel's videos in the YouTube analyzer database.
    """
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        if channel_id:
            cursor.execute('''
                SELECT title, description FROM videos
                WHERE channel_id = ?
            ''', (channel_id,))
        else:
            # Get my_channel from the first row in channels that matches
            cursor.execute('''
                SELECT DISTINCT title, description FROM videos LIMIT 100
            ''')

        rows = cursor.fetchall()

        # Extract keywords from titles
        all_words = []
        for title, desc in rows:
            words = re.findall(r'\b[a-zA-Z]{4,}\b', title.lower())
            all_words.extend(words)

        # Get most common topics
        common = Counter(all_words).most_common(50)
        topics = [word for word, count in common if count >= 2]

        conn.close()
        return topics

    except Exception as e:
        print(f"  Database error: {e}")
        conn.close()
        return []


def load_niche_config(path: str = "niche_config.yaml") -> bool:
    """
    Load niche-specific classification data (countries, visa/tax terms) from
    an external YAML file, replacing TOPIC_CATEGORIES' contents *in place*.

    Mutating in place (clear + update) rather than rebinding the name is
    deliberate: news_signal_scanner.py does `from google_search_analyzer
    import TOPIC_CATEGORIES`, which binds to this same dict object. An
    in-place mutation here is visible there too; reassigning the name
    would not be. This is what lets one config file drive both scripts.

    Returns False (leaving the built-in defaults untouched) if the file
    doesn't exist - a second channel in a different niche points
    --niche-config at its own file; the original channel needs no changes.
    """
    import yaml

    if not os.path.exists(path):
        return False

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    categories = data.get("topic_categories")
    if categories:
        TOPIC_CATEGORIES.clear()
        TOPIC_CATEGORIES.update(categories)

    return True


def load_my_channel_config() -> dict:
    """
    Load channel configuration from my_channels.yaml or config.yaml.
    """
    import yaml

    config = {}

    # Try my_channels.yaml first (gitignored)
    if os.path.exists("my_channels.yaml"):
        with open("my_channels.yaml", 'r') as f:
            config = yaml.safe_load(f) or {}

    # Fall back to config.yaml
    if not config and os.path.exists("config.yaml"):
        with open("config.yaml", 'r') as f:
            config = yaml.safe_load(f) or {}

    return config


# =============================================================================
# OUTPUT GENERATION
# =============================================================================

def generate_video_ideas(opportunities: list, patterns: dict, num_ideas: int = 30) -> list:
    """
    Generate specific video title ideas from opportunities.
    """
    video_ideas = []

    # Title templates by content type
    templates = {
        "explainer": [
            "{query}: Complete Guide for Expats (2025)",
            "{query} - What You Need to Know",
            "The Truth About {query}",
        ],
        "comparison": [
            "{query}: Which Should You Choose?",
            "{query} - Honest Comparison",
        ],
        "tutorial": [
            "How to {query} (Step-by-Step)",
            "{query} - Beginner's Guide",
        ],
        "listicle": [
            "{query}: Complete Ranking",
            "Top {query} You Should Consider",
        ],
        "informational": [
            "{query}: What Expats Should Know",
            "{query} Explained Simply",
        ]
    }

    for opp in opportunities[:num_ideas]:
        query = opp["query"]
        content_type = opp["content_type"]

        # Clean up query for title
        title_query = query.title()

        # Select template
        template_list = templates.get(content_type, templates["informational"])
        title = template_list[0].format(query=title_query)

        video_ideas.append({
            "title": title,
            "source_query": query,
            "score": opp["score"],
            "content_type": content_type,
            "is_gap": opp["is_gap"],
            "search_frequency": opp["frequency"],
            "countries_mentioned": opp["classification"]["countries"],
            "visa_types_mentioned": opp["classification"]["visa_types"],
            "tax_terms_mentioned": opp["classification"]["tax_terms"],
        })

    return video_ideas


def save_results(results: dict, output_dir: str) -> dict:
    """
    Save analysis results to files.
    """
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save full JSON
    json_path = os.path.join(output_dir, f"google_search_analysis_{timestamp}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Save to SQLite for integration with YouTube analyzer
    db_path = os.path.join(output_dir, "search_demand.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT UNIQUE,
            score REAL,
            frequency INTEGER,
            content_type TEXT,
            is_gap BOOLEAN,
            countries TEXT,
            visa_types TEXT,
            tax_terms TEXT,
            sources TEXT,
            analyzed_at TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            source_query TEXT,
            score REAL,
            content_type TEXT,
            is_gap BOOLEAN,
            generated_at TEXT
        )
    ''')

    # Insert opportunities
    for opp in results.get("opportunities", []):
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO search_opportunities
                (query, score, frequency, content_type, is_gap, countries, visa_types, tax_terms, sources, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                opp["query"],
                opp["score"],
                opp["frequency"],
                opp["content_type"],
                opp["is_gap"],
                json.dumps(opp["classification"]["countries"]),
                json.dumps(opp["classification"]["visa_types"]),
                json.dumps(opp["classification"]["tax_terms"]),
                json.dumps(opp["sources"]),
                datetime.now().isoformat()
            ))
        except Exception:
            pass

    # Insert video ideas
    for idea in results.get("video_ideas", []):
        try:
            cursor.execute('''
                INSERT INTO video_ideas
                (title, source_query, score, content_type, is_gap, generated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                idea["title"],
                idea["source_query"],
                idea["score"],
                idea["content_type"],
                idea["is_gap"],
                datetime.now().isoformat()
            ))
        except Exception:
            pass

    conn.commit()
    conn.close()

    # Generate markdown report
    md_path = os.path.join(output_dir, f"google_search_report_{timestamp}.md")
    generate_markdown_report(results, md_path)

    return {
        "json": json_path,
        "database": db_path,
        "markdown": md_path
    }


def generate_markdown_report(results: dict, output_path: str):
    """
    Generate a readable markdown report.
    """
    lines = []

    lines.append("# Google Search Demand Analysis")
    lines.append(f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

    # Summary stats
    lines.append("## Summary\n")
    lines.append(f"- **Total search queries analyzed:** {results.get('total_suggestions', 0)}")
    lines.append(f"- **Video opportunities identified:** {len(results.get('opportunities', []))}")
    lines.append(f"- **Questions found:** {len(results.get('patterns', {}).get('questions', []))}")
    lines.append(f"- **Comparison searches:** {len(results.get('patterns', {}).get('comparisons', []))}")

    # Top video ideas
    lines.append("\n## Top Video Ideas (by search demand)\n")
    lines.append("| # | Video Title | Score | Type | Gap? |")
    lines.append("|---|-------------|-------|------|------|")

    for i, idea in enumerate(results.get("video_ideas", [])[:20], 1):
        gap_emoji = "Yes" if idea["is_gap"] else "No"
        lines.append(f"| {i} | {idea['title'][:60]} | {idea['score']:.0f} | {idea['content_type']} | {gap_emoji} |")

    # Top questions (People Also Ask style)
    lines.append("\n## Top Questions (PAA-style content)\n")
    for q in results.get("patterns", {}).get("questions", [])[:15]:
        lines.append(f"- {q['question']} (freq: {q['frequency']})")

    # Comparison opportunities
    lines.append("\n## Comparison Video Opportunities\n")
    for c in results.get("patterns", {}).get("comparisons", [])[:10]:
        lines.append(f"- {c['query']}")

    # Trending topics by category
    patterns = results.get("patterns", {})

    lines.append("\n## Search Demand by Country\n")
    for country, count in list(patterns.get("by_country", {}).items())[:15]:
        lines.append(f"- **{country.title()}**: {count} searches")

    lines.append("\n## Search Demand by Visa Type\n")
    for visa, count in list(patterns.get("by_visa_type", {}).items())[:10]:
        lines.append(f"- **{visa.title()}**: {count} searches")

    lines.append("\n## Search Demand by Tax Term\n")
    for tax, count in list(patterns.get("by_tax_term", {}).items())[:10]:
        lines.append(f"- **{tax.title()}**: {count} searches")

    # Google Trends data if available
    if results.get("trends_data", {}).get("data"):
        lines.append("\n## Google Trends Insights\n")
        for kw, data in results["trends_data"]["data"].items():
            trend_emoji = "Rising" if data.get("trend") == "rising" else "Stable"
            lines.append(f"- **{kw}**: {trend_emoji} (avg interest: {data.get('avg_interest', 0):.0f})")

    # Cyclical topics reigniting (peak -> trough -> recovery)
    cyclical = results.get("cyclical_topics", [])
    if cyclical:
        lines.append("\n## Cyclical Topics Reigniting (cover before competitors notice)\n")
        lines.append("| Keyword | Recovery | Recent Avg | Trough | All-Time Max | Latest Data |")
        lines.append("|---------|----------|------------|--------|--------------|-------------|")
        for c in cyclical[:20]:
            recovery = f"+{c['recovery_pct']:.0f}%" if c["recovery_pct"] is not None else "n/a"
            lines.append(
                f"| {c['keyword']} | {recovery} | {c['recent_avg']:.0f} | "
                f"{c['trough_value']:.0f} | {c['all_time_max']:.0f} | {c['latest_date']} |"
            )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def print_summary(results: dict):
    """
    Print a summary to the console.
    """
    print("\n" + "=" * 60)
    print("  GOOGLE SEARCH DEMAND ANALYSIS COMPLETE")
    print("=" * 60)

    print(f"\nTotal queries analyzed: {results.get('total_suggestions', 0)}")
    print(f"Video opportunities: {len(results.get('opportunities', []))}")

    print("\nTOP 10 VIDEO IDEAS:")
    print("-" * 60)

    for i, idea in enumerate(results.get("video_ideas", [])[:10], 1):
        gap = " [GAP]" if idea["is_gap"] else ""
        print(f"{i:2}. {idea['title'][:55]}{gap}")

    print("\nTOP QUESTIONS (PAA-style):")
    print("-" * 60)
    for q in results.get("patterns", {}).get("questions", [])[:5]:
        print(f"   - {q['question']}")

    print("\nHIGHEST DEMAND COUNTRIES:")
    for country, count in list(results.get("patterns", {}).get("by_country", {}).items())[:5]:
        print(f"   - {country.title()}: {count}")

    print("\nHIGHEST DEMAND VISA TYPES:")
    for visa, count in list(results.get("patterns", {}).get("by_visa_type", {}).items())[:5]:
        print(f"   - {visa.title()}: {count}")

    cyclical = results.get("cyclical_topics", [])
    if cyclical:
        print("\nCYCLICAL TOPICS REIGNITING (cover before competitors notice):")
        print("-" * 60)
        for c in cyclical[:10]:
            recovery = f"+{c['recovery_pct']:.0f}%" if c["recovery_pct"] is not None else "n/a"
            print(f"   - {c['keyword']}: {recovery} off trough (recent avg {c['recent_avg']:.0f} vs all-time max {c['all_time_max']:.0f})")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Analyze Google search demand for video topic opportunities"
    )

    parser.add_argument('--keywords', '-k', type=str,
                        help='Comma-separated seed keywords to analyze')
    parser.add_argument('--from-youtube', action='store_true',
                        help='Extract keywords from your YouTube channel analysis')
    parser.add_argument('--niche', type=str, default='expat',
                        choices=['expat', 'finance', 'travel', 'custom'],
                        help='Preset niche for seed keywords')
    parser.add_argument('--output', '-o', type=str, default=DEFAULT_OUTPUT_DIR,
                        help='Output directory')
    parser.add_argument('--trends', action='store_true',
                        help='Include Google Trends data (requires pytrends)')
    parser.add_argument('--countries', type=str, default='us,gb,de',
                        help='Countries for autocomplete (comma-separated)')
    parser.add_argument('--top-n', type=int, default=30,
                        help='Number of video ideas to generate')
    parser.add_argument('--trend-history', action='store_true',
                        help='Fetch multi-year Google Trends history and detect cyclical topics reigniting after a dip (requires pytrends)')
    parser.add_argument('--trend-history-timeframe', type=str, default='today 5-y',
                        help='pytrends timeframe for history fetch (default: "today 5-y")')
    parser.add_argument('--niche-config', type=str, default='niche_config.yaml',
                        help='Path to a niche config YAML (countries/visa/tax terms) - '
                             'point a second channel at its own file to run this tool for a different niche')

    args = parser.parse_args()

    if load_niche_config(args.niche_config):
        print(f"Loaded niche config from {args.niche_config}")

    # Determine seed keywords
    if args.keywords:
        seed_keywords = [k.strip() for k in args.keywords.split(',')]
    elif args.from_youtube:
        # Load from YouTube analyzer database
        db_path = os.path.join(args.output, "competitive_analysis.db")
        seed_keywords = get_channel_topics_from_db(db_path)
        if not seed_keywords:
            print("Could not extract topics from YouTube database. Using defaults.")
            seed_keywords = []
    else:
        seed_keywords = []

    # Add niche-specific keywords. Sourced from TOPIC_CATEGORIES (which
    # load_niche_config() has already swapped in-place for whatever
    # --niche-config was passed) rather than a hardcoded expat list, so a
    # second channel in a different niche doesn't get expat-tax keywords
    # injected into its seed set.
    if args.niche == 'expat' or not seed_keywords:
        niche_keywords = (
            TOPIC_CATEGORIES.get('visa_types', [])
            + TOPIC_CATEGORIES.get('tax_terms', [])
            + TOPIC_CATEGORIES.get('expat_lifestyle', [])
        )
        seed_keywords = list(set(seed_keywords + niche_keywords))

    print(f"\nSeed keywords: {len(seed_keywords)}")

    # Parse countries
    countries = [c.strip().lower() for c in args.countries.split(',')]

    # Gather autocomplete suggestions
    suggestions = gather_autocomplete_suggestions(seed_keywords, countries)
    print(f"\nTotal unique suggestions gathered: {len(suggestions)}")

    # Analyze patterns
    patterns = analyze_search_patterns(suggestions)

    # Get your topics for gap analysis
    db_path = os.path.join(args.output, "competitive_analysis.db")
    your_topics = get_channel_topics_from_db(db_path) if os.path.exists(db_path) else []

    # Score opportunities
    opportunities = score_video_opportunities(suggestions, patterns, your_topics)

    # Generate video ideas
    video_ideas = generate_video_ideas(opportunities, patterns, args.top_n)

    # Google Trends data (optional)
    trends_data = {}
    if args.trends and PYTRENDS_AVAILABLE:
        # Use top keywords for trends
        top_keywords = [opp["query"] for opp in opportunities[:10]]
        trends_data = get_google_trends_data(top_keywords[:5])  # Limit to 5

    search_db_path = os.path.join(args.output, "search_demand.db")

    # Append today's snapshot so repeat runs build first-party history
    if trends_data.get("data"):
        append_current_snapshot(search_db_path, trends_data["data"])

    # Trend-cycle history: fetch multi-year series and store (optional, uses pytrends quota)
    if args.trend_history and PYTRENDS_AVAILABLE:
        history_keywords = [opp["query"] for opp in opportunities[:15]]
        series_by_keyword = get_trends_time_series(history_keywords, args.trend_history_timeframe)
        if series_by_keyword:
            save_trends_history(search_db_path, series_by_keyword, args.trend_history_timeframe)

    # Detect cyclical topics from whatever history is already stored locally
    # (cheap, no API calls — runs every time regardless of --trend-history)
    cyclical_topics = detect_cyclical_topics(search_db_path)

    # Compile results
    results = {
        "generated_at": datetime.now().isoformat(),
        "seed_keywords": seed_keywords,
        "total_suggestions": len(suggestions),
        "patterns": patterns,
        "opportunities": opportunities[:100],  # Top 100
        "video_ideas": video_ideas,
        "trends_data": trends_data,
        "cyclical_topics": cyclical_topics,
    }

    # Save results
    output_files = save_results(results, args.output)

    # Print summary
    print_summary(results)

    print(f"\nOutput saved to:")
    print(f"  - {output_files['json']}")
    print(f"  - {output_files['database']}")
    print(f"  - {output_files['markdown']}")


if __name__ == "__main__":
    main()
