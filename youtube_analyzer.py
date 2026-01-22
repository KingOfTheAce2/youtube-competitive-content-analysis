#!/usr/bin/env python3
"""
YouTube Competitive Content Analysis Tool - Ultimate Edition

A powerful tool for analyzing YouTube channels to gain competitive insights,
identify content opportunities, and develop data-driven content strategies.

=== API KEY SETUP (FREE) ===
The YouTube Data API is free with 10,000 units/day quota.

Quick links:
  - Create project: https://console.cloud.google.com/projectcreate
  - Enable API:     https://console.cloud.google.com/apis/library/youtube.googleapis.com
  - Get API key:    https://console.cloud.google.com/apis/credentials

=== FEATURES ===
- Virality score & channel health score
- Title pattern analysis & hook scoring
- Shorts vs Long-form analytics
- Channel comparison & content gap analysis
- Historical trend tracking & growth rates
- Estimated revenue calculations
- Video series & collaboration detection
- Upload consistency scoring
- Seasonality analysis
- HTML dashboard with interactive charts
- Discord/Slack webhook alerts
- YAML config file support
- Multiple export formats (CSV, JSON, Excel, SQLite, Markdown, HTML)
- Interactive CLI mode

License: MIT
"""

import argparse
import csv
import hashlib
import json
import math
import os
import pickle
import random
import re
import signal
import sqlite3
import sys
import time
import urllib.request
import urllib.parse
import http.server
import socketserver
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Optional, Callable
from urllib.parse import urlparse, parse_qs

# Third-party imports
try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Error: pip install google-api-python-client")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

# PDF support (optional)
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Google Sheets support (optional)
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build as build_sheets
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False

# AI Provider support (optional)
ANTHROPIC_AVAILABLE = False
OPENAI_AVAILABLE = False
GEMINI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    pass

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    pass

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    pass


# =============================================================================
# CONSTANTS
# =============================================================================

MAX_RESULTS_PER_PAGE = 50
MAX_RETRIES = 5
BASE_RETRY_DELAY = 1

VIDEO_CATEGORIES = {
    '1': 'Film & Animation', '2': 'Autos & Vehicles', '10': 'Music',
    '15': 'Pets & Animals', '17': 'Sports', '18': 'Short Movies',
    '19': 'Travel & Events', '20': 'Gaming', '21': 'Videoblogging',
    '22': 'People & Blogs', '23': 'Comedy', '24': 'Entertainment',
    '25': 'News & Politics', '26': 'Howto & Style', '27': 'Education',
    '28': 'Science & Technology', '29': 'Nonprofits & Activism',
    '30': 'Movies', '31': 'Anime/Animation', '32': 'Action/Adventure',
    '33': 'Classics', '34': 'Comedy', '35': 'Documentary', '36': 'Drama',
    '37': 'Family', '38': 'Foreign', '39': 'Horror', '40': 'Sci-Fi/Fantasy',
    '41': 'Thriller', '42': 'Shorts', '43': 'Shows', '44': 'Trailers'
}

# Average CPM by category (USD per 1000 views) - estimates
CATEGORY_CPM = {
    'Film & Animation': 3.0, 'Autos & Vehicles': 4.5, 'Music': 1.5,
    'Pets & Animals': 2.5, 'Sports': 3.0, 'Travel & Events': 4.0,
    'Gaming': 2.5, 'People & Blogs': 2.0, 'Comedy': 2.5,
    'Entertainment': 2.5, 'News & Politics': 4.0, 'Howto & Style': 3.5,
    'Education': 4.0, 'Science & Technology': 5.0, 'Nonprofits & Activism': 2.0,
    'default': 2.5
}

EMOTIONAL_WORDS = {
    'shocking', 'amazing', 'incredible', 'unbelievable', 'insane', 'crazy',
    'mind-blowing', 'epic', 'ultimate', 'worst', 'best', 'top', 'secret',
    'hidden', 'revealed', 'truth', 'real', 'actual', 'finally', 'never',
    'always', 'must', 'need', 'stop', 'warning', 'danger', 'urgent',
    'breaking', 'exclusive', 'rare', 'impossible', 'perfect', 'horrible'
}

POWER_WORDS = {
    'free', 'new', 'proven', 'easy', 'simple', 'fast', 'quick', 'instant',
    'guaranteed', 'complete', 'essential', 'powerful', 'effective', 'official',
    'updated', 'latest', 'first', 'last', 'only', 'unique', 'limited'
}

COLLAB_INDICATORS = [
    'feat', 'ft.', 'featuring', 'with', 'collab', 'collaboration',
    'x ', ' x ', 'meets', 'vs', 'interview', 'guest', 'joined by'
]

# Video network discovery settings
MAX_RELATED_SEARCH_RESULTS = 25
MAX_COMPETITOR_CHANNELS = 20

SERIES_PATTERNS = [
    r'part\s*(\d+)', r'ep\.?\s*(\d+)', r'episode\s*(\d+)',
    r'#(\d+)', r'\|\s*(\d+)', r'-\s*(\d+)\s*$', r'vol\.?\s*(\d+)',
    r'chapter\s*(\d+)', r'day\s*(\d+)', r'week\s*(\d+)'
]

# Sentiment analysis keywords
POSITIVE_WORDS = {
    'love', 'great', 'amazing', 'awesome', 'excellent', 'fantastic', 'perfect',
    'best', 'beautiful', 'wonderful', 'incredible', 'brilliant', 'outstanding',
    'helpful', 'informative', 'inspiring', 'thank', 'thanks', 'appreciate',
    'good', 'nice', 'cool', 'interesting', 'useful', 'valuable', 'quality'
}

NEGATIVE_WORDS = {
    'hate', 'bad', 'terrible', 'awful', 'worst', 'horrible', 'poor', 'boring',
    'waste', 'disappointed', 'disappointing', 'clickbait', 'misleading', 'fake',
    'spam', 'scam', 'annoying', 'stupid', 'useless', 'wrong', 'lies', 'trash'
}

# Retention estimates by category and duration
RETENTION_BENCHMARKS = {
    'short': {'avg': 0.70, 'good': 0.80, 'excellent': 0.90},  # < 5 min
    'medium': {'avg': 0.50, 'good': 0.60, 'excellent': 0.70},  # 5-15 min
    'long': {'avg': 0.40, 'good': 0.50, 'excellent': 0.60},    # 15-30 min
    'very_long': {'avg': 0.30, 'good': 0.40, 'excellent': 0.50},  # > 30 min
}

# Niche benchmark defaults (can be overridden by building database)
DEFAULT_NICHE_BENCHMARKS = {
    'Science & Technology': {'avg_virality': 0.45, 'avg_engagement': 3.5, 'avg_ctr': 5.0},
    'Education': {'avg_virality': 0.40, 'avg_engagement': 3.0, 'avg_ctr': 4.5},
    'Gaming': {'avg_virality': 0.35, 'avg_engagement': 4.0, 'avg_ctr': 6.0},
    'Entertainment': {'avg_virality': 0.50, 'avg_engagement': 3.5, 'avg_ctr': 5.5},
    'Music': {'avg_virality': 0.60, 'avg_engagement': 2.5, 'avg_ctr': 4.0},
    'Howto & Style': {'avg_virality': 0.35, 'avg_engagement': 3.0, 'avg_ctr': 5.0},
    'default': {'avg_virality': 0.40, 'avg_engagement': 3.0, 'avg_ctr': 5.0},
}

# Title templates for A/B suggestions
TITLE_TEMPLATES = [
    "{number} {topic} That Will {benefit}",
    "How to {action} in {timeframe}",
    "Why {topic} is {adjective} (And What to Do About It)",
    "The Ultimate Guide to {topic}",
    "{topic}: Everything You Need to Know",
    "I Tried {topic} for {duration} - Here's What Happened",
    "{topic} vs {alternative}: Which is Better?",
    "Stop Making These {number} {topic} Mistakes",
    "The Truth About {topic} Nobody Tells You",
    "{topic} Tutorial for Beginners ({year})",
]

# Description section patterns
DESCRIPTION_SECTIONS = {
    'timestamps': r'(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—:]\s*(.+)',
    'links': r'https?://[^\s<>"{}|\\^`\[\]]+',
    'social_cta': r'(?:follow|subscribe|join|connect)\s+(?:me|us)?\s*(?:on|at)?\s*:?',
    'hashtags': r'#\w+',
    'discount_codes': r'(?:code|coupon|discount)[\s:]+([A-Z0-9]+)',
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def parse_duration(duration_str: str) -> int:
    if not duration_str:
        return 0
    pattern = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')
    match = pattern.match(duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def format_number(num: int) -> str:
    return f"{num:,}"


def format_currency(amount: float) -> str:
    return f"${amount:,.2f}"


def progress_bar(iterable, desc="Processing", total=None):
    if tqdm:
        return tqdm(iterable, desc=desc, total=total)
    return iterable


def retry_with_backoff(func, max_retries=MAX_RETRIES):
    for attempt in range(max_retries):
        try:
            return func()
        except HttpError as e:
            if e.resp.status in [429, 500, 503]:
                if attempt < max_retries - 1:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    print(f"\nAPI error {e.resp.status}, retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    raise
            else:
                raise


def safe_filename(name: str, max_length: int = 50) -> str:
    return re.sub(r'[^\w\-]', '_', name)[:max_length]


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    if not YAML_AVAILABLE:
        return {}
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except:
        return {}


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def analyze_title_patterns(title: str) -> dict:
    """Analyze title for viral patterns."""
    title_lower = title.lower()

    patterns = {
        'is_question': title.rstrip().endswith('?'),
        'starts_with_how': title_lower.startswith('how '),
        'starts_with_what': title_lower.startswith('what '),
        'starts_with_why': title_lower.startswith('why '),
        'has_number': bool(re.search(r'\d+', title)),
        'starts_with_number': bool(re.match(r'^\d+', title)),
        'has_year': bool(re.search(r'\b20[0-9]{2}\b', title)),
        'has_parentheses': '(' in title and ')' in title,
        'has_brackets': '[' in title and ']' in title,
        'all_caps_words': len(re.findall(r'\b[A-Z]{2,}\b', title)),
        'emotional_words_count': sum(1 for w in EMOTIONAL_WORDS if w in title_lower),
        'has_emotional_word': any(w in title_lower for w in EMOTIONAL_WORDS),
        'power_words_count': sum(1 for w in POWER_WORDS if w in title_lower),
        'has_power_word': any(w in title_lower for w in POWER_WORDS),
        'has_ellipsis': '...' in title,
        'has_exclamation': '!' in title,
        'has_vs': ' vs ' in title_lower or ' vs. ' in title_lower,
        'has_colon': ':' in title,
        'has_negative': any(w in title_lower for w in
                          ['don\'t', 'won\'t', 'can\'t', 'never', 'stop', 'worst', 'wrong', 'mistake']),
    }

    # Hook score
    indicators = [
        patterns['is_question'], patterns['has_number'],
        patterns['has_emotional_word'], patterns['has_power_word'],
        patterns['has_brackets'] or patterns['has_parentheses'],
        patterns['all_caps_words'] >= 2, patterns['has_ellipsis'],
        patterns['has_exclamation'],
    ]
    patterns['title_hook_score'] = sum(indicators)

    return patterns


def extract_title_formula(title: str) -> str:
    """Extract structural formula from title."""
    formula_parts = []
    if re.match(r'^\d+', title):
        formula_parts.append('NUMBER')
        title = re.sub(r'^\d+\s*', '', title)

    title_lower = title.lower()

    if title_lower.startswith('how to'):
        formula_parts.append('HOW TO')
    elif title_lower.startswith('why '):
        formula_parts.append('WHY')
    elif title_lower.startswith('what '):
        formula_parts.append('WHAT')
    elif 'vs' in title_lower:
        formula_parts.append('X VS Y')
    elif 'review' in title_lower:
        formula_parts.append('REVIEW')
    elif 'tutorial' in title_lower:
        formula_parts.append('TUTORIAL')
    elif 'explained' in title_lower:
        formula_parts.append('EXPLAINED')
    elif 'reaction' in title_lower:
        formula_parts.append('REACTION')

    if re.search(r'\b20[0-9]{2}\b', title):
        formula_parts.append('+ YEAR')
    if '(' in title:
        formula_parts.append('+ (CONTEXT)')
    if '[' in title:
        formula_parts.append('+ [TAG]')

    return ' '.join(formula_parts) if formula_parts else 'STANDARD'


def detect_series(title: str) -> dict:
    """Detect if video is part of a series."""
    title_lower = title.lower()

    for pattern in SERIES_PATTERNS:
        match = re.search(pattern, title_lower)
        if match:
            return {
                'is_series': True,
                'series_number': int(match.group(1)),
                'series_pattern': pattern
            }

    return {'is_series': False, 'series_number': None, 'series_pattern': None}


def detect_collaboration(title: str, description: str = "") -> dict:
    """Detect if video is a collaboration."""
    combined = (title + " " + description).lower()

    for indicator in COLLAB_INDICATORS:
        if indicator in combined:
            return {
                'is_collab': True,
                'collab_indicator': indicator
            }

    return {'is_collab': False, 'collab_indicator': None}


def calculate_virality_score(video: dict, channel_subscribers: int) -> float:
    """Calculate virality score."""
    if channel_subscribers == 0:
        return 0.0

    views = video.get('view_count', 0)

    try:
        publish_date = datetime.fromisoformat(video['publish_date'].replace('Z', '+00:00'))
        days_since = (datetime.now(publish_date.tzinfo) - publish_date).days
        days_since = max(days_since, 1)
    except:
        days_since = 30

    views_per_sub = views / channel_subscribers
    time_factor = (30 / days_since) ** 0.5 if days_since < 365 else 0.3

    return round(views_per_sub * time_factor, 4)


def estimate_revenue(video: dict, category: str = 'default') -> dict:
    """Estimate video revenue based on views and category."""
    views = video.get('view_count', 0)
    cpm = CATEGORY_CPM.get(category, CATEGORY_CPM['default'])

    # Assume 50-60% of views are monetized
    monetized_views = views * 0.55

    # Revenue estimates
    low_estimate = (monetized_views / 1000) * (cpm * 0.5)
    mid_estimate = (monetized_views / 1000) * cpm
    high_estimate = (monetized_views / 1000) * (cpm * 2.0)

    return {
        'estimated_revenue_low': round(low_estimate, 2),
        'estimated_revenue_mid': round(mid_estimate, 2),
        'estimated_revenue_high': round(high_estimate, 2),
        'cpm_used': cpm,
    }


def calculate_upload_consistency(videos: list[dict]) -> dict:
    """Calculate upload consistency score."""
    if len(videos) < 2:
        return {'consistency_score': 0, 'avg_days_between': 0, 'std_deviation': 0}

    dates = sorted([
        datetime.fromisoformat(v['publish_date'].replace('Z', '+00:00'))
        for v in videos
    ])

    gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]

    if not gaps:
        return {'consistency_score': 0, 'avg_days_between': 0, 'std_deviation': 0}

    avg_gap = sum(gaps) / len(gaps)
    variance = sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)
    std_dev = variance ** 0.5

    # Consistency score: lower std_dev = higher consistency
    # Score 0-100, where 100 is perfectly consistent
    if avg_gap > 0:
        coefficient_of_variation = std_dev / avg_gap
        consistency_score = max(0, min(100, 100 - (coefficient_of_variation * 50)))
    else:
        consistency_score = 100

    return {
        'consistency_score': round(consistency_score, 1),
        'avg_days_between': round(avg_gap, 1),
        'std_deviation': round(std_dev, 1),
        'total_gaps_analyzed': len(gaps),
    }


def calculate_channel_health_score(channel_info: dict, analytics: dict) -> dict:
    """Calculate overall channel health score (0-100)."""
    scores = {}

    # Engagement score (0-25)
    engagement = analytics.get('overview', {}).get('average_engagement_rate', 0)
    scores['engagement'] = min(25, engagement * 5)

    # Virality score (0-25)
    avg_virality = analytics.get('overview', {}).get('average_virality_score', 0)
    scores['virality'] = min(25, avg_virality * 25)

    # Consistency score (0-25)
    consistency = analytics.get('consistency', {}).get('consistency_score', 0)
    scores['consistency'] = consistency * 0.25

    # Growth score (0-25) - based on recent video performance
    viral_percentage = analytics.get('viral_videos', {}).get('percentage', 0)
    scores['growth'] = min(25, viral_percentage * 2.5)

    total_score = sum(scores.values())

    # Grade
    if total_score >= 90:
        grade = 'A+'
    elif total_score >= 80:
        grade = 'A'
    elif total_score >= 70:
        grade = 'B'
    elif total_score >= 60:
        grade = 'C'
    elif total_score >= 50:
        grade = 'D'
    else:
        grade = 'F'

    return {
        'total_score': round(total_score, 1),
        'grade': grade,
        'breakdown': {k: round(v, 1) for k, v in scores.items()},
    }


def analyze_seasonality(videos: list[dict]) -> dict:
    """Analyze performance by month/season with year-over-year comparison."""
    # Monthly data by month name only (for general patterns)
    monthly_data = defaultdict(lambda: {'views': [], 'virality': [], 'count': 0})
    # Year-month data (e.g., "2024-01" or "January 2024")
    year_month_data = defaultdict(lambda: {'views': [], 'virality': [], 'count': 0, 'videos': []})
    # Yearly data for YoY comparison
    yearly_data = defaultdict(lambda: {'views': [], 'virality': [], 'count': 0})

    for v in videos:
        try:
            pub_date = datetime.fromisoformat(v['publish_date'].replace('Z', '+00:00'))
            month = pub_date.strftime('%B')
            year = pub_date.year
            year_month_key = f"{month} {year}"

            # General monthly (all years combined)
            monthly_data[month]['views'].append(v['view_count'])
            monthly_data[month]['virality'].append(v.get('virality_score', 0))
            monthly_data[month]['count'] += 1

            # Specific year-month
            year_month_data[year_month_key]['views'].append(v['view_count'])
            year_month_data[year_month_key]['virality'].append(v.get('virality_score', 0))
            year_month_data[year_month_key]['count'] += 1
            year_month_data[year_month_key]['year'] = year
            year_month_data[year_month_key]['month'] = month
            year_month_data[year_month_key]['videos'].append(v['title'][:40])

            # Yearly totals
            yearly_data[year]['views'].append(v['view_count'])
            yearly_data[year]['virality'].append(v.get('virality_score', 0))
            yearly_data[year]['count'] += 1
        except:
            continue

    # General monthly performance (all years)
    monthly_performance = {}
    for month in ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']:
        if month in monthly_data and monthly_data[month]['count'] > 0:
            data = monthly_data[month]
            monthly_performance[month] = {
                'count': data['count'],
                'avg_views': sum(data['views']) // len(data['views']),
                'avg_virality': round(sum(data['virality']) / len(data['virality']), 4),
            }

    # Year-month performance (sorted by date)
    year_month_performance = {}
    for ym_key, data in sorted(year_month_data.items(),
                                key=lambda x: (x[1].get('year', 0),
                                             ['January', 'February', 'March', 'April', 'May', 'June',
                                              'July', 'August', 'September', 'October', 'November', 'December'].index(x[1].get('month', 'January')))):
        year_month_performance[ym_key] = {
            'year': data['year'],
            'month': data['month'],
            'count': data['count'],
            'total_views': sum(data['views']),
            'avg_views': sum(data['views']) // len(data['views']),
            'avg_virality': round(sum(data['virality']) / len(data['virality']), 4),
        }

    # Yearly performance
    yearly_performance = {}
    for year, data in sorted(yearly_data.items()):
        yearly_performance[year] = {
            'count': data['count'],
            'total_views': sum(data['views']),
            'avg_views': sum(data['views']) // len(data['views']),
            'avg_virality': round(sum(data['virality']) / len(data['virality']), 4),
        }

    # Year-over-Year comparison
    yoy_comparison = {}
    years = sorted(yearly_data.keys())
    for i in range(1, len(years)):
        prev_year = years[i-1]
        curr_year = years[i]
        prev_data = yearly_performance[prev_year]
        curr_data = yearly_performance[curr_year]

        views_change = ((curr_data['avg_views'] - prev_data['avg_views']) / max(prev_data['avg_views'], 1)) * 100
        virality_change = ((curr_data['avg_virality'] - prev_data['avg_virality']) / max(prev_data['avg_virality'], 0.001)) * 100
        count_change = ((curr_data['count'] - prev_data['count']) / max(prev_data['count'], 1)) * 100

        yoy_comparison[f"{prev_year} → {curr_year}"] = {
            'prev_year': prev_year,
            'curr_year': curr_year,
            'views_change_pct': round(views_change, 1),
            'virality_change_pct': round(virality_change, 1),
            'upload_change_pct': round(count_change, 1),
            'prev_avg_views': prev_data['avg_views'],
            'curr_avg_views': curr_data['avg_views'],
            'prev_uploads': prev_data['count'],
            'curr_uploads': curr_data['count'],
            'trend': 'up' if views_change > 10 else 'down' if views_change < -10 else 'stable',
        }

    # Best months
    best_by_views = max(monthly_performance.items(),
                        key=lambda x: x[1]['avg_views'])[0] if monthly_performance else None
    best_by_virality = max(monthly_performance.items(),
                           key=lambda x: x[1]['avg_virality'])[0] if monthly_performance else None

    # Season analysis
    seasons = {
        'Winter': ['December', 'January', 'February'],
        'Spring': ['March', 'April', 'May'],
        'Summer': ['June', 'July', 'August'],
        'Fall': ['September', 'October', 'November']
    }

    season_performance = {}
    for season, months in seasons.items():
        season_views = []
        season_virality = []
        for month in months:
            if month in monthly_performance:
                season_views.append(monthly_performance[month]['avg_views'])
                season_virality.append(monthly_performance[month]['avg_virality'])
        if season_views:
            season_performance[season] = {
                'avg_views': sum(season_views) // len(season_views),
                'avg_virality': round(sum(season_virality) / len(season_virality), 4),
            }

    return {
        'monthly_performance': monthly_performance,
        'year_month_performance': year_month_performance,
        'yearly_performance': yearly_performance,
        'yoy_comparison': yoy_comparison,
        'best_month_by_views': best_by_views,
        'best_month_by_virality': best_by_virality,
        'season_performance': season_performance,
        'best_season': max(season_performance.items(),
                          key=lambda x: x[1]['avg_views'])[0] if season_performance else None,
    }


def calculate_growth_rate(db_path: str, channel_id: str) -> dict:
    """Calculate growth rates from historical data."""
    if not os.path.exists(db_path):
        return {'error': 'No historical data'}

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT snapshot_date, subscriber_count, total_views, avg_virality
            FROM historical_snapshots
            WHERE channel_id = ?
            ORDER BY snapshot_date DESC
            LIMIT 30
        ''', (channel_id,))
        rows = cursor.fetchall()
        conn.close()

        if len(rows) < 2:
            return {'error': 'Insufficient historical data'}

        # Calculate growth rates
        latest = rows[0]
        oldest = rows[-1]

        days_diff = (datetime.fromisoformat(latest[0]) -
                    datetime.fromisoformat(oldest[0])).days or 1

        sub_growth = latest[1] - oldest[1]
        view_growth = latest[2] - oldest[2]

        return {
            'subscriber_growth': sub_growth,
            'subscriber_growth_rate': round(sub_growth / days_diff, 1),
            'view_growth': view_growth,
            'view_growth_rate': round(view_growth / days_diff, 0),
            'days_tracked': days_diff,
            'snapshots': len(rows),
        }
    except Exception as e:
        return {'error': str(e)}


def extract_links_from_description(description: str) -> dict:
    """Extract and categorize links from description."""
    if not description:
        return {
            'all_links': [],
            'social_links': {},
            'product_links': [],
            'other_links': [],
            'total_links': 0,
            'has_affiliate_links': False,
        }

    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    all_links = re.findall(url_pattern, description)

    social_platforms = {
        'twitter': ['twitter.com', 'x.com'],
        'instagram': ['instagram.com'],
        'tiktok': ['tiktok.com'],
        'facebook': ['facebook.com'],
        'discord': ['discord.gg', 'discord.com'],
        'patreon': ['patreon.com'],
    }

    social_links = defaultdict(list)
    product_links = []
    other_links = []

    affiliate_indicators = ['amzn.to', 'amazon.com', 'geni.us', 'bit.ly', 'linktr.ee']

    for link in all_links:
        link_lower = link.lower()
        categorized = False

        for platform, domains in social_platforms.items():
            if any(d in link_lower for d in domains):
                social_links[platform].append(link)
                categorized = True
                break

        if not categorized:
            if any(ind in link_lower for ind in affiliate_indicators):
                product_links.append(link)
            else:
                other_links.append(link)

    return {
        'all_links': all_links,
        'social_links': dict(social_links),
        'product_links': product_links,
        'other_links': other_links,
        'total_links': len(all_links),
        'has_affiliate_links': len(product_links) > 0,
    }


# =============================================================================
# ADVANCED ANALYTICS - TREND & VELOCITY
# =============================================================================

def calculate_trend_velocity(video: dict, channel_subscribers: int) -> dict:
    """
    Calculate trend velocity - how fast a video is gaining views.
    Higher velocity in first 48h indicates potential viral content.
    """
    try:
        publish_date = datetime.fromisoformat(video['publish_date'].replace('Z', '+00:00'))
        hours_since = max(1, (datetime.now(publish_date.tzinfo) - publish_date).total_seconds() / 3600)
        days_since = hours_since / 24
    except:
        hours_since = 24
        days_since = 1

    views = video.get('view_count', 0)
    likes = video.get('like_count', 0)

    # Views per hour
    views_per_hour = views / hours_since

    # Velocity score (normalized by subscriber count)
    if channel_subscribers > 0:
        velocity_score = (views_per_hour * 24) / channel_subscribers
    else:
        velocity_score = 0

    # Trend classification
    if days_since <= 2:  # First 48 hours
        if velocity_score > 0.5:
            trend_status = 'exploding'
        elif velocity_score > 0.2:
            trend_status = 'trending'
        elif velocity_score > 0.1:
            trend_status = 'gaining'
        else:
            trend_status = 'normal'
    elif days_since <= 7:  # First week
        if velocity_score > 0.2:
            trend_status = 'hot'
        elif velocity_score > 0.05:
            trend_status = 'active'
        else:
            trend_status = 'cooling'
    else:
        if velocity_score > 0.1:
            trend_status = 'evergreen'
        elif velocity_score > 0.01:
            trend_status = 'stable'
        else:
            trend_status = 'dormant'

    # Engagement velocity
    engagement_velocity = (likes / views * 100) if views > 0 else 0

    return {
        'views_per_hour': round(views_per_hour, 1),
        'views_per_day': round(views_per_hour * 24, 0),
        'velocity_score': round(velocity_score, 4),
        'trend_status': trend_status,
        'hours_since_publish': round(hours_since, 1),
        'engagement_velocity': round(engagement_velocity, 2),
        'is_new': days_since <= 7,
    }


def analyze_video_lifecycle(videos: list[dict]) -> dict:
    """
    Analyze how videos perform over their lifecycle.
    Groups videos by age and compares performance patterns.
    """
    lifecycle_data = {
        'first_day': [],      # 0-24h
        'first_week': [],     # 1-7 days
        'first_month': [],    # 7-30 days
        'mature': [],         # 30-90 days
        'evergreen': [],      # 90+ days
    }

    for v in videos:
        try:
            pub_date = datetime.fromisoformat(v['publish_date'].replace('Z', '+00:00'))
            days_old = (datetime.now(pub_date.tzinfo) - pub_date).days
        except:
            days_old = 30

        video_data = {
            'title': v['title'],
            'views': v['view_count'],
            'virality': v.get('virality_score', 0),
            'engagement': v.get('engagement_rate', 0),
            'days_old': days_old,
        }

        if days_old <= 1:
            lifecycle_data['first_day'].append(video_data)
        elif days_old <= 7:
            lifecycle_data['first_week'].append(video_data)
        elif days_old <= 30:
            lifecycle_data['first_month'].append(video_data)
        elif days_old <= 90:
            lifecycle_data['mature'].append(video_data)
        else:
            lifecycle_data['evergreen'].append(video_data)

    # Calculate averages for each stage
    lifecycle_summary = {}
    for stage, vids in lifecycle_data.items():
        if vids:
            lifecycle_summary[stage] = {
                'count': len(vids),
                'avg_views': sum(v['views'] for v in vids) // len(vids),
                'avg_virality': round(sum(v['virality'] for v in vids) / len(vids), 4),
                'avg_engagement': round(sum(v['engagement'] for v in vids) / len(vids), 2),
                'top_performer': max(vids, key=lambda x: x['views'])['title'][:50],
            }
        else:
            lifecycle_summary[stage] = {'count': 0}

    # Identify evergreen content (old but still performing)
    evergreen_videos = []
    for v in lifecycle_data['evergreen']:
        if v['virality'] > 0.3:  # Still getting good views relative to subs
            evergreen_videos.append(v)

    return {
        'lifecycle_stages': lifecycle_summary,
        'evergreen_content': evergreen_videos[:10],
        'total_evergreen': len(evergreen_videos),
    }


def estimate_retention(video: dict) -> dict:
    """
    Estimate video retention based on duration, category, and engagement patterns.
    """
    duration = video.get('duration_seconds', 0)
    engagement = video.get('engagement_rate', 0)
    category = video.get('category_name', 'default')

    # Determine duration bucket
    if duration <= 60:
        duration_type = 'shorts'
        base_retention = 0.85
    elif duration <= 300:
        duration_type = 'short'
        base_retention = RETENTION_BENCHMARKS['short']['avg']
    elif duration <= 900:
        duration_type = 'medium'
        base_retention = RETENTION_BENCHMARKS['medium']['avg']
    elif duration <= 1800:
        duration_type = 'long'
        base_retention = RETENTION_BENCHMARKS['long']['avg']
    else:
        duration_type = 'very_long'
        base_retention = RETENTION_BENCHMARKS['very_long']['avg']

    # Adjust based on engagement (higher engagement = better retention)
    engagement_multiplier = 1 + (engagement / 100)
    estimated_retention = min(0.95, base_retention * engagement_multiplier)

    # Estimate watch time
    estimated_watch_time = duration * estimated_retention

    # Quality rating
    if duration_type != 'shorts':
        benchmarks = RETENTION_BENCHMARKS.get(duration_type, RETENTION_BENCHMARKS['medium'])
        if estimated_retention >= benchmarks['excellent']:
            quality = 'excellent'
        elif estimated_retention >= benchmarks['good']:
            quality = 'good'
        else:
            quality = 'average'
    else:
        quality = 'shorts'

    return {
        'estimated_retention': round(estimated_retention, 2),
        'estimated_watch_time_seconds': round(estimated_watch_time, 0),
        'estimated_watch_time_formatted': format_duration(int(estimated_watch_time)),
        'duration_type': duration_type,
        'retention_quality': quality,
    }


def calculate_momentum_score(videos: list[dict], channel_info: dict) -> dict:
    """
    Calculate channel momentum - combines growth rate, recent virality, and consistency.
    """
    if not videos:
        return {'momentum_score': 0, 'momentum_grade': 'N/A'}

    # Recent videos (last 30 days)
    recent_videos = []
    for v in videos:
        try:
            pub_date = datetime.fromisoformat(v['publish_date'].replace('Z', '+00:00'))
            if (datetime.now(pub_date.tzinfo) - pub_date).days <= 30:
                recent_videos.append(v)
        except:
            pass

    # Components
    # 1. Recent activity score (0-25)
    activity_score = min(25, len(recent_videos) * 3)

    # 2. Recent virality score (0-25)
    if recent_videos:
        recent_virality = sum(v.get('virality_score', 0) for v in recent_videos) / len(recent_videos)
        virality_score = min(25, recent_virality * 25)
    else:
        virality_score = 0

    # 3. Trend direction score (0-25)
    if len(recent_videos) >= 3:
        # Compare first half vs second half
        mid = len(recent_videos) // 2
        first_half_avg = sum(v['view_count'] for v in recent_videos[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(v['view_count'] for v in recent_videos[mid:]) / (len(recent_videos) - mid) if len(recent_videos) > mid else 0

        if second_half_avg > first_half_avg * 1.2:
            trend_score = 25  # Growing
        elif second_half_avg > first_half_avg * 0.8:
            trend_score = 15  # Stable
        else:
            trend_score = 5   # Declining
    else:
        trend_score = 12.5  # Not enough data

    # 4. Engagement momentum (0-25)
    if recent_videos:
        recent_engagement = sum(v.get('engagement_rate', 0) for v in recent_videos) / len(recent_videos)
        engagement_score = min(25, recent_engagement * 5)
    else:
        engagement_score = 0

    total_score = activity_score + virality_score + trend_score + engagement_score

    # Grade
    if total_score >= 80:
        grade = 'A'
        status = 'Surging'
    elif total_score >= 60:
        grade = 'B'
        status = 'Growing'
    elif total_score >= 40:
        grade = 'C'
        status = 'Stable'
    elif total_score >= 20:
        grade = 'D'
        status = 'Slowing'
    else:
        grade = 'F'
        status = 'Stagnant'

    return {
        'momentum_score': round(total_score, 1),
        'momentum_grade': grade,
        'momentum_status': status,
        'breakdown': {
            'activity': round(activity_score, 1),
            'virality': round(virality_score, 1),
            'trend': round(trend_score, 1),
            'engagement': round(engagement_score, 1),
        },
        'recent_videos_count': len(recent_videos),
    }


def calculate_content_saturation(videos: list[dict], topic_keyword: str) -> dict:
    """
    Calculate how saturated a specific topic is in the channel's content.
    """
    keyword_lower = topic_keyword.lower()

    matching_videos = []
    for v in videos:
        title_lower = v['title'].lower()
        tags_lower = [t.lower() for t in v.get('tags', [])]

        if keyword_lower in title_lower or keyword_lower in tags_lower:
            matching_videos.append(v)

    if not matching_videos:
        return {
            'topic': topic_keyword,
            'saturation_level': 'none',
            'coverage_percentage': 0,
            'videos_count': 0,
        }

    coverage = len(matching_videos) / len(videos) * 100
    avg_virality = sum(v.get('virality_score', 0) for v in matching_videos) / len(matching_videos)

    # Saturation assessment
    if coverage > 30:
        if avg_virality > 0.8:
            saturation = 'high_performing'
        else:
            saturation = 'oversaturated'
    elif coverage > 15:
        saturation = 'well_covered'
    elif coverage > 5:
        saturation = 'moderate'
    else:
        saturation = 'underexplored'

    return {
        'topic': topic_keyword,
        'saturation_level': saturation,
        'coverage_percentage': round(coverage, 1),
        'videos_count': len(matching_videos),
        'avg_virality': round(avg_virality, 4),
        'recommendation': 'expand' if saturation in ['underexplored', 'moderate'] and avg_virality > 0.5
                          else 'maintain' if saturation == 'well_covered'
                          else 'reduce' if saturation == 'oversaturated'
                          else 'test',
    }


# =============================================================================
# VIDEO IDEA GENERATOR & CONTENT STRATEGY
# =============================================================================

def generate_video_ideas(videos: list[dict], analytics: dict, competitors_data: dict = None) -> dict:
    """
    Generate video ideas based on content gaps, trends, and high-performing patterns.
    """
    ideas = {
        'gap_based': [],
        'trend_based': [],
        'formula_based': [],
        'competitor_inspired': [],
        'remix_ideas': [],
    }

    # Extract successful patterns
    top_videos = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:20]

    # High-performing keywords
    hp_keywords = analytics.get('keyword_analysis', {}).get('high_performing_keywords', {})
    top_keywords = list(hp_keywords.keys())[:10]

    # High-performing formulas
    formulas = analytics.get('title_analysis', {}).get('common_formulas', {})

    # 1. Gap-based ideas (topics not covered recently)
    all_title_words = []
    recent_topics = set()

    for v in videos:
        words = re.findall(r'\b\w+\b', v['title'].lower())
        all_title_words.extend(words)

        try:
            pub_date = datetime.fromisoformat(v['publish_date'].replace('Z', '+00:00'))
            if (datetime.now(pub_date.tzinfo) - pub_date).days <= 90:
                recent_topics.update(words)
        except:
            pass

    # Find topics covered before but not recently
    old_topics = set(all_title_words) - recent_topics
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'it', 'how', 'what', 'why'}
    gap_topics = [t for t in old_topics if t not in stop_words and len(t) > 3][:5]

    for topic in gap_topics:
        ideas['gap_based'].append({
            'idea': f"Revisit '{topic.title()}' with updated information",
            'reason': 'Previously covered topic not addressed recently',
            'suggested_title': f"The Ultimate Guide to {topic.title()} ({datetime.now().year})",
        })

    # 2. Trend-based ideas (combine trending elements)
    if top_keywords:
        for i in range(min(3, len(top_keywords))):
            kw1 = top_keywords[i]
            kw2 = top_keywords[(i + 1) % len(top_keywords)] if len(top_keywords) > 1 else kw1
            ideas['trend_based'].append({
                'idea': f"Combine '{kw1}' with '{kw2}'",
                'reason': 'Both keywords perform well individually',
                'suggested_title': f"How {kw1.title()} Changes Everything About {kw2.title()}",
            })

    # 3. Formula-based ideas (apply successful formulas to new topics)
    best_formulas = [f for f, count in sorted(formulas.items(), key=lambda x: x[1], reverse=True)[:3]]

    formula_suggestions = {
        'NUMBER': "Create a listicle: '7 Things About [Topic]'",
        'HOW TO': "Create a tutorial: 'How to [Action] in [Timeframe]'",
        'WHY': "Create an explainer: 'Why [Topic] Matters'",
        'X VS Y': "Create a comparison: '[Option A] vs [Option B]'",
        'REVIEW': "Create a review: '[Product/Topic] Review'",
    }

    for formula in best_formulas:
        for key, suggestion in formula_suggestions.items():
            if key in formula:
                ideas['formula_based'].append({
                    'idea': suggestion,
                    'reason': f"Formula '{formula}' performs well on this channel",
                    'formula': formula,
                })
                break

    # 4. Competitor-inspired ideas
    if competitors_data and competitors_data.get('competitors', {}).get('competitors'):
        ideas['competitor_inspired'].append({
            'idea': "Analyze and respond to competitor content",
            'reason': "Competitor channels identified in your niche",
            'suggested_title': "My Response to [Competitor Topic] - Here's What They Got Wrong",
        })

    # 5. Remix ideas (combine top performing video elements)
    if len(top_videos) >= 2:
        v1 = top_videos[0]
        v2 = top_videos[1]
        ideas['remix_ideas'].append({
            'idea': f"Combine elements from '{v1['title'][:30]}...' and '{v2['title'][:30]}...'",
            'reason': 'Both are top performers - combining elements could work',
            'suggested_title': f"The Complete Guide: {v1['title'].split()[0]} + {v2['title'].split()[-1]}",
        })

    # Count total ideas
    total_ideas = sum(len(v) for v in ideas.values())

    return {
        'ideas': ideas,
        'total_ideas': total_ideas,
        'top_keywords_used': top_keywords[:5],
        'best_formulas': best_formulas,
    }


def generate_title_suggestions(video: dict, videos: list[dict]) -> dict:
    """
    Generate A/B title suggestions for a video based on successful patterns.
    """
    original_title = video['title']
    suggestions = []

    # Extract topic from title
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'it', 'how', 'what', 'why', 'i', 'my'}
    words = [w for w in re.findall(r'\b\w+\b', original_title.lower()) if w not in stop_words and len(w) > 2]
    main_topic = ' '.join(words[:3]).title() if words else 'Topic'

    # Get patterns from top videos
    top_videos = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:10]
    top_patterns = analyze_title_patterns(top_videos[0]['title']) if top_videos else {}

    # Generate suggestions based on different patterns
    current_year = datetime.now().year

    # Question format
    if not original_title.endswith('?'):
        suggestions.append({
            'title': f"Is {main_topic} Worth It? Here's The Truth",
            'pattern': 'question',
            'reason': 'Questions increase curiosity clicks',
        })

    # Number format
    if not re.search(r'\d+', original_title):
        suggestions.append({
            'title': f"7 {main_topic} Secrets Nobody Tells You",
            'pattern': 'number',
            'reason': 'Numbers set clear expectations',
        })

    # Brackets format
    if '[' not in original_title and '(' not in original_title:
        suggestions.append({
            'title': f"{main_topic} [{current_year} Complete Guide]",
            'pattern': 'brackets',
            'reason': 'Brackets add context and freshness',
        })

    # Emotional hook
    emotional_present = any(w in original_title.lower() for w in EMOTIONAL_WORDS)
    if not emotional_present:
        suggestions.append({
            'title': f"The Shocking Truth About {main_topic}",
            'pattern': 'emotional',
            'reason': 'Emotional words increase CTR',
        })

    # How-to format
    if not original_title.lower().startswith('how'):
        suggestions.append({
            'title': f"How to Master {main_topic} (Step-by-Step)",
            'pattern': 'how_to',
            'reason': 'How-to titles signal value',
        })

    return {
        'original_title': original_title,
        'suggestions': suggestions[:5],
        'title_score': video.get('title_hook_score', 0),
        'improvement_potential': 'high' if video.get('title_hook_score', 0) < 3 else 'medium' if video.get('title_hook_score', 0) < 5 else 'low',
    }


def build_content_calendar(analytics: dict, videos_per_week: int = 3) -> dict:
    """
    Generate an optimal content calendar based on performance patterns.
    """
    posting_schedule = analytics.get('posting_schedule', {})
    seasonality = analytics.get('seasonality', {})

    # Best days
    day_performance = posting_schedule.get('day_performance', {})
    days_ranked = sorted(day_performance.items(), key=lambda x: x[1].get('avg_virality', 0), reverse=True)

    # Best hours (estimate from data or use defaults)
    best_hours = [9, 12, 17]  # Default: morning, noon, evening

    # Generate calendar for next 4 weeks
    calendar = []
    current_date = datetime.now()

    day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}

    # Select best days for posting
    posting_days = [d[0] for d in days_ranked[:videos_per_week]] if days_ranked else ['Tuesday', 'Thursday', 'Saturday']

    for week in range(4):
        week_start = current_date + timedelta(weeks=week)

        for day_name in posting_days:
            day_num = day_map.get(day_name, 0)
            days_until = (day_num - week_start.weekday()) % 7
            post_date = week_start + timedelta(days=days_until)

            if post_date < current_date:
                post_date += timedelta(weeks=1)

            calendar.append({
                'date': post_date.strftime('%Y-%m-%d'),
                'day': day_name,
                'suggested_time': f"{best_hours[len(calendar) % len(best_hours)]:02d}:00 UTC",
                'week': week + 1,
                'performance_score': day_performance.get(day_name, {}).get('avg_virality', 0),
            })

    # Sort by date
    calendar.sort(key=lambda x: x['date'])

    # Monthly recommendations
    monthly_perf = seasonality.get('monthly_performance', {})
    current_month = datetime.now().strftime('%B')
    month_data = monthly_perf.get(current_month, {})

    return {
        'calendar': calendar[:12],  # Next 12 posting slots
        'posting_days': posting_days,
        'suggested_frequency': f"{videos_per_week} videos/week",
        'current_month_performance': {
            'month': current_month,
            'historical_avg_views': month_data.get('avg_views', 'N/A'),
            'historical_avg_virality': month_data.get('avg_virality', 'N/A'),
        },
        'best_season': seasonality.get('best_season', 'N/A'),
    }


def build_description_template(videos: list[dict]) -> dict:
    """
    Analyze top video descriptions and create an optimized template.
    """
    top_videos = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:20]

    # Analyze patterns
    has_timestamps = 0
    has_links = 0
    has_social = 0
    has_hashtags = 0
    has_discount = 0
    avg_length = 0
    common_phrases = []

    for v in top_videos:
        desc = v.get('description', '')
        avg_length += len(desc)

        if re.search(DESCRIPTION_SECTIONS['timestamps'], desc):
            has_timestamps += 1
        if re.search(DESCRIPTION_SECTIONS['links'], desc):
            has_links += 1
        if re.search(DESCRIPTION_SECTIONS['social_cta'], desc, re.I):
            has_social += 1
        if re.search(DESCRIPTION_SECTIONS['hashtags'], desc):
            has_hashtags += 1
        if re.search(DESCRIPTION_SECTIONS['discount_codes'], desc, re.I):
            has_discount += 1

    avg_length = avg_length // len(top_videos) if top_videos else 0

    # Build template
    template_parts = []

    template_parts.append("[HOOK: 1-2 sentences summarizing video value]")
    template_parts.append("")

    if has_timestamps > len(top_videos) * 0.3:
        template_parts.append("⏱️ TIMESTAMPS:")
        template_parts.append("0:00 - Introduction")
        template_parts.append("1:00 - [Section 1]")
        template_parts.append("5:00 - [Section 2]")
        template_parts.append("")

    if has_links > len(top_videos) * 0.5:
        template_parts.append("🔗 RESOURCES:")
        template_parts.append("• [Link 1]: [URL]")
        template_parts.append("• [Link 2]: [URL]")
        template_parts.append("")

    if has_social > len(top_videos) * 0.4:
        template_parts.append("📱 CONNECT WITH ME:")
        template_parts.append("• Twitter: [URL]")
        template_parts.append("• Instagram: [URL]")
        template_parts.append("")

    if has_discount > len(top_videos) * 0.2:
        template_parts.append("🎁 EXCLUSIVE OFFERS:")
        template_parts.append("• Use code [CODE] for [X]% off")
        template_parts.append("")

    if has_hashtags > len(top_videos) * 0.3:
        template_parts.append("#[topic] #[niche] #[year]")

    return {
        'template': '\n'.join(template_parts),
        'recommendations': {
            'use_timestamps': has_timestamps > len(top_videos) * 0.3,
            'include_links': has_links > len(top_videos) * 0.5,
            'add_social': has_social > len(top_videos) * 0.4,
            'use_hashtags': has_hashtags > len(top_videos) * 0.3,
            'optimal_length': f"{avg_length} characters",
        },
        'pattern_analysis': {
            'videos_with_timestamps': f"{has_timestamps}/{len(top_videos)}",
            'videos_with_links': f"{has_links}/{len(top_videos)}",
            'videos_with_social': f"{has_social}/{len(top_videos)}",
            'videos_with_hashtags': f"{has_hashtags}/{len(top_videos)}",
        }
    }


def analyze_thumbnail_patterns(videos: list[dict]) -> dict:
    """
    Analyze thumbnail URLs and patterns from successful videos.
    Note: Full image analysis would require additional libraries.
    """
    top_videos = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:30]

    thumbnails = []
    for v in top_videos:
        thumb_url = v.get('thumbnail_maxres') or v.get('thumbnail_high') or v.get('thumbnail_default')
        if thumb_url:
            thumbnails.append({
                'video_id': v['video_id'],
                'title': v['title'],
                'thumbnail_url': thumb_url,
                'views': v['view_count'],
                'virality': v.get('virality_score', 0),
            })

    # Patterns we can detect from titles (proxy for thumbnail content)
    has_face_indicator = 0  # Words suggesting face in thumb
    has_text_indicator = 0   # All caps words suggesting text overlay
    has_emotion_indicator = 0

    face_words = {'reaction', 'face', 'shocked', 'surprised', 'crying', 'laughing'}
    emotion_words = {'😱', '😂', '🤯', '!', '?'}

    for v in top_videos:
        title_lower = v['title'].lower()
        if any(fw in title_lower for fw in face_words):
            has_face_indicator += 1
        if re.search(r'\b[A-Z]{3,}\b', v['title']):
            has_text_indicator += 1
        if any(ew in v['title'] for ew in emotion_words):
            has_emotion_indicator += 1

    return {
        'top_thumbnails': thumbnails[:10],
        'patterns_detected': {
            'likely_has_faces': f"{has_face_indicator}/{len(top_videos)} top videos",
            'likely_has_text_overlay': f"{has_text_indicator}/{len(top_videos)} top videos",
            'emotional_indicators': f"{has_emotion_indicator}/{len(top_videos)} top videos",
        },
        'recommendations': [
            "Use high-contrast colors for visibility",
            "Include faces showing emotion when relevant",
            "Add 2-4 words of text overlay",
            "Maintain consistent branding/style",
            "Test different thumbnail styles",
        ],
        'download_command': f"python youtube_analyzer.py @channel --thumbnails",
    }


# =============================================================================
# SENTIMENT & COMMENTS ANALYSIS
# =============================================================================

def analyze_comment_sentiment(comments: list[str]) -> dict:
    """
    Simple sentiment analysis on comments using keyword matching.
    """
    if not comments:
        return {'sentiment_score': 0, 'sentiment_label': 'neutral', 'analyzed': 0}

    positive_count = 0
    negative_count = 0
    neutral_count = 0

    for comment in comments:
        comment_lower = comment.lower()
        pos = sum(1 for w in POSITIVE_WORDS if w in comment_lower)
        neg = sum(1 for w in NEGATIVE_WORDS if w in comment_lower)

        if pos > neg:
            positive_count += 1
        elif neg > pos:
            negative_count += 1
        else:
            neutral_count += 1

    total = len(comments)
    sentiment_score = (positive_count - negative_count) / total if total > 0 else 0

    if sentiment_score > 0.3:
        label = 'very_positive'
    elif sentiment_score > 0.1:
        label = 'positive'
    elif sentiment_score > -0.1:
        label = 'neutral'
    elif sentiment_score > -0.3:
        label = 'negative'
    else:
        label = 'very_negative'

    return {
        'sentiment_score': round(sentiment_score, 3),
        'sentiment_label': label,
        'positive_count': positive_count,
        'negative_count': negative_count,
        'neutral_count': neutral_count,
        'analyzed': total,
    }


def fetch_video_comments(youtube, video_id: str, max_comments: int = 100) -> list[str]:
    """
    Fetch comments for a video (requires additional API quota).
    """
    try:
        comments = []
        next_page = None

        while len(comments) < max_comments:
            response = retry_with_backoff(lambda: youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=min(100, max_comments - len(comments)),
                pageToken=next_page,
                textFormat='plainText'
            ).execute())

            for item in response.get('items', []):
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(comment)

            next_page = response.get('nextPageToken')
            if not next_page:
                break

        return comments
    except Exception as e:
        return []


# =============================================================================
# COLLABORATION & AUDIENCE ANALYSIS
# =============================================================================

def calculate_collab_roi(videos: list[dict]) -> dict:
    """
    Calculate ROI of collaborations vs solo content.
    """
    collab_videos = [v for v in videos if v.get('is_collab')]
    solo_videos = [v for v in videos if not v.get('is_collab')]

    if not collab_videos or not solo_videos:
        return {
            'has_data': False,
            'collab_count': len(collab_videos),
            'solo_count': len(solo_videos),
        }

    collab_avg_views = sum(v['view_count'] for v in collab_videos) // len(collab_videos)
    solo_avg_views = sum(v['view_count'] for v in solo_videos) // len(solo_videos)

    collab_avg_virality = sum(v.get('virality_score', 0) for v in collab_videos) / len(collab_videos)
    solo_avg_virality = sum(v.get('virality_score', 0) for v in solo_videos) / len(solo_videos)

    view_lift = ((collab_avg_views - solo_avg_views) / solo_avg_views * 100) if solo_avg_views > 0 else 0
    virality_lift = ((collab_avg_virality - solo_avg_virality) / solo_avg_virality * 100) if solo_avg_virality > 0 else 0

    # Top collab partners (from titles)
    collab_partners = []
    for v in collab_videos:
        for indicator in COLLAB_INDICATORS:
            if indicator in v['title'].lower():
                # Try to extract partner name
                parts = re.split(r'\s+(?:feat|ft\.?|featuring|with|x)\s+', v['title'], flags=re.I)
                if len(parts) > 1:
                    collab_partners.append(parts[1].split()[0])

    return {
        'has_data': True,
        'collab_count': len(collab_videos),
        'solo_count': len(solo_videos),
        'collab_avg_views': collab_avg_views,
        'solo_avg_views': solo_avg_views,
        'view_lift_percentage': round(view_lift, 1),
        'collab_avg_virality': round(collab_avg_virality, 4),
        'solo_avg_virality': round(solo_avg_virality, 4),
        'virality_lift_percentage': round(virality_lift, 1),
        'recommendation': 'increase_collabs' if view_lift > 20 else 'maintain' if view_lift > -10 else 'focus_solo',
        'top_collab_indicators': Counter(collab_partners).most_common(5),
    }


def estimate_audience_overlap(channel1_videos: list[dict], channel2_videos: list[dict]) -> dict:
    """
    Estimate audience overlap based on content similarity.
    """
    def extract_keywords(videos):
        keywords = []
        for v in videos:
            words = re.findall(r'\b\w+\b', v['title'].lower())
            keywords.extend([w for w in words if len(w) > 3])
            keywords.extend([t.lower() for t in v.get('tags', [])])
        return set(keywords)

    kw1 = extract_keywords(channel1_videos)
    kw2 = extract_keywords(channel2_videos)

    if not kw1 or not kw2:
        return {'overlap_score': 0, 'shared_keywords': []}

    intersection = kw1 & kw2
    union = kw1 | kw2

    jaccard_similarity = len(intersection) / len(union) if union else 0

    # Category overlap
    cats1 = Counter(v['category_name'] for v in channel1_videos)
    cats2 = Counter(v['category_name'] for v in channel2_videos)

    category_overlap = len(set(cats1.keys()) & set(cats2.keys())) / len(set(cats1.keys()) | set(cats2.keys())) if cats1 or cats2 else 0

    # Combined score
    overlap_score = (jaccard_similarity * 0.7 + category_overlap * 0.3) * 100

    return {
        'overlap_score': round(overlap_score, 1),
        'keyword_similarity': round(jaccard_similarity * 100, 1),
        'category_similarity': round(category_overlap * 100, 1),
        'shared_keywords': list(intersection)[:20],
        'interpretation': 'high_overlap' if overlap_score > 50 else 'moderate_overlap' if overlap_score > 25 else 'low_overlap',
    }


def analyze_competitor_traffic_opportunities(
    your_videos: list[dict],
    your_channel: dict,
    competitor_videos: list[dict],
    competitor_channel: dict
) -> dict:
    """
    Analyze competitor's content to find traffic capture opportunities.
    Identifies content gaps, keyword opportunities, and video ideas that
    could help you rank for searches currently going to the competitor.
    """

    # Extract keywords and tags from both channels
    def extract_content_data(videos):
        keywords = Counter()
        tags = Counter()
        topics = Counter()
        title_patterns = []

        for v in videos:
            # Title keywords
            words = re.findall(r'\b\w+\b', v['title'].lower())
            words = [w for w in words if len(w) > 3 and w not in {'this', 'that', 'with', 'from', 'have', 'will', 'your', 'what', 'when', 'where', 'which', 'their', 'there', 'would', 'could', 'should', 'about', 'into', 'more', 'some', 'than', 'them', 'then', 'these', 'they', 'were', 'been', 'being', 'each', 'very', 'just', 'over', 'such', 'only'}]

            # Weight by performance
            weight = 1 + (v.get('virality_score', 0) * 2)
            for w in words:
                keywords[w] += weight

            # Tags
            for t in v.get('tags', []):
                tags[t.lower()] += weight

            # Topic extraction from title
            topic = ' '.join(words[:3]) if words else ''
            if topic:
                topics[topic] += v.get('view_count', 0)

            # Title patterns
            title_patterns.append({
                'title': v['title'],
                'views': v.get('view_count', 0),
                'virality': v.get('virality_score', 0),
                'has_number': bool(re.search(r'\d+', v['title'])),
                'has_question': '?' in v['title'],
                'has_how_to': bool(re.search(r'\b(how|why|what|when|where)\b', v['title'].lower())),
                'length': len(v['title']),
            })

        return keywords, tags, topics, title_patterns

    your_keywords, your_tags, your_topics, your_patterns = extract_content_data(your_videos)
    comp_keywords, comp_tags, comp_topics, comp_patterns = extract_content_data(competitor_videos)

    # 1. Keyword Gap Analysis - Keywords competitor ranks for that you don't cover
    keyword_gaps = []
    for kw, score in comp_keywords.most_common(100):
        if kw not in your_keywords or your_keywords[kw] < score * 0.3:
            keyword_gaps.append({
                'keyword': kw,
                'competitor_score': round(score, 1),
                'your_score': round(your_keywords.get(kw, 0), 1),
                'opportunity': 'high' if score > 10 else 'medium' if score > 5 else 'low',
            })

    # 2. Tag Opportunities - Tags that work for competitor
    tag_opportunities = []
    for tag, score in comp_tags.most_common(50):
        if tag not in your_tags or your_tags[tag] < score * 0.5:
            tag_opportunities.append({
                'tag': tag,
                'competitor_usage': round(score, 1),
                'your_usage': round(your_tags.get(tag, 0), 1),
            })

    # 3. Viral Content You Haven't Covered
    viral_gaps = []
    your_topic_set = set(' '.join(re.findall(r'\b\w+\b', v['title'].lower())[:5]) for v in your_videos)

    for v in sorted(competitor_videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:30]:
        topic_words = ' '.join(re.findall(r'\b\w+\b', v['title'].lower())[:5])

        # Check if you have similar content
        has_similar = any(
            len(set(topic_words.split()) & set(yt.split())) >= 2
            for yt in your_topic_set
        )

        if not has_similar and v.get('virality_score', 0) > 0.5:
            viral_gaps.append({
                'competitor_title': v['title'],
                'views': v['view_count'],
                'virality': v.get('virality_score', 0),
                'publish_date': v['publish_date'][:10],
                'url': f"https://www.youtube.com/watch?v={v['video_id']}",
                'suggested_angle': f"Create your version covering: {topic_words}",
            })

    # 4. Title Pattern Analysis - What works for competitor
    comp_viral_patterns = [p for p in comp_patterns if p['virality'] > 0.8]

    pattern_insights = {
        'avg_title_length': round(sum(p['length'] for p in comp_viral_patterns) / len(comp_viral_patterns)) if comp_viral_patterns else 0,
        'percent_with_numbers': round(sum(1 for p in comp_viral_patterns if p['has_number']) / len(comp_viral_patterns) * 100) if comp_viral_patterns else 0,
        'percent_questions': round(sum(1 for p in comp_viral_patterns if p['has_question']) / len(comp_viral_patterns) * 100) if comp_viral_patterns else 0,
        'percent_how_to': round(sum(1 for p in comp_viral_patterns if p['has_how_to']) / len(comp_viral_patterns) * 100) if comp_viral_patterns else 0,
    }

    # Compare to your patterns
    your_viral_patterns = [p for p in your_patterns if p['virality'] > 0.8]
    your_pattern_insights = {
        'avg_title_length': round(sum(p['length'] for p in your_viral_patterns) / len(your_viral_patterns)) if your_viral_patterns else 0,
        'percent_with_numbers': round(sum(1 for p in your_viral_patterns if p['has_number']) / len(your_viral_patterns) * 100) if your_viral_patterns else 0,
        'percent_questions': round(sum(1 for p in your_viral_patterns if p['has_question']) / len(your_viral_patterns) * 100) if your_viral_patterns else 0,
        'percent_how_to': round(sum(1 for p in your_viral_patterns if p['has_how_to']) / len(your_viral_patterns) * 100) if your_viral_patterns else 0,
    }

    # 5. Generate Specific Video Ideas to Capture Traffic
    video_ideas = []

    # Ideas from keyword gaps
    for gap in keyword_gaps[:10]:
        if gap['opportunity'] == 'high':
            video_ideas.append({
                'type': 'keyword_opportunity',
                'idea': f"Create content targeting '{gap['keyword']}'",
                'reason': f"Competitor scores {gap['competitor_score']:.0f} on this keyword, you score {gap['your_score']:.0f}",
                'priority': 'high',
            })

    # Ideas from viral gaps
    for gap in viral_gaps[:5]:
        video_ideas.append({
            'type': 'viral_gap',
            'idea': gap['suggested_angle'],
            'reason': f"Competitor got {format_number(gap['views'])} views (virality: {gap['virality']:.2f})",
            'reference': gap['url'],
            'priority': 'high',
        })

    # Ideas from tag opportunities
    top_tags = [t['tag'] for t in tag_opportunities[:5]]
    if top_tags:
        video_ideas.append({
            'type': 'tag_opportunity',
            'idea': f"Create content using tags: {', '.join(top_tags)}",
            'reason': 'These tags perform well for competitor but you underutilize them',
            'priority': 'medium',
        })

    # 6. Performance Comparison
    your_avg_views = sum(v['view_count'] for v in your_videos) / len(your_videos) if your_videos else 0
    comp_avg_views = sum(v['view_count'] for v in competitor_videos) / len(competitor_videos) if competitor_videos else 0

    your_avg_virality = sum(v.get('virality_score', 0) for v in your_videos) / len(your_videos) if your_videos else 0
    comp_avg_virality = sum(v.get('virality_score', 0) for v in competitor_videos) / len(competitor_videos) if competitor_videos else 0

    comparison = {
        'your_channel': {
            'name': your_channel.get('title', 'Your Channel'),
            'subscribers': your_channel.get('subscriber_count', 0),
            'avg_views': round(your_avg_views),
            'avg_virality': round(your_avg_virality, 3),
            'total_videos': len(your_videos),
        },
        'competitor': {
            'name': competitor_channel.get('title', 'Competitor'),
            'subscribers': competitor_channel.get('subscriber_count', 0),
            'avg_views': round(comp_avg_views),
            'avg_virality': round(comp_avg_virality, 3),
            'total_videos': len(competitor_videos),
        },
        'you_vs_competitor': {
            'subscriber_ratio': round(your_channel.get('subscriber_count', 1) / max(competitor_channel.get('subscriber_count', 1), 1), 2),
            'views_ratio': round(your_avg_views / max(comp_avg_views, 1), 2),
            'virality_ratio': round(your_avg_virality / max(comp_avg_virality, 0.001), 2),
        }
    }

    # 7. Action Plan
    action_plan = []

    if len(viral_gaps) > 3:
        action_plan.append({
            'priority': 1,
            'action': f"Create videos on {len(viral_gaps)} topics competitor went viral on that you haven't covered",
            'expected_impact': 'high',
        })

    if pattern_insights['percent_with_numbers'] > your_pattern_insights['percent_with_numbers'] + 20:
        action_plan.append({
            'priority': 2,
            'action': f"Use more numbers in titles (competitor: {pattern_insights['percent_with_numbers']}%, you: {your_pattern_insights['percent_with_numbers']}%)",
            'expected_impact': 'medium',
        })

    if pattern_insights['percent_how_to'] > your_pattern_insights['percent_how_to'] + 20:
        action_plan.append({
            'priority': 2,
            'action': f"Create more how-to/educational content (competitor: {pattern_insights['percent_how_to']}%, you: {your_pattern_insights['percent_how_to']}%)",
            'expected_impact': 'medium',
        })

    if len(tag_opportunities) > 10:
        action_plan.append({
            'priority': 3,
            'action': f"Adopt {len(tag_opportunities[:15])} high-performing tags from competitor",
            'expected_impact': 'medium',
        })

    if comparison['you_vs_competitor']['virality_ratio'] < 0.8:
        action_plan.append({
            'priority': 3,
            'action': 'Study competitor thumbnail and title patterns - their virality is higher',
            'expected_impact': 'medium',
        })

    return {
        'summary': {
            'keyword_gaps_found': len(keyword_gaps),
            'tag_opportunities': len(tag_opportunities),
            'viral_content_gaps': len(viral_gaps),
            'video_ideas_generated': len(video_ideas),
        },
        'keyword_gaps': keyword_gaps[:20],
        'tag_opportunities': tag_opportunities[:20],
        'viral_gaps': viral_gaps[:10],
        'title_patterns': {
            'competitor': pattern_insights,
            'yours': your_pattern_insights,
        },
        'video_ideas': video_ideas,
        'comparison': comparison,
        'action_plan': sorted(action_plan, key=lambda x: x['priority']),
    }


def format_traffic_analysis(analysis: dict) -> str:
    """Format traffic capture analysis for display."""
    lines = []

    lines.append("\n" + "=" * 60)
    lines.append("🎯 COMPETITOR TRAFFIC CAPTURE ANALYSIS")
    lines.append("=" * 60)

    # Summary
    summary = analysis['summary']
    lines.append(f"\n📊 Summary:")
    lines.append(f"   • Keyword gaps found: {summary['keyword_gaps_found']}")
    lines.append(f"   • Tag opportunities: {summary['tag_opportunities']}")
    lines.append(f"   • Viral content gaps: {summary['viral_content_gaps']}")
    lines.append(f"   • Video ideas generated: {summary['video_ideas_generated']}")

    # Comparison
    comp = analysis['comparison']
    lines.append(f"\n📈 Channel Comparison:")
    lines.append(f"   Your Channel: {comp['your_channel']['name']}")
    lines.append(f"      Subscribers: {format_number(comp['your_channel']['subscribers'])}")
    lines.append(f"      Avg Views: {format_number(comp['your_channel']['avg_views'])}")
    lines.append(f"      Avg Virality: {comp['your_channel']['avg_virality']:.3f}")
    lines.append(f"   Competitor: {comp['competitor']['name']}")
    lines.append(f"      Subscribers: {format_number(comp['competitor']['subscribers'])}")
    lines.append(f"      Avg Views: {format_number(comp['competitor']['avg_views'])}")
    lines.append(f"      Avg Virality: {comp['competitor']['avg_virality']:.3f}")

    # Top keyword gaps
    if analysis['keyword_gaps']:
        lines.append(f"\n🔑 Top Keyword Gaps (competitor ranks, you don't):")
        for gap in analysis['keyword_gaps'][:10]:
            lines.append(f"   • '{gap['keyword']}' - opportunity: {gap['opportunity']}")

    # Viral content gaps
    if analysis['viral_gaps']:
        lines.append(f"\n🔥 Viral Content You Haven't Covered:")
        for gap in analysis['viral_gaps'][:5]:
            lines.append(f"   • \"{gap['competitor_title'][:50]}...\"")
            lines.append(f"     Views: {format_number(gap['views'])} | Virality: {gap['virality']:.2f}")
            lines.append(f"     → {gap['suggested_angle']}")

    # Title patterns
    patterns = analysis['title_patterns']
    lines.append(f"\n📝 Title Pattern Comparison:")
    lines.append(f"   Competitor viral titles: {patterns['competitor']['percent_with_numbers']}% use numbers, {patterns['competitor']['percent_how_to']}% are how-to")
    lines.append(f"   Your viral titles: {patterns['yours']['percent_with_numbers']}% use numbers, {patterns['yours']['percent_how_to']}% are how-to")

    # Video ideas
    if analysis['video_ideas']:
        lines.append(f"\n💡 Video Ideas to Capture Traffic:")
        for i, idea in enumerate(analysis['video_ideas'][:5], 1):
            lines.append(f"   {i}. [{idea['priority'].upper()}] {idea['idea']}")
            lines.append(f"      Reason: {idea['reason']}")

    # Action plan
    if analysis['action_plan']:
        lines.append(f"\n🎬 Action Plan:")
        for action in analysis['action_plan']:
            lines.append(f"   [{action['priority']}] {action['action']}")
            lines.append(f"       Expected impact: {action['expected_impact']}")

    lines.append("\n" + "=" * 60)

    return '\n'.join(lines)


def generate_traffic_analysis_html(analysis: dict, output_path: str) -> None:
    """Generate HTML report for traffic capture analysis."""

    summary = analysis['summary']
    comp = analysis['comparison']
    patterns = analysis['title_patterns']

    # Determine who's winning
    your_virality = comp['your_channel']['avg_virality']
    their_virality = comp['competitor']['avg_virality']
    virality_diff = ((your_virality - their_virality) / max(their_virality, 0.001)) * 100

    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Traffic Capture Analysis: {comp['your_channel']['name']} vs {comp['competitor']['name']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e2e8f0;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{
            text-align: center;
            margin-bottom: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.5em;
        }}
        .subtitle {{ text-align: center; color: #a0aec0; margin-bottom: 40px; }}

        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .card h3 {{ color: #a0aec0; font-size: 0.9em; margin-bottom: 10px; }}
        .card .value {{ font-size: 2.5em; font-weight: bold; color: #667eea; }}
        .card .subvalue {{ font-size: 0.85em; color: #a0aec0; margin-top: 5px; }}

        .section {{
            background: rgba(255,255,255,0.03);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .section h2 {{ color: #667eea; margin-bottom: 20px; font-size: 1.5em; }}
        .section h3 {{ color: #a0aec0; margin: 20px 0 15px 0; font-size: 1.1em; }}

        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        th {{ background: rgba(102,126,234,0.2); color: #667eea; font-weight: 600; }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}

        .opportunity-high {{ color: #38ef7d; font-weight: bold; }}
        .opportunity-medium {{ color: #ffc107; }}
        .opportunity-low {{ color: #a0aec0; }}

        .priority-high {{ background: rgba(56,239,125,0.2); color: #38ef7d; padding: 3px 10px; border-radius: 12px; font-size: 0.8em; }}
        .priority-medium {{ background: rgba(255,193,7,0.2); color: #ffc107; padding: 3px 10px; border-radius: 12px; font-size: 0.8em; }}

        .comparison-box {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin: 20px 0;
        }}
        .channel-stats {{
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 20px;
        }}
        .channel-stats h4 {{ color: #667eea; margin-bottom: 15px; font-size: 1.2em; }}
        .stat-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        .stat-label {{ color: #a0aec0; }}
        .stat-value {{ font-weight: bold; }}

        .viral-card {{
            background: rgba(255,107,107,0.1);
            border: 1px solid rgba(255,107,107,0.3);
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
        }}
        .viral-card h4 {{ color: #ff6b6b; margin-bottom: 10px; }}
        .viral-card .views {{ color: #38ef7d; font-weight: bold; }}
        .viral-card .suggestion {{
            background: rgba(102,126,234,0.2);
            padding: 10px 15px;
            border-radius: 8px;
            margin-top: 10px;
            border-left: 3px solid #667eea;
        }}

        .action-item {{
            background: rgba(102,126,234,0.1);
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
            border-left: 4px solid #667eea;
        }}
        .action-item .priority {{
            display: inline-block;
            width: 30px;
            height: 30px;
            background: #667eea;
            color: white;
            border-radius: 50%;
            text-align: center;
            line-height: 30px;
            font-weight: bold;
            margin-right: 15px;
        }}
        .action-item .impact {{ color: #38ef7d; font-size: 0.9em; margin-top: 10px; }}

        .idea-card {{
            background: rgba(56,239,125,0.1);
            border: 1px solid rgba(56,239,125,0.3);
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
        }}
        .idea-card .type {{
            display: inline-block;
            padding: 3px 10px;
            background: rgba(102,126,234,0.3);
            border-radius: 12px;
            font-size: 0.8em;
            margin-bottom: 10px;
        }}

        .pattern-compare {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .pattern-box {{ background: rgba(255,255,255,0.05); border-radius: 10px; padding: 20px; }}
        .pattern-box h4 {{ margin-bottom: 15px; }}
        .pattern-stat {{ display: flex; justify-content: space-between; padding: 8px 0; }}

        .winner {{ color: #38ef7d; }}
        .loser {{ color: #ff6b6b; }}

        .footer {{ text-align: center; color: #a0aec0; margin-top: 40px; padding: 20px; }}

        a {{ color: #667eea; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 Traffic Capture Analysis</h1>
        <p class="subtitle">{comp['your_channel']['name']} vs {comp['competitor']['name']}</p>

        <!-- Summary Cards -->
        <div class="grid">
            <div class="card">
                <h3>Keyword Gaps</h3>
                <div class="value">{summary['keyword_gaps_found']}</div>
                <div class="subvalue">Topics to target</div>
            </div>
            <div class="card">
                <h3>Viral Gaps</h3>
                <div class="value">{summary['viral_content_gaps']}</div>
                <div class="subvalue">Their hits you haven't covered</div>
            </div>
            <div class="card">
                <h3>Tag Opportunities</h3>
                <div class="value">{summary['tag_opportunities']}</div>
                <div class="subvalue">Tags to adopt</div>
            </div>
            <div class="card">
                <h3>Video Ideas</h3>
                <div class="value">{summary['video_ideas_generated']}</div>
                <div class="subvalue">Ready to create</div>
            </div>
        </div>

        <!-- Channel Comparison -->
        <div class="section">
            <h2>📊 Channel Comparison</h2>
            <div class="comparison-box">
                <div class="channel-stats">
                    <h4>Your Channel: {comp['your_channel']['name']}</h4>
                    <div class="stat-row">
                        <span class="stat-label">Subscribers</span>
                        <span class="stat-value">{format_number(comp['your_channel']['subscribers'])}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Avg Views</span>
                        <span class="stat-value">{format_number(comp['your_channel']['avg_views'])}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Avg Virality</span>
                        <span class="stat-value {'winner' if your_virality > their_virality else 'loser'}">{comp['your_channel']['avg_virality']:.3f}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Videos Analyzed</span>
                        <span class="stat-value">{comp['your_channel']['total_videos']}</span>
                    </div>
                </div>
                <div class="channel-stats">
                    <h4>Competitor: {comp['competitor']['name']}</h4>
                    <div class="stat-row">
                        <span class="stat-label">Subscribers</span>
                        <span class="stat-value">{format_number(comp['competitor']['subscribers'])}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Avg Views</span>
                        <span class="stat-value">{format_number(comp['competitor']['avg_views'])}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Avg Virality</span>
                        <span class="stat-value {'winner' if their_virality > your_virality else 'loser'}">{comp['competitor']['avg_virality']:.3f}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Videos Analyzed</span>
                        <span class="stat-value">{comp['competitor']['total_videos']}</span>
                    </div>
                </div>
            </div>
            <div style="text-align:center;margin-top:20px;padding:15px;background:rgba(102,126,234,0.1);border-radius:10px;">
                <strong>Your virality is {'+' if virality_diff > 0 else ''}{virality_diff:.1f}% {'higher' if virality_diff > 0 else 'lower'} than competitor</strong>
            </div>
        </div>

        <!-- Viral Content Gaps -->
        <div class="section">
            <h2>🔥 Viral Content Gaps - Their Hits You Haven't Covered</h2>
            <p style="color:#a0aec0;margin-bottom:20px;">These videos went viral for your competitor. Create your own version to capture this traffic.</p>
'''

    for gap in analysis.get('viral_gaps', [])[:10]:
        html += f'''
            <div class="viral-card">
                <h4>{gap['competitor_title']}</h4>
                <p>
                    <span class="views">{format_number(gap['views'])} views</span> •
                    Virality: {gap['virality']:.2f} •
                    Published: {gap['publish_date']}
                </p>
                <p style="margin-top:10px;"><a href="{gap['url']}" target="_blank">Watch on YouTube →</a></p>
                <div class="suggestion">
                    <strong>💡 Suggestion:</strong> {gap['suggested_angle']}
                </div>
            </div>
'''

    if not analysis.get('viral_gaps'):
        html += '<p style="color:#a0aec0;">No significant viral gaps found - you\'re covering similar content well!</p>'

    html += '''
        </div>

        <!-- Keyword Gaps -->
        <div class="section">
            <h2>🔑 Keyword Gaps - Topics to Target</h2>
            <p style="color:#a0aec0;margin-bottom:20px;">Keywords your competitor ranks for that you don't cover enough. Create content targeting these.</p>
            <table>
                <tr>
                    <th>Keyword</th>
                    <th>Competitor Score</th>
                    <th>Your Score</th>
                    <th>Opportunity</th>
                </tr>
'''

    for gap in analysis.get('keyword_gaps', [])[:20]:
        opp_class = f"opportunity-{gap['opportunity']}"
        html += f'''
                <tr>
                    <td><strong>{gap['keyword']}</strong></td>
                    <td>{gap['competitor_score']}</td>
                    <td>{gap['your_score']}</td>
                    <td class="{opp_class}">{gap['opportunity'].upper()}</td>
                </tr>
'''

    html += '''
            </table>
        </div>

        <!-- Tag Opportunities -->
        <div class="section">
            <h2>🏷️ Tag Opportunities</h2>
            <p style="color:#a0aec0;margin-bottom:20px;">Tags that work well for your competitor but you underutilize. Add these to your videos.</p>
            <table>
                <tr>
                    <th>Tag</th>
                    <th>Competitor Usage Score</th>
                    <th>Your Usage Score</th>
                </tr>
'''

    for tag in analysis.get('tag_opportunities', [])[:20]:
        html += f'''
                <tr>
                    <td><strong>{tag['tag']}</strong></td>
                    <td>{tag['competitor_usage']}</td>
                    <td>{tag['your_usage']}</td>
                </tr>
'''

    html += f'''
            </table>
        </div>

        <!-- Title Pattern Comparison -->
        <div class="section">
            <h2>📝 Title Pattern Comparison</h2>
            <p style="color:#a0aec0;margin-bottom:20px;">What makes their viral titles work? Adopt winning patterns.</p>
            <div class="pattern-compare">
                <div class="pattern-box">
                    <h4>Your Viral Titles</h4>
                    <div class="pattern-stat">
                        <span>Avg Length</span>
                        <span>{patterns['yours']['avg_title_length']} chars</span>
                    </div>
                    <div class="pattern-stat">
                        <span>Use Numbers</span>
                        <span>{patterns['yours']['percent_with_numbers']}%</span>
                    </div>
                    <div class="pattern-stat">
                        <span>Questions</span>
                        <span>{patterns['yours']['percent_questions']}%</span>
                    </div>
                    <div class="pattern-stat">
                        <span>How-to Style</span>
                        <span>{patterns['yours']['percent_how_to']}%</span>
                    </div>
                </div>
                <div class="pattern-box">
                    <h4>Competitor Viral Titles</h4>
                    <div class="pattern-stat">
                        <span>Avg Length</span>
                        <span>{patterns['competitor']['avg_title_length']} chars</span>
                    </div>
                    <div class="pattern-stat">
                        <span>Use Numbers</span>
                        <span class="{'winner' if patterns['competitor']['percent_with_numbers'] > patterns['yours']['percent_with_numbers'] else ''}">{patterns['competitor']['percent_with_numbers']}%</span>
                    </div>
                    <div class="pattern-stat">
                        <span>Questions</span>
                        <span class="{'winner' if patterns['competitor']['percent_questions'] > patterns['yours']['percent_questions'] else ''}">{patterns['competitor']['percent_questions']}%</span>
                    </div>
                    <div class="pattern-stat">
                        <span>How-to Style</span>
                        <span class="{'winner' if patterns['competitor']['percent_how_to'] > patterns['yours']['percent_how_to'] else ''}">{patterns['competitor']['percent_how_to']}%</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Video Ideas -->
        <div class="section">
            <h2>💡 Video Ideas to Capture Traffic</h2>
            <p style="color:#a0aec0;margin-bottom:20px;">Ready-to-use video ideas based on gaps and opportunities.</p>
'''

    for idea in analysis.get('video_ideas', []):
        priority_class = "priority-high" if idea['priority'] == 'high' else "priority-medium"
        html += f'''
            <div class="idea-card">
                <span class="type">{idea['type'].replace('_', ' ').title()}</span>
                <span class="{priority_class}">{idea['priority'].upper()} PRIORITY</span>
                <h4 style="margin-top:10px;">{idea['idea']}</h4>
                <p style="color:#a0aec0;margin-top:10px;">{idea['reason']}</p>
                {'<p style="margin-top:10px;"><a href="' + idea.get('reference', '#') + '" target="_blank">Reference video →</a></p>' if idea.get('reference') else ''}
            </div>
'''

    html += '''
        </div>

        <!-- Action Plan -->
        <div class="section">
            <h2>🎬 Action Plan</h2>
            <p style="color:#a0aec0;margin-bottom:20px;">Prioritized steps to capture competitor traffic.</p>
'''

    for action in analysis.get('action_plan', []):
        html += f'''
            <div class="action-item">
                <span class="priority">{action['priority']}</span>
                <strong>{action['action']}</strong>
                <p class="impact">Expected impact: {action['expected_impact'].upper()}</p>
            </div>
'''

    html += f'''
        </div>

        <div class="footer">
            <p>Generated by YouTube Competitive Analysis Tool • {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
    </div>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"📊 Traffic analysis HTML saved: {output_path}")


def analyze_traffic_drivers(videos: list[dict], channel_info: dict) -> dict:
    """
    Analyze which videos drive the most traffic to your channel and identify
    common patterns in your best-performing content so you can make more like them.
    """
    if not videos:
        return {'top_drivers': [], 'patterns': {}, 'recommendations': []}

    subscribers = channel_info.get('subscriber_count', 1)

    # Identify top performing videos by different metrics
    by_views = sorted(videos, key=lambda x: x.get('view_count', 0), reverse=True)
    by_virality = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)
    by_engagement = sorted(videos, key=lambda x: (
        x.get('like_count', 0) + x.get('comment_count', 0) * 5
    ) / max(x.get('view_count', 1), 1), reverse=True)

    # Top drivers are videos that appear in multiple top lists
    driver_scores = Counter()
    for i, v in enumerate(by_views[:20]):
        driver_scores[v['video_id']] += (20 - i)  # Higher score for higher rank
    for i, v in enumerate(by_virality[:20]):
        driver_scores[v['video_id']] += (20 - i)
    for i, v in enumerate(by_engagement[:20]):
        driver_scores[v['video_id']] += (20 - i)

    # Map video IDs back to video data
    video_map = {v['video_id']: v for v in videos}
    top_drivers = []
    for video_id, score in driver_scores.most_common(15):
        v = video_map[video_id]
        top_drivers.append({
            'video_id': video_id,
            'title': v['title'],
            'views': v.get('view_count', 0),
            'virality': v.get('virality_score', 0),
            'engagement_rate': round(
                (v.get('like_count', 0) + v.get('comment_count', 0) * 5) /
                max(v.get('view_count', 1), 1) * 100, 2
            ),
            'driver_score': score,
            'duration': v.get('duration_formatted', 'N/A'),
            'duration_seconds': v.get('duration_seconds', 0),
            'publish_date': v.get('publish_date', '')[:10],
            'tags': v.get('tags', [])[:5],
            'url': f"https://www.youtube.com/watch?v={video_id}",
        })

    # Analyze patterns in top performers
    top_videos = [video_map[vid] for vid, _ in driver_scores.most_common(15)]
    all_videos_sample = videos[:100] if len(videos) > 100 else videos

    def analyze_pattern_group(video_list):
        if not video_list:
            return {}
        return {
            'avg_title_length': round(sum(len(v['title']) for v in video_list) / len(video_list)),
            'percent_with_numbers': round(
                sum(1 for v in video_list if re.search(r'\d+', v['title'])) / len(video_list) * 100
            ),
            'percent_questions': round(
                sum(1 for v in video_list if '?' in v['title']) / len(video_list) * 100
            ),
            'percent_how_to': round(
                sum(1 for v in video_list if re.search(r'\b(how|why|what|when|where)\b', v['title'].lower()))
                / len(video_list) * 100
            ),
            'avg_duration_seconds': round(
                sum(v.get('duration_seconds', 0) for v in video_list) / len(video_list)
            ),
            'avg_tags': round(sum(len(v.get('tags', [])) for v in video_list) / len(video_list)),
        }

    top_patterns = analyze_pattern_group(top_videos)
    all_patterns = analyze_pattern_group(all_videos_sample)

    # Find what makes top videos different
    differences = {}
    if top_patterns and all_patterns:
        if top_patterns['percent_with_numbers'] > all_patterns['percent_with_numbers'] + 10:
            differences['numbers_in_title'] = f"Top videos use numbers {top_patterns['percent_with_numbers']}% vs {all_patterns['percent_with_numbers']}% overall"
        if top_patterns['percent_how_to'] > all_patterns['percent_how_to'] + 10:
            differences['how_to_content'] = f"Top videos are how-to {top_patterns['percent_how_to']}% vs {all_patterns['percent_how_to']}% overall"
        if abs(top_patterns['avg_duration_seconds'] - all_patterns['avg_duration_seconds']) > 120:
            if top_patterns['avg_duration_seconds'] > all_patterns['avg_duration_seconds']:
                differences['duration'] = f"Top videos are longer ({top_patterns['avg_duration_seconds']//60}m vs {all_patterns['avg_duration_seconds']//60}m avg)"
            else:
                differences['duration'] = f"Top videos are shorter ({top_patterns['avg_duration_seconds']//60}m vs {all_patterns['avg_duration_seconds']//60}m avg)"

    # Extract common keywords from top performers
    keyword_counts = Counter()
    for v in top_videos:
        words = re.findall(r'\b\w+\b', v['title'].lower())
        words = [w for w in words if len(w) > 3 and w not in {
            'this', 'that', 'with', 'from', 'have', 'will', 'your', 'what',
            'when', 'where', 'which', 'their', 'there', 'would', 'could',
            'should', 'about', 'into', 'more', 'some', 'than', 'them', 'then'
        }]
        keyword_counts.update(words)

    # Common tags in top performers
    tag_counts = Counter()
    for v in top_videos:
        tag_counts.update(t.lower() for t in v.get('tags', []))

    # Generate recommendations
    recommendations = []
    if differences.get('numbers_in_title'):
        recommendations.append("Include specific numbers in your titles (e.g., '5 Ways', '10 Tips')")
    if differences.get('how_to_content'):
        recommendations.append("Create more educational how-to content - it performs better for you")
    if 'duration' in differences and 'longer' in differences['duration']:
        recommendations.append("Your audience prefers longer, in-depth content - don't be afraid of length")
    if 'duration' in differences and 'shorter' in differences['duration']:
        recommendations.append("Your audience prefers concise content - keep videos focused")

    top_keywords = keyword_counts.most_common(10)
    if top_keywords:
        recommendations.append(
            f"Focus on these topics that drive traffic: {', '.join(kw for kw, _ in top_keywords[:5])}"
        )

    top_tags = tag_counts.most_common(10)
    if top_tags:
        recommendations.append(
            f"Keep using these high-performing tags: {', '.join(t for t, _ in top_tags[:5])}"
        )

    return {
        'top_drivers': top_drivers,
        'patterns': {
            'top_performers': top_patterns,
            'all_videos': all_patterns,
            'key_differences': differences,
        },
        'top_keywords': [{'keyword': kw, 'count': c} for kw, c in top_keywords],
        'top_tags': [{'tag': t, 'count': c} for t, c in top_tags],
        'recommendations': recommendations,
    }


def analyze_content_gaps_from_network(
    your_videos: list[dict],
    network_data: dict
) -> dict:
    """
    Analyze the content neighborhood to find topics/videos that related channels
    cover but you don't. Uses network data from build_video_network.
    """
    if not network_data:
        return {'gaps': [], 'opportunities': [], 'recommendations': []}

    related_channels = network_data.get('related_channels', [])
    if not related_channels:
        return {'gaps': [], 'opportunities': [], 'recommendations': []}

    # Extract your topics (keywords from titles)
    your_topics = set()
    your_keywords = Counter()
    for v in your_videos:
        words = re.findall(r'\b\w+\b', v['title'].lower())
        words = [w for w in words if len(w) > 3 and w not in {
            'this', 'that', 'with', 'from', 'have', 'will', 'your', 'what',
            'when', 'where', 'which', 'their', 'there', 'video', 'episode'
        }]
        your_topics.update(words)
        your_keywords.update(words)

    # Extract topics from related channels' videos
    network_topics = Counter()
    network_videos = []

    for ch in related_channels:
        for vid_info in ch.get('videos', []):
            related_title = vid_info.get('related_video', '')
            if related_title:
                words = re.findall(r'\b\w+\b', related_title.lower())
                words = [w for w in words if len(w) > 3 and w not in {
                    'this', 'that', 'with', 'from', 'have', 'will', 'your',
                    'what', 'when', 'where', 'which', 'their', 'there', 'video'
                }]
                network_topics.update(words)
                network_videos.append({
                    'title': related_title,
                    'channel': ch.get('title', 'Unknown'),
                    'video_id': vid_info.get('related_video_id', ''),
                    'connection_strength': ch.get('appearances', 1),
                    'keywords': words,
                })

    # Find gaps - topics in network that you don't cover
    gaps = []
    for topic, count in network_topics.most_common(100):
        if topic not in your_topics and count >= 2:
            gaps.append({
                'topic': topic,
                'network_frequency': count,
                'your_coverage': your_keywords.get(topic, 0),
                'opportunity_level': 'high' if count >= 5 else 'medium' if count >= 3 else 'low',
            })

    # Find specific video opportunities
    video_opportunities = []
    for vid in network_videos:
        # Check if video topic overlaps with your content but you might not cover it
        overlap = len(set(vid['keywords']) & your_topics)
        if overlap >= 1 and overlap < len(vid['keywords']) * 0.5:
            # Related to your content but potentially different angle
            video_opportunities.append({
                'title': vid['title'],
                'channel': vid['channel'],
                'video_id': vid['video_id'],
                'url': f"https://www.youtube.com/watch?v={vid['video_id']}" if vid['video_id'] else '',
                'connection_strength': vid['connection_strength'],
                'relevance': 'related_angle',
            })

    # Deduplicate and sort by connection strength
    seen_titles = set()
    unique_opportunities = []
    for opp in sorted(video_opportunities, key=lambda x: x['connection_strength'], reverse=True):
        title_key = opp['title'][:30].lower()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_opportunities.append(opp)
            if len(unique_opportunities) >= 20:
                break

    # Generate recommendations
    recommendations = []
    high_gaps = [g for g in gaps if g['opportunity_level'] == 'high']
    if high_gaps:
        topics = [g['topic'] for g in high_gaps[:5]]
        recommendations.append(
            f"High-opportunity topics from your network: {', '.join(topics)}"
        )

    if unique_opportunities:
        recommendations.append(
            f"Found {len(unique_opportunities)} videos from related channels worth studying"
        )

    # Identify channels creating content you're missing
    channel_gaps = Counter()
    for opp in unique_opportunities:
        channel_gaps[opp['channel']] += 1

    top_gap_channels = channel_gaps.most_common(5)
    if top_gap_channels:
        recommendations.append(
            f"Study these channels for content ideas: {', '.join(ch for ch, _ in top_gap_channels[:3])}"
        )

    return {
        'topic_gaps': gaps[:30],
        'video_opportunities': unique_opportunities,
        'top_gap_channels': [{'channel': ch, 'gap_count': c} for ch, c in top_gap_channels],
        'recommendations': recommendations,
        'summary': {
            'total_gaps_found': len(gaps),
            'high_opportunity_gaps': len(high_gaps),
            'video_opportunities': len(unique_opportunities),
        }
    }


def generate_traffic_drivers_html(
    traffic_drivers: dict,
    content_gaps: dict,
    channel_info: dict
) -> str:
    """Generate HTML section for traffic drivers and content gaps analysis."""
    if not traffic_drivers.get('top_drivers') and not content_gaps.get('topic_gaps'):
        return ""

    html = '''
        <div class="section" style="margin-top: 30px; background: linear-gradient(135deg, rgba(102,126,234,0.1) 0%, rgba(118,75,162,0.1) 100%);">
            <h2>🚀 Traffic Drivers Analysis</h2>
            <p style="color:#a0aec0;margin-bottom:20px;">Your best performing videos and what makes them successful.</p>
    '''

    # Top traffic drivers
    if traffic_drivers.get('top_drivers'):
        html += '''
            <h3>📈 Top Traffic Drivers</h3>
            <p style="color:#a0aec0;font-size:0.9em;margin-bottom:15px;">
                These videos drive the most traffic based on views, virality, and engagement combined.
            </p>
            <table>
                <tr>
                    <th>Title</th>
                    <th>Views</th>
                    <th>Virality</th>
                    <th>Engagement</th>
                    <th>Duration</th>
                </tr>
        '''
        for v in traffic_drivers['top_drivers'][:10]:
            virality_color = '#38ef7d' if v['virality'] > 1 else '#ffc107' if v['virality'] > 0.5 else '#a0aec0'
            html += f'''
                <tr>
                    <td><a href="{v['url']}" target="_blank" style="color:#667eea;text-decoration:none;">{v['title'][:50]}...</a></td>
                    <td>{format_number(v['views'])}</td>
                    <td style="color:{virality_color};">{v['virality']:.2f}</td>
                    <td>{v['engagement_rate']}%</td>
                    <td>{v['duration']}</td>
                </tr>
            '''
        html += '</table>'

    # Success patterns
    patterns = traffic_drivers.get('patterns', {})
    if patterns.get('key_differences'):
        html += '''
            <h3 style="margin-top:25px;">🎯 What Makes Your Top Videos Different</h3>
            <div style="background:rgba(56,239,125,0.1);border-radius:10px;padding:20px;margin:15px 0;">
        '''
        for key, diff in patterns['key_differences'].items():
            html += f'<p style="margin:8px 0;">✓ {diff}</p>'
        html += '</div>'

    # Top keywords and tags
    if traffic_drivers.get('top_keywords'):
        html += '''
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px;">
                <div>
                    <h4>🔑 High-Performing Keywords</h4>
                    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;">
        '''
        for kw in traffic_drivers['top_keywords'][:8]:
            html += f'<span style="background:rgba(102,126,234,0.2);padding:5px 12px;border-radius:15px;font-size:0.9em;">{kw["keyword"]} ({kw["count"]})</span>'
        html += '</div></div>'

        if traffic_drivers.get('top_tags'):
            html += '''
                <div>
                    <h4>🏷️ High-Performing Tags</h4>
                    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;">
            '''
            for tag in traffic_drivers['top_tags'][:8]:
                html += f'<span style="background:rgba(118,75,162,0.2);padding:5px 12px;border-radius:15px;font-size:0.9em;">{tag["tag"]} ({tag["count"]})</span>'
            html += '</div></div>'
        html += '</div>'

    # Recommendations
    if traffic_drivers.get('recommendations'):
        html += '''
            <h3 style="margin-top:25px;">💡 Recommendations</h3>
            <ul style="margin:15px 0 0 20px;">
        '''
        for rec in traffic_drivers['recommendations']:
            html += f'<li style="margin:8px 0;color:#e2e8f0;">{rec}</li>'
        html += '</ul>'

    html += '</div>'

    # Content Gaps Section
    if content_gaps.get('topic_gaps') or content_gaps.get('video_opportunities'):
        html += '''
        <div class="section" style="margin-top: 30px; background: linear-gradient(135deg, rgba(255,107,107,0.1) 0%, rgba(255,193,7,0.1) 100%);">
            <h2>🔍 Content Gaps from Network</h2>
            <p style="color:#a0aec0;margin-bottom:20px;">Topics and videos from related channels that you might want to cover.</p>
        '''

        # Summary stats
        summary = content_gaps.get('summary', {})
        html += f'''
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-bottom:25px;">
                <div class="card">
                    <h3>Topic Gaps Found</h3>
                    <div class="value" style="color:#ff6b6b;">{summary.get('total_gaps_found', 0)}</div>
                </div>
                <div class="card">
                    <h3>High Opportunity</h3>
                    <div class="value" style="color:#ffc107;">{summary.get('high_opportunity_gaps', 0)}</div>
                </div>
                <div class="card">
                    <h3>Video Ideas</h3>
                    <div class="value" style="color:#38ef7d;">{summary.get('video_opportunities', 0)}</div>
                </div>
            </div>
        '''

        # Topic gaps
        topic_gaps = content_gaps.get('topic_gaps', [])
        high_gaps = [g for g in topic_gaps if g['opportunity_level'] == 'high']
        if high_gaps:
            html += '''
                <h3>🎯 High-Opportunity Topics</h3>
                <p style="color:#a0aec0;font-size:0.9em;margin-bottom:15px;">
                    Topics frequently covered by related channels that you don't cover yet.
                </p>
                <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:20px;">
            '''
            for gap in high_gaps[:15]:
                html += f'''
                    <span style="background:rgba(255,107,107,0.2);padding:8px 15px;border-radius:20px;border:1px solid rgba(255,107,107,0.3);">
                        {gap['topic']} <span style="color:#a0aec0;font-size:0.8em;">({gap['network_frequency']}x in network)</span>
                    </span>
                '''
            html += '</div>'

        # Video opportunities
        video_opps = content_gaps.get('video_opportunities', [])
        if video_opps:
            html += '''
                <h3>📺 Videos from Related Channels to Study</h3>
                <p style="color:#a0aec0;font-size:0.9em;margin-bottom:15px;">
                    These videos from your network cover angles you might want to explore.
                </p>
                <table>
                    <tr><th>Video Title</th><th>Channel</th><th>Connection</th></tr>
            '''
            for opp in video_opps[:10]:
                strength = '●●●●●' if opp['connection_strength'] >= 5 else '●●●○○' if opp['connection_strength'] >= 3 else '●○○○○'
                html += f'''
                    <tr>
                        <td><a href="{opp['url']}" target="_blank" style="color:#667eea;text-decoration:none;">{opp['title'][:50]}...</a></td>
                        <td>{opp['channel'][:25]}</td>
                        <td style="color:#ffc107;">{strength}</td>
                    </tr>
                '''
            html += '</table>'

        # Recommendations
        if content_gaps.get('recommendations'):
            html += '''
                <h3 style="margin-top:25px;">💡 Recommendations</h3>
                <ul style="margin:15px 0 0 20px;">
            '''
            for rec in content_gaps['recommendations']:
                html += f'<li style="margin:8px 0;color:#e2e8f0;">{rec}</li>'
            html += '</ul>'

        html += '</div>'

    return html


# =============================================================================
# AI-ENHANCED ANALYSIS
# =============================================================================

def detect_ai_provider() -> tuple[str, str]:
    """
    Detect available AI provider based on API keys in environment.
    Returns (provider_name, api_key) or (None, None) if no provider available.
    Priority: Anthropic > OpenAI > Gemini
    """
    # Check Anthropic
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    if anthropic_key and ANTHROPIC_AVAILABLE:
        return ('anthropic', anthropic_key)

    # Check OpenAI
    openai_key = os.environ.get('OPENAI_API_KEY')
    if openai_key and OPENAI_AVAILABLE:
        return ('openai', openai_key)

    # Check Gemini
    gemini_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if gemini_key and GEMINI_AVAILABLE:
        return ('gemini', gemini_key)

    return (None, None)


def format_analysis_for_ai(
    your_channel: dict,
    your_analytics: dict,
    your_videos: list[dict],
    competitor_channel: dict = None,
    competitor_analytics: dict = None,
    traffic_analysis: dict = None,
) -> str:
    """
    Format analysis data into a prompt for AI analysis.
    """
    prompt_parts = []

    # Your channel summary
    prompt_parts.append(f"""## Your Channel: {your_channel.get('title', 'Unknown')}
- Subscribers: {format_number(your_channel.get('subscriber_count', 0))}
- Total Videos Analyzed: {your_analytics.get('overview', {}).get('total_videos_analyzed', 0)}
- Average Views per Video: {format_number(your_analytics.get('overview', {}).get('average_views_per_video', 0))}
- Average Virality Score: {your_analytics.get('overview', {}).get('average_virality_score', 0):.3f}
- Health Score: {your_analytics.get('health_score', {}).get('total_score', 0):.0f}/100 ({your_analytics.get('health_score', {}).get('grade', 'N/A')})
- Viral Videos: {your_analytics.get('viral_videos', {}).get('count', 0)} ({your_analytics.get('viral_videos', {}).get('percentage', 0):.1f}%)
""")

    # Top performing videos
    top_videos = your_analytics.get('top_videos', {}).get('by_virality', [])[:5]
    if top_videos:
        prompt_parts.append("### Your Top Performing Videos:")
        for v in top_videos:
            prompt_parts.append(f"- \"{v['title']}\" (views: {format_number(v.get('views', 0))}, virality: {v.get('virality', 0):.2f})")
        prompt_parts.append("")

    # Traffic drivers insights
    traffic_drivers = your_analytics.get('traffic_drivers', {})
    if traffic_drivers.get('patterns', {}).get('key_differences'):
        prompt_parts.append("### What Makes Your Top Videos Different:")
        for key, diff in traffic_drivers['patterns']['key_differences'].items():
            prompt_parts.append(f"- {diff}")
        prompt_parts.append("")

    # High performing keywords
    if traffic_drivers.get('top_keywords'):
        keywords = [kw['keyword'] for kw in traffic_drivers['top_keywords'][:10]]
        prompt_parts.append(f"### Your High-Performing Keywords: {', '.join(keywords)}")
        prompt_parts.append("")

    # Content gaps from network
    content_gaps = your_analytics.get('content_gaps', {})
    if content_gaps.get('topic_gaps'):
        high_gaps = [g['topic'] for g in content_gaps['topic_gaps'] if g['opportunity_level'] == 'high'][:10]
        if high_gaps:
            prompt_parts.append(f"### Content Gaps (topics related channels cover that you don't): {', '.join(high_gaps)}")
            prompt_parts.append("")

    # Competitor analysis
    if competitor_channel and competitor_analytics:
        prompt_parts.append(f"""## Competitor Channel: {competitor_channel.get('title', 'Unknown')}
- Subscribers: {format_number(competitor_channel.get('subscriber_count', 0))}
- Average Views per Video: {format_number(competitor_analytics.get('overview', {}).get('average_views_per_video', 0))}
- Average Virality Score: {competitor_analytics.get('overview', {}).get('average_virality_score', 0):.3f}
- Health Score: {competitor_analytics.get('health_score', {}).get('total_score', 0):.0f}/100
""")

        # Competitor top videos
        comp_top = competitor_analytics.get('top_videos', {}).get('by_virality', [])[:5]
        if comp_top:
            prompt_parts.append("### Competitor's Top Performing Videos:")
            for v in comp_top:
                prompt_parts.append(f"- \"{v['title']}\" (views: {format_number(v.get('views', 0))}, virality: {v.get('virality', 0):.2f})")
            prompt_parts.append("")

    # Traffic capture analysis
    if traffic_analysis:
        prompt_parts.append("## Traffic Capture Opportunities:")

        # Keyword gaps
        keyword_gaps = traffic_analysis.get('keyword_gaps', [])[:10]
        if keyword_gaps:
            gaps = [f"{g['keyword']} ({g['opportunity']})" for g in keyword_gaps]
            prompt_parts.append(f"### Keyword Gaps (competitor ranks, you don't): {', '.join(gaps)}")

        # Viral gaps
        viral_gaps = traffic_analysis.get('viral_gaps', [])[:5]
        if viral_gaps:
            prompt_parts.append("### Competitor Viral Videos You Haven't Covered:")
            for gap in viral_gaps:
                prompt_parts.append(f"- \"{gap['competitor_title']}\" ({format_number(gap['views'])} views)")

        # Title patterns
        patterns = traffic_analysis.get('title_patterns', {})
        if patterns.get('competitor') and patterns.get('yours'):
            comp_p = patterns['competitor']
            your_p = patterns['yours']
            prompt_parts.append(f"""### Title Pattern Comparison:
- Numbers in titles: You {your_p.get('percent_with_numbers', 0)}% vs Competitor {comp_p.get('percent_with_numbers', 0)}%
- How-to content: You {your_p.get('percent_how_to', 0)}% vs Competitor {comp_p.get('percent_how_to', 0)}%
- Question titles: You {your_p.get('percent_questions', 0)}% vs Competitor {comp_p.get('percent_questions', 0)}%
""")

    return '\n'.join(prompt_parts)


def get_ai_analysis_prompt(analysis_data: str, focus: str = 'general') -> str:
    """
    Create the full prompt for AI analysis.
    """
    base_prompt = f"""You are a YouTube growth strategist and content consultant. Analyze this YouTube channel data and provide actionable recommendations.

{analysis_data}

Based on this analysis, provide:

1. **Video Topic Ideas** (5-7 specific video ideas with working titles)
   - Each should target a gap or opportunity identified in the data
   - Include the strategic reasoning for each idea

2. **Content Strategy Recommendations** (3-5 actionable strategies)
   - How to improve based on what's working
   - How to capture competitor traffic
   - Posting schedule and format recommendations

3. **Title & Thumbnail Optimization** (specific suggestions)
   - Title formulas that would work for this channel
   - Thumbnail style recommendations based on top performers

4. **Quick Wins** (3 things to implement immediately)
   - Low-effort, high-impact changes

5. **90-Day Growth Plan** (prioritized roadmap)
   - Week 1-2, Week 3-4, Month 2, Month 3

Format your response in clear markdown with headers. Be specific and actionable - avoid generic advice. Reference the actual data provided."""

    return base_prompt


def call_anthropic_api(prompt: str, api_key: str) -> str:
    """Call Anthropic Claude API."""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text
    except Exception as e:
        return f"Error calling Anthropic API: {e}"


def call_openai_api(prompt: str, api_key: str) -> str:
    """Call OpenAI API."""
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error calling OpenAI API: {e}"


def call_gemini_api(prompt: str, api_key: str) -> str:
    """Call Google Gemini API."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error calling Gemini API: {e}"


def get_ai_recommendations(
    your_channel: dict,
    your_analytics: dict,
    your_videos: list[dict],
    competitor_channel: dict = None,
    competitor_analytics: dict = None,
    traffic_analysis: dict = None,
    output_dir: str = None,
) -> dict:
    """
    Get AI-powered recommendations using available AI provider.
    Falls back to generating a prompt file for manual use with Claude Code.
    """
    # Format the analysis data
    analysis_data = format_analysis_for_ai(
        your_channel, your_analytics, your_videos,
        competitor_channel, competitor_analytics, traffic_analysis
    )

    # Create the full prompt
    full_prompt = get_ai_analysis_prompt(analysis_data)

    # Detect available provider
    provider, api_key = detect_ai_provider()

    result = {
        'provider': provider,
        'prompt': full_prompt,
        'recommendations': None,
        'prompt_file': None,
    }

    if provider == 'anthropic':
        print("\n🤖 Generating AI recommendations using Claude...")
        result['recommendations'] = call_anthropic_api(full_prompt, api_key)
    elif provider == 'openai':
        print("\n🤖 Generating AI recommendations using GPT-4...")
        result['recommendations'] = call_openai_api(full_prompt, api_key)
    elif provider == 'gemini':
        print("\n🤖 Generating AI recommendations using Gemini...")
        result['recommendations'] = call_gemini_api(full_prompt, api_key)
    else:
        # No API key - save prompt for manual use
        print("\n⚠️  No AI API key found. Generating prompt file for manual use...")
        print("   Set one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY")

        if output_dir:
            prompt_file = os.path.join(output_dir, 'ai_analysis_prompt.md')
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write("# AI Analysis Prompt\n\n")
                f.write("Copy and paste this prompt into Claude Code, ChatGPT, or any AI assistant:\n\n")
                f.write("---\n\n")
                f.write(full_prompt)
            result['prompt_file'] = prompt_file
            print(f"   📄 Prompt saved to: {prompt_file}")
            print(f"\n   💡 To use with Claude Code, run:")
            print(f"      cat \"{prompt_file}\" | claude")
            print(f"\n   Or copy the contents and paste into any AI chat interface.")

    return result


def generate_ai_recommendations_html(ai_result: dict) -> str:
    """Generate HTML section for AI recommendations."""
    if not ai_result.get('recommendations'):
        if ai_result.get('prompt_file'):
            return f'''
        <div class="section" style="margin-top: 30px; background: linear-gradient(135deg, rgba(255,193,7,0.1) 0%, rgba(255,107,107,0.1) 100%);">
            <h2>🤖 AI Analysis</h2>
            <p style="color:#a0aec0;">No AI API key configured. A prompt file has been generated for manual use.</p>
            <p style="margin-top:15px;">
                <strong>Prompt file:</strong> <code>{ai_result['prompt_file']}</code>
            </p>
            <p style="color:#a0aec0;margin-top:10px;">
                Copy the prompt and paste it into Claude, ChatGPT, or any AI assistant to get personalized recommendations.
            </p>
        </div>
            '''
        return ""

    # Convert markdown to basic HTML
    recommendations = ai_result['recommendations']
    # Simple markdown to HTML conversion
    recommendations_html = recommendations.replace('\n\n', '</p><p>')
    recommendations_html = recommendations_html.replace('**', '<strong>').replace('**', '</strong>')
    recommendations_html = recommendations_html.replace('# ', '<h3>').replace('\n', '<br>')

    provider_names = {
        'anthropic': 'Claude',
        'openai': 'GPT-4',
        'gemini': 'Gemini'
    }
    provider_name = provider_names.get(ai_result.get('provider'), 'AI')

    return f'''
        <div class="section" style="margin-top: 30px; background: linear-gradient(135deg, rgba(102,126,234,0.15) 0%, rgba(56,239,125,0.1) 100%);">
            <h2>🤖 AI-Powered Recommendations</h2>
            <p style="color:#a0aec0;margin-bottom:20px;">Generated by {provider_name} based on your channel analysis.</p>
            <div style="background:rgba(0,0,0,0.2);border-radius:10px;padding:25px;line-height:1.8;">
                <div class="ai-content" style="white-space:pre-wrap;font-size:0.95em;">
{recommendations}
                </div>
            </div>
        </div>
    '''


def save_ai_recommendations(ai_result: dict, output_path: str) -> None:
    """Save AI recommendations to a markdown file."""
    if not ai_result.get('recommendations'):
        return

    provider_names = {
        'anthropic': 'Claude',
        'openai': 'GPT-4',
        'gemini': 'Gemini'
    }
    provider_name = provider_names.get(ai_result.get('provider'), 'AI')

    content = f"""# AI-Powered YouTube Growth Recommendations

*Generated by {provider_name} on {datetime.now().strftime('%Y-%m-%d %H:%M')}*

---

{ai_result['recommendations']}
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"📄 AI recommendations saved: {output_path}")


# =============================================================================
# NICHE BENCHMARKS & CUSTOM SCORING
# =============================================================================

def get_niche_benchmarks(category: str, custom_benchmarks: dict = None) -> dict:
    """
    Get benchmark data for a specific niche/category.
    """
    if custom_benchmarks and category in custom_benchmarks:
        return custom_benchmarks[category]

    return DEFAULT_NICHE_BENCHMARKS.get(category, DEFAULT_NICHE_BENCHMARKS['default'])


def compare_to_benchmarks(analytics: dict, category: str) -> dict:
    """
    Compare channel performance to niche benchmarks.
    """
    benchmarks = get_niche_benchmarks(category)

    overview = analytics.get('overview', {})

    channel_virality = overview.get('average_virality_score', 0)
    channel_engagement = overview.get('average_engagement_rate', 0)

    virality_vs_benchmark = ((channel_virality - benchmarks['avg_virality']) / benchmarks['avg_virality'] * 100) if benchmarks['avg_virality'] > 0 else 0
    engagement_vs_benchmark = ((channel_engagement - benchmarks['avg_engagement']) / benchmarks['avg_engagement'] * 100) if benchmarks['avg_engagement'] > 0 else 0

    return {
        'category': category,
        'benchmarks': benchmarks,
        'channel_performance': {
            'virality': channel_virality,
            'engagement': channel_engagement,
        },
        'vs_benchmark': {
            'virality': f"{'+' if virality_vs_benchmark > 0 else ''}{virality_vs_benchmark:.1f}%",
            'engagement': f"{'+' if engagement_vs_benchmark > 0 else ''}{engagement_vs_benchmark:.1f}%",
        },
        'performance_rating': 'above_average' if virality_vs_benchmark > 10 and engagement_vs_benchmark > 10
                              else 'average' if virality_vs_benchmark > -10 and engagement_vs_benchmark > -10
                              else 'below_average',
    }


def create_custom_scoring(weights: dict = None) -> Callable:
    """
    Create a custom scoring function with user-defined weights.
    """
    default_weights = {
        'views': 0.3,
        'engagement': 0.2,
        'virality': 0.3,
        'recency': 0.2,
    }

    weights = weights or default_weights

    def score_video(video: dict, channel_subscribers: int) -> float:
        views_score = min(1.0, video.get('view_count', 0) / max(channel_subscribers, 1))
        engagement_score = min(1.0, video.get('engagement_rate', 0) / 10)
        virality_score = min(1.0, video.get('virality_score', 0))

        try:
            pub_date = datetime.fromisoformat(video['publish_date'].replace('Z', '+00:00'))
            days_old = (datetime.now(pub_date.tzinfo) - pub_date).days
            recency_score = max(0, 1 - (days_old / 365))
        except:
            recency_score = 0.5

        total = (
            views_score * weights['views'] +
            engagement_score * weights['engagement'] +
            virality_score * weights['virality'] +
            recency_score * weights['recency']
        )

        return round(total * 100, 2)

    return score_video


# =============================================================================
# KEYWORD TRACKING
# =============================================================================

def track_keyword_rankings(youtube, keywords: list[str], channel_id: str, db_path: str) -> dict:
    """
    Track how channel videos rank for specific keywords over time.
    """
    rankings = {}

    for keyword in keywords[:10]:  # Limit to save quota
        try:
            response = retry_with_backoff(lambda kw=keyword: youtube.search().list(
                part='snippet',
                q=kw,
                type='video',
                maxResults=50,
            ).execute())

            position = None
            for i, item in enumerate(response.get('items', [])):
                if item['snippet']['channelId'] == channel_id:
                    position = i + 1
                    break

            rankings[keyword] = {
                'position': position,
                'in_top_10': position is not None and position <= 10,
                'in_top_50': position is not None,
                'timestamp': datetime.now().isoformat(),
            }
        except:
            rankings[keyword] = {'position': None, 'error': True}

    # Store in database if available
    if db_path and os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS keyword_rankings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT,
                keyword TEXT,
                position INTEGER,
                tracked_at TEXT
            )''')

            for keyword, data in rankings.items():
                if data.get('position'):
                    cursor.execute(
                        'INSERT INTO keyword_rankings (channel_id, keyword, position, tracked_at) VALUES (?,?,?,?)',
                        (channel_id, keyword, data['position'], data['timestamp'])
                    )

            conn.commit()
            conn.close()
        except:
            pass

    return {
        'rankings': rankings,
        'keywords_tracked': len(keywords),
        'in_top_10': sum(1 for r in rankings.values() if r.get('in_top_10')),
        'in_top_50': sum(1 for r in rankings.values() if r.get('in_top_50')),
    }


# =============================================================================
# PLAYLIST ANALYSIS
# =============================================================================

def analyze_playlists(youtube, channel_id: str) -> dict:
    """
    Analyze channel playlists and their performance.
    """
    try:
        response = retry_with_backoff(lambda: youtube.playlists().list(
            part='snippet,contentDetails',
            channelId=channel_id,
            maxResults=50,
        ).execute())

        playlists = []
        for item in response.get('items', []):
            playlists.append({
                'playlist_id': item['id'],
                'title': item['snippet']['title'],
                'description': item['snippet'].get('description', '')[:200],
                'video_count': item['contentDetails']['itemCount'],
                'published_at': item['snippet']['publishedAt'],
            })

        # Sort by video count
        playlists.sort(key=lambda x: x['video_count'], reverse=True)

        return {
            'total_playlists': len(playlists),
            'playlists': playlists[:20],
            'largest_playlist': playlists[0] if playlists else None,
            'total_videos_in_playlists': sum(p['video_count'] for p in playlists),
        }
    except Exception as e:
        return {'error': str(e), 'total_playlists': 0}


# =============================================================================
# VIDEO NETWORK & COMPETITOR DISCOVERY
# =============================================================================

def discover_related_videos(youtube, video: dict, max_results: int = MAX_RELATED_SEARCH_RESULTS) -> list[dict]:
    """
    Find videos related to a given video by searching for similar content.
    Note: YouTube deprecated relatedToVideoId, so we use keyword-based search.
    """
    # Extract keywords from title and tags
    title_words = re.findall(r'\b\w+\b', video['title'].lower())
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                  'of', 'with', 'by', 'from', 'is', 'it', 'this', 'that', 'i', 'you', 'we',
                  'my', 'your', 'how', 'what', 'why', 'when', 'where', 'which'}

    keywords = [w for w in title_words if w not in stop_words and len(w) > 3][:5]

    # Add top tags if available
    if video.get('tags'):
        keywords.extend(video['tags'][:3])

    if not keywords:
        return []

    search_query = ' '.join(keywords[:5])

    try:
        response = retry_with_backoff(lambda: youtube.search().list(
            part='snippet',
            q=search_query,
            type='video',
            maxResults=max_results,
            relevanceLanguage='en'
        ).execute())

        related = []
        for item in response.get('items', []):
            # Skip the same video
            if item['id']['videoId'] == video['video_id']:
                continue

            related.append({
                'video_id': item['id']['videoId'],
                'title': item['snippet']['title'],
                'channel_id': item['snippet']['channelId'],
                'channel_title': item['snippet']['channelTitle'],
                'description': item['snippet'].get('description', '')[:200],
                'published_at': item['snippet']['publishedAt'],
                'thumbnail': item['snippet'].get('thumbnails', {}).get('medium', {}).get('url', ''),
            })

        return related
    except Exception as e:
        print(f"Related video search error: {e}")
        return []


def discover_competitor_channels(youtube, channel_info: dict, videos: list[dict],
                                  max_channels: int = MAX_COMPETITOR_CHANNELS) -> dict:
    """
    Discover competitor channels based on:
    1. Channels that appear in related video searches
    2. Channels with similar content (keyword overlap)
    3. Channels mentioned in video descriptions
    """
    competitor_scores = defaultdict(lambda: {'score': 0, 'reasons': [], 'videos': []})
    own_channel_id = channel_info['channel_id']

    # Collect keywords from analyzed channel
    all_tags = []
    all_title_words = []

    for v in videos:
        all_tags.extend([t.lower() for t in v.get('tags', [])])
        words = re.findall(r'\b\w+\b', v['title'].lower())
        all_title_words.extend([w for w in words if len(w) > 3])

    top_tags = [tag for tag, _ in Counter(all_tags).most_common(10)]
    top_words = [w for w, _ in Counter(all_title_words).most_common(10)]

    # Search for competitors using top keywords/tags
    search_queries = []
    if top_tags:
        search_queries.append(' '.join(top_tags[:4]))
    if top_words:
        search_queries.append(' '.join(top_words[:4]))

    # Add category-specific search
    categories = Counter(v['category_name'] for v in videos).most_common(1)
    if categories:
        main_category = categories[0][0]
        if main_category != 'Unknown':
            search_queries.append(f"{main_category} {' '.join(top_words[:2])}")

    print(f"  Searching for competitors...")

    for query in search_queries[:3]:  # Limit to 3 searches to save quota
        try:
            response = retry_with_backoff(lambda q=query: youtube.search().list(
                part='snippet',
                q=q,
                type='channel',
                maxResults=15,
                relevanceLanguage='en'
            ).execute())

            for item in response.get('items', []):
                ch_id = item['snippet']['channelId']
                if ch_id == own_channel_id:
                    continue

                competitor_scores[ch_id]['channel_id'] = ch_id
                competitor_scores[ch_id]['title'] = item['snippet']['title']
                competitor_scores[ch_id]['description'] = item['snippet'].get('description', '')[:200]
                competitor_scores[ch_id]['thumbnail'] = item['snippet'].get('thumbnails', {}).get('medium', {}).get('url', '')
                competitor_scores[ch_id]['score'] += 1
                competitor_scores[ch_id]['reasons'].append(f"Found in search: {query[:30]}...")
        except Exception as e:
            print(f"  Competitor search error: {e}")

    # Also search for related videos from top-performing content
    top_videos = sorted(videos, key=lambda x: x['virality_score'], reverse=True)[:5]

    for v in top_videos:
        related = discover_related_videos(youtube, v, max_results=10)
        for rel in related:
            ch_id = rel['channel_id']
            if ch_id == own_channel_id:
                continue

            competitor_scores[ch_id]['channel_id'] = ch_id
            competitor_scores[ch_id]['title'] = rel['channel_title']
            competitor_scores[ch_id]['score'] += 2  # Higher weight for video-based discovery
            competitor_scores[ch_id]['reasons'].append(f"Related to: {v['title'][:30]}...")
            competitor_scores[ch_id]['videos'].append(rel['video_id'])

    # Extract channels mentioned in descriptions
    youtube_channel_pattern = r'(?:youtube\.com/(?:channel/|c/|@))([a-zA-Z0-9_-]+)'
    for v in videos[:50]:  # Check top 50 video descriptions
        matches = re.findall(youtube_channel_pattern, v.get('description', ''))
        for match in matches:
            # Note: This is a handle/custom URL, not channel ID
            competitor_scores[match]['score'] += 1
            competitor_scores[match]['reasons'].append("Mentioned in description")

    # Sort by score and return top competitors
    sorted_competitors = sorted(
        competitor_scores.items(),
        key=lambda x: x[1]['score'],
        reverse=True
    )[:max_channels]

    # Get additional info for top competitors
    competitors_list = []
    for ch_id, data in sorted_competitors:
        if data.get('title'):  # Only include if we have channel info
            competitors_list.append({
                'channel_id': ch_id,
                'title': data.get('title', 'Unknown'),
                'description': data.get('description', ''),
                'thumbnail': data.get('thumbnail', ''),
                'relevance_score': data['score'],
                'discovery_reasons': list(set(data['reasons']))[:3],  # Unique reasons
                'related_videos': data['videos'][:5],
            })

    return {
        'competitors': competitors_list,
        'total_found': len(competitors_list),
        'search_keywords': top_tags[:5] + top_words[:5],
    }


def build_video_network(youtube, videos: list[dict], channel_info: dict,
                        sample_size: int = 10) -> dict:
    """
    Build a network map showing how videos relate to the broader YouTube ecosystem.
    Shows which other channels/videos are in the same "content neighborhood".
    """
    print("  Building video network map...")

    network = {
        'center_channel': {
            'id': channel_info['channel_id'],
            'title': channel_info['title'],
            'subscribers': channel_info.get('subscriber_count', 0),
        },
        'related_channels': defaultdict(lambda: {'appearances': 0, 'videos': []}),
        'content_clusters': [],
        'network_stats': {},
    }

    # Sample top-performing videos for network analysis
    sample_videos = sorted(videos, key=lambda x: x['virality_score'], reverse=True)[:sample_size]

    all_related_channels = []

    for v in progress_bar(sample_videos, desc="Mapping network"):
        related = discover_related_videos(youtube, v, max_results=15)

        for rel in related:
            ch_id = rel['channel_id']
            if ch_id == channel_info['channel_id']:
                continue

            network['related_channels'][ch_id]['channel_id'] = ch_id
            network['related_channels'][ch_id]['title'] = rel['channel_title']
            network['related_channels'][ch_id]['appearances'] += 1
            network['related_channels'][ch_id]['videos'].append({
                'source_video': v['title'][:50],
                'related_video': rel['title'][:50],
                'related_video_id': rel['video_id'],
            })

            all_related_channels.append(ch_id)

    # Convert to list and sort by appearances (no limit - keep all)
    related_list = sorted(
        network['related_channels'].values(),
        key=lambda x: x['appearances'],
        reverse=True
    )

    # Calculate network stats
    unique_channels = len(set(all_related_channels))
    most_connected = related_list[0] if related_list else None

    network['related_channels'] = related_list
    network['network_stats'] = {
        'videos_analyzed': len(sample_videos),
        'unique_related_channels': unique_channels,
        'avg_connections_per_video': round(len(all_related_channels) / max(len(sample_videos), 1), 1),
        'most_connected_channel': most_connected['title'] if most_connected else None,
        'most_connected_appearances': most_connected['appearances'] if most_connected else 0,
    }

    # Identify content clusters (channels that appear together frequently)
    channel_pairs = defaultdict(int)
    for i, v in enumerate(sample_videos):
        related = discover_related_videos(youtube, v, max_results=10)
        channels_in_related = [r['channel_id'] for r in related if r['channel_id'] != channel_info['channel_id']]

        # Count co-occurrences
        for j, ch1 in enumerate(channels_in_related):
            for ch2 in channels_in_related[j+1:]:
                pair = tuple(sorted([ch1, ch2]))
                channel_pairs[pair] += 1

    # Top channel pairs that often appear together
    top_pairs = sorted(channel_pairs.items(), key=lambda x: x[1], reverse=True)[:10]
    network['content_clusters'] = [
        {'channels': list(pair), 'co_occurrences': count}
        for pair, count in top_pairs
    ]

    return network


def analyze_content_neighborhood(youtube, channel_info: dict, videos: list[dict]) -> dict:
    """
    Comprehensive analysis of the channel's position in the YouTube ecosystem.
    Combines competitor discovery and video network analysis.
    """
    print("\n🌐 Analyzing content neighborhood...")

    # Discover competitors
    competitors = discover_competitor_channels(youtube, channel_info, videos)

    # Build video network (limited to save API quota)
    network = build_video_network(youtube, videos, channel_info, sample_size=15)

    # Combine insights
    neighborhood = {
        'competitors': competitors,
        'video_network': network,
        'insights': [],
    }

    # Generate insights
    if competitors['competitors']:
        top_comp = competitors['competitors'][0]
        neighborhood['insights'].append(
            f"Top competitor: {top_comp['title']} (relevance score: {top_comp['relevance_score']})"
        )

    if network['network_stats'].get('most_connected_channel'):
        neighborhood['insights'].append(
            f"Most connected channel in your niche: {network['network_stats']['most_connected_channel']}"
        )

    if network['network_stats'].get('unique_related_channels', 0) > 20:
        neighborhood['insights'].append(
            "Your content connects to a diverse range of channels - broad appeal"
        )
    elif network['network_stats'].get('unique_related_channels', 0) < 10:
        neighborhood['insights'].append(
            "Your content has a focused niche - consider expanding topics for growth"
        )

    return neighborhood


# =============================================================================
# ADDITIONAL EXPORT FORMATS
# =============================================================================

def save_to_pdf(analytics: dict, channel_info: dict, videos: list[dict], output_path: str) -> bool:
    """
    Generate a PDF report using reportlab.
    """
    if not PDF_AVAILABLE:
        print("PDF export requires reportlab: pip install reportlab")
        return False

    try:
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph(f"YouTube Analysis Report: {channel_info['title']}", styles['Title']))
        story.append(Spacer(1, 20))

        # Overview
        story.append(Paragraph("Channel Overview", styles['Heading2']))
        overview = analytics.get('overview', {})
        overview_data = [
            ['Metric', 'Value'],
            ['Subscribers', format_number(channel_info.get('subscriber_count', 0))],
            ['Videos Analyzed', str(overview.get('total_videos_analyzed', 0))],
            ['Total Views', format_number(overview.get('total_views', 0))],
            ['Avg Views/Video', format_number(overview.get('average_views_per_video', 0))],
            ['Avg Virality', f"{overview.get('average_virality_score', 0):.4f}"],
        ]

        t = Table(overview_data, colWidths=[200, 200])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(t)
        story.append(Spacer(1, 20))

        # Health Score
        health = analytics.get('health_score', {})
        story.append(Paragraph(f"Channel Health: {health.get('total_score', 0):.0f}/100 ({health.get('grade', 'N/A')})", styles['Heading2']))
        story.append(Spacer(1, 10))

        # Top Videos
        story.append(Paragraph("Top 10 Videos by Virality", styles['Heading2']))
        top_videos = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:10]
        video_data = [['Title', 'Views', 'Virality']]
        for v in top_videos:
            video_data.append([
                v['title'][:40] + '...' if len(v['title']) > 40 else v['title'],
                format_number(v['view_count']),
                f"{v.get('virality_score', 0):.3f}"
            ])

        t2 = Table(video_data, colWidths=[250, 100, 80])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(t2)
        story.append(Spacer(1, 20))

        # Recommendations
        story.append(Paragraph("Strategic Recommendations", styles['Heading2']))
        for rec in analytics.get('recommendations', [])[:10]:
            story.append(Paragraph(f"• {rec}", styles['Normal']))

        # Build PDF
        doc.build(story)
        print(f"Saved PDF: {output_path}")
        return True
    except Exception as e:
        print(f"PDF export error: {e}")
        return False


def generate_rss_feed(channel_info: dict, videos: list[dict], output_path: str) -> None:
    """
    Generate an RSS feed for channel videos.
    """
    rss_items = []
    for v in sorted(videos, key=lambda x: x['publish_date'], reverse=True)[:50]:
        item = f"""    <item>
      <title><![CDATA[{v['title']}]]></title>
      <link>https://www.youtube.com/watch?v={v['video_id']}</link>
      <guid>https://www.youtube.com/watch?v={v['video_id']}</guid>
      <pubDate>{v['publish_date']}</pubDate>
      <description><![CDATA[
Views: {format_number(v['view_count'])}
Virality: {v.get('virality_score', 0):.3f}
Duration: {v.get('duration_formatted', 'N/A')}
      ]]></description>
    </item>"""
        rss_items.append(item)

    rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{channel_info['title']} - Analysis Feed</title>
    <link>https://www.youtube.com/channel/{channel_info['channel_id']}</link>
    <description>YouTube analytics feed for {channel_info['title']}</description>
    <lastBuildDate>{datetime.now().isoformat()}</lastBuildDate>
    <generator>YouTube Competitive Analysis Tool</generator>
{chr(10).join(rss_items)}
  </channel>
</rss>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(rss_content)
    print(f"Saved RSS feed: {output_path}")


def generate_scheduled_report(youtube, channel_ids: list[str], output_dir: str, config: dict = None) -> dict:
    """
    Generate scheduled reports for multiple channels.
    Designed to be called from cron/scheduler.
    """
    results = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')

    for channel_id in channel_ids:
        try:
            result = analyze_channel(
                youtube, channel_id, output_dir,
                ['json', 'html', 'markdown'],
                config=config
            )
            results.append({
                'channel': channel_id,
                'status': 'success',
                'timestamp': timestamp,
            })
        except Exception as e:
            results.append({
                'channel': channel_id,
                'status': 'error',
                'error': str(e),
                'timestamp': timestamp,
            })

    # Save summary
    summary_path = os.path.join(output_dir, f'scheduled_report_{timestamp}.json')
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)

    return {
        'reports_generated': len([r for r in results if r['status'] == 'success']),
        'errors': len([r for r in results if r['status'] == 'error']),
        'summary_path': summary_path,
    }


# =============================================================================
# API SERVER MODE
# =============================================================================

class AnalyticsAPIHandler(http.server.SimpleHTTPRequestHandler):
    """Simple HTTP handler for API mode."""

    youtube = None
    cache = {}
    config = {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/api/analyze':
            self.handle_analyze(params)
        elif path == '/api/health':
            self.send_json({'status': 'ok', 'timestamp': datetime.now().isoformat()})
        elif path == '/api/channels':
            self.handle_channels(params)
        else:
            self.send_error(404, 'Endpoint not found')

    def handle_analyze(self, params):
        channel = params.get('channel', [None])[0]
        if not channel:
            self.send_json({'error': 'channel parameter required'}, 400)
            return

        cache_key = f"analyze_{channel}"
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if (datetime.now() - cache_time).seconds < 3600:  # 1 hour cache
                self.send_json(data)
                return

        try:
            # Quick analysis without file export
            channel_id, channel_title = resolve_channel_id(self.youtube, channel)
            channel_info = get_channel_info(self.youtube, channel_id)
            videos = fetch_all_videos(self.youtube, channel_id, limit=50)

            for v in videos:
                v['virality_score'] = calculate_virality_score(v, channel_info.get('subscriber_count', 1))

            analytics = generate_analytics(videos, channel_info)

            result = {
                'channel': channel_info,
                'analytics': analytics,
                'video_count': len(videos),
                'timestamp': datetime.now().isoformat(),
            }

            self.cache[cache_key] = (datetime.now(), result)
            self.send_json(result)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def handle_channels(self, params):
        # List cached channels
        channels = list(set(k.replace('analyze_', '') for k in self.cache.keys() if k.startswith('analyze_')))
        self.send_json({'channels': channels, 'count': len(channels)})

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def log_message(self, format, *args):
        pass  # Suppress logging


def run_api_server(youtube, port: int = 8080, config: dict = None):
    """
    Run a simple API server for programmatic access.
    """
    AnalyticsAPIHandler.youtube = youtube
    AnalyticsAPIHandler.config = config or {}

    with socketserver.TCPServer(("", port), AnalyticsAPIHandler) as httpd:
        print(f"\n🌐 API Server running at http://localhost:{port}")
        print(f"   Endpoints:")
        print(f"   - GET /api/health")
        print(f"   - GET /api/analyze?channel=@handle")
        print(f"   - GET /api/channels")
        print(f"\nPress Ctrl+C to stop...")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


# =============================================================================
# TREND ALERTS SYSTEM
# =============================================================================

def check_trend_alerts(youtube, watchlist: list[str], db_path: str, config: dict = None) -> list[dict]:
    """
    Check watchlist channels for trending/viral videos and new uploads.
    Returns alerts for significant events.
    """
    alerts = []
    config = config or {}

    for channel_id in watchlist:
        try:
            # Get channel info
            try:
                ch_id, ch_title = resolve_channel_id(youtube, channel_id)
            except:
                continue

            channel_info = get_channel_info(youtube, ch_id)

            # Get recent videos (last 7 days)
            videos = fetch_all_videos(youtube, ch_id, limit=20)

            for v in videos:
                v['virality_score'] = calculate_virality_score(v, channel_info.get('subscriber_count', 1))
                velocity = calculate_trend_velocity(v, channel_info.get('subscriber_count', 1))
                v['velocity'] = velocity

                # Check for alerts
                try:
                    pub_date = datetime.fromisoformat(v['publish_date'].replace('Z', '+00:00'))
                    hours_old = (datetime.now(pub_date.tzinfo) - pub_date).total_seconds() / 3600
                except:
                    hours_old = 999

                # New video alert (< 24 hours)
                if hours_old < 24:
                    alerts.append({
                        'type': 'new_video',
                        'channel': ch_title,
                        'channel_id': ch_id,
                        'video_title': v['title'],
                        'video_id': v['video_id'],
                        'views': v['view_count'],
                        'hours_old': round(hours_old, 1),
                        'url': f"https://www.youtube.com/watch?v={v['video_id']}",
                    })

                # Trending alert (high velocity)
                if velocity['trend_status'] in ['exploding', 'trending']:
                    alerts.append({
                        'type': 'trending',
                        'channel': ch_title,
                        'channel_id': ch_id,
                        'video_title': v['title'],
                        'video_id': v['video_id'],
                        'views': v['view_count'],
                        'velocity_score': velocity['velocity_score'],
                        'trend_status': velocity['trend_status'],
                        'url': f"https://www.youtube.com/watch?v={v['video_id']}",
                    })

                # Viral alert (virality > 2)
                if v['virality_score'] > 2.0 and hours_old < 168:  # Within a week
                    alerts.append({
                        'type': 'viral',
                        'channel': ch_title,
                        'channel_id': ch_id,
                        'video_title': v['title'],
                        'video_id': v['video_id'],
                        'views': v['view_count'],
                        'virality_score': v['virality_score'],
                        'url': f"https://www.youtube.com/watch?v={v['video_id']}",
                    })

        except Exception as e:
            print(f"Error checking {channel_id}: {e}")

    # Deduplicate alerts
    seen = set()
    unique_alerts = []
    for alert in alerts:
        key = f"{alert['type']}_{alert['video_id']}"
        if key not in seen:
            seen.add(key)
            unique_alerts.append(alert)

    return unique_alerts


def format_alert_message(alert: dict) -> str:
    """Format an alert for display/notification."""
    if alert['type'] == 'new_video':
        return f"🆕 NEW: {alert['channel']} posted \"{alert['video_title']}\" ({alert['hours_old']}h ago, {format_number(alert['views'])} views)"
    elif alert['type'] == 'trending':
        return f"📈 TRENDING: \"{alert['video_title']}\" by {alert['channel']} is {alert['trend_status']}!"
    elif alert['type'] == 'viral':
        return f"🔥 VIRAL: \"{alert['video_title']}\" by {alert['channel']} (virality: {alert['virality_score']:.2f})"
    return str(alert)


# =============================================================================
# WATCH MODE - CONTINUOUS MONITORING
# =============================================================================

class WatchMode:
    """Continuous monitoring mode for watchlist channels."""

    def __init__(self, youtube, config: dict, interval_hours: float = 6):
        self.youtube = youtube
        self.config = config
        self.interval = interval_hours * 3600  # Convert to seconds
        self.running = False
        self.seen_alerts = set()  # Track sent alerts to avoid duplicates

    def start(self):
        """Start continuous monitoring."""
        self.running = True
        print(f"\n👁️  WATCH MODE ACTIVE")
        print(f"   Monitoring {len(self.config.get('watchlist', []))} channels")
        print(f"   Check interval: {self.interval / 3600:.1f} hours")
        print(f"   Press Ctrl+C to stop\n")

        # Handle graceful shutdown
        def signal_handler(sig, frame):
            print("\n\n🛑 Stopping watch mode...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)

        check_count = 0
        while self.running:
            check_count += 1
            print(f"\n{'='*50}")
            print(f"🔍 Check #{check_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print('='*50)

            self._run_check()

            if self.running:
                next_check = datetime.now() + timedelta(seconds=self.interval)
                print(f"\n⏰ Next check at {next_check.strftime('%H:%M:%S')}")

                # Sleep in small increments to allow interrupt
                for _ in range(int(self.interval / 10)):
                    if not self.running:
                        break
                    time.sleep(10)

        print("👋 Watch mode stopped")

    def _run_check(self):
        """Run a single monitoring check."""
        watchlist = self.config.get('watchlist', [])
        if not watchlist:
            print("❌ No channels in watchlist")
            return

        alerts = check_trend_alerts(self.youtube, watchlist, './output/watch.db', self.config)

        # Filter out already-seen alerts
        new_alerts = []
        for alert in alerts:
            alert_key = f"{alert['type']}_{alert['video_id']}"
            if alert_key not in self.seen_alerts:
                new_alerts.append(alert)
                self.seen_alerts.add(alert_key)

        if new_alerts:
            print(f"\n📢 {len(new_alerts)} new alert(s):\n")
            for alert in new_alerts:
                msg = format_alert_message(alert)
                print(f"  {msg}")

                # Send webhooks
                discord_url = self.config.get('webhooks', {}).get('discord')
                slack_url = self.config.get('webhooks', {}).get('slack')

                if discord_url:
                    send_discord_webhook(discord_url, msg)
                if slack_url:
                    send_slack_webhook(slack_url, msg)
        else:
            print("✅ No new alerts")

        # Clean old alerts from memory (keep last 1000)
        if len(self.seen_alerts) > 1000:
            self.seen_alerts = set(list(self.seen_alerts)[-500:])


def run_watch_mode(youtube, config: dict, interval_hours: float = 6):
    """Run continuous watch mode."""
    watcher = WatchMode(youtube, config, interval_hours)
    watcher.start()


# =============================================================================
# TIME COMPARISON - WEEK OVER WEEK ANALYSIS
# =============================================================================

def compare_time_periods(videos: list[dict], channel_info: dict) -> dict:
    """
    Compare performance between this week and last week.
    """
    now = datetime.now()
    one_week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    this_week = []
    last_week = []

    for v in videos:
        try:
            pub_date = datetime.fromisoformat(v['publish_date'].replace('Z', '+00:00'))
            pub_date_naive = pub_date.replace(tzinfo=None)

            if pub_date_naive >= one_week_ago:
                this_week.append(v)
            elif pub_date_naive >= two_weeks_ago:
                last_week.append(v)
        except:
            pass

    def calc_metrics(vids):
        if not vids:
            return {'count': 0, 'views': 0, 'avg_views': 0, 'avg_virality': 0, 'avg_engagement': 0}
        return {
            'count': len(vids),
            'views': sum(v['view_count'] for v in vids),
            'avg_views': sum(v['view_count'] for v in vids) // len(vids),
            'avg_virality': round(sum(v.get('virality_score', 0) for v in vids) / len(vids), 4),
            'avg_engagement': round(sum(v.get('engagement_rate', 0) for v in vids) / len(vids), 2),
        }

    this_week_metrics = calc_metrics(this_week)
    last_week_metrics = calc_metrics(last_week)

    # Calculate changes
    def calc_change(current, previous):
        if previous == 0:
            return 0 if current == 0 else 100
        return round((current - previous) / previous * 100, 1)

    comparison = {
        'this_week': this_week_metrics,
        'last_week': last_week_metrics,
        'changes': {
            'video_count': calc_change(this_week_metrics['count'], last_week_metrics['count']),
            'total_views': calc_change(this_week_metrics['views'], last_week_metrics['views']),
            'avg_views': calc_change(this_week_metrics['avg_views'], last_week_metrics['avg_views']),
            'avg_virality': calc_change(this_week_metrics['avg_virality'], last_week_metrics['avg_virality']),
            'avg_engagement': calc_change(this_week_metrics['avg_engagement'], last_week_metrics['avg_engagement']),
        },
        'trend': 'improving' if this_week_metrics['avg_virality'] > last_week_metrics['avg_virality'] else 'declining' if this_week_metrics['avg_virality'] < last_week_metrics['avg_virality'] else 'stable',
        'top_this_week': sorted(this_week, key=lambda x: x['view_count'], reverse=True)[:5] if this_week else [],
        'top_last_week': sorted(last_week, key=lambda x: x['view_count'], reverse=True)[:5] if last_week else [],
    }

    return comparison


def format_time_comparison(comparison: dict) -> str:
    """Format time comparison for display."""
    lines = [
        "\n📊 WEEK OVER WEEK COMPARISON",
        "=" * 40,
        "",
        f"{'Metric':<20} {'This Week':<12} {'Last Week':<12} {'Change':<10}",
        "-" * 54,
    ]

    tw = comparison['this_week']
    lw = comparison['last_week']
    ch = comparison['changes']

    def fmt_change(val):
        if val > 0:
            return f"+{val}%"
        elif val < 0:
            return f"{val}%"
        return "0%"

    lines.append(f"{'Videos Posted':<20} {tw['count']:<12} {lw['count']:<12} {fmt_change(ch['video_count']):<10}")
    lines.append(f"{'Total Views':<20} {format_number(tw['views']):<12} {format_number(lw['views']):<12} {fmt_change(ch['total_views']):<10}")
    lines.append(f"{'Avg Views':<20} {format_number(tw['avg_views']):<12} {format_number(lw['avg_views']):<12} {fmt_change(ch['avg_views']):<10}")
    lines.append(f"{'Avg Virality':<20} {tw['avg_virality']:<12.4f} {lw['avg_virality']:<12.4f} {fmt_change(ch['avg_virality']):<10}")
    lines.append(f"{'Avg Engagement':<20} {tw['avg_engagement']:<12.2f}% {lw['avg_engagement']:<12.2f}% {fmt_change(ch['avg_engagement']):<10}")
    lines.append("")
    lines.append(f"📈 Overall Trend: {comparison['trend'].upper()}")

    return '\n'.join(lines)


# =============================================================================
# TAG OPTIMIZATION
# =============================================================================

def optimize_tags(videos: list[dict], target_video: dict = None) -> dict:
    """
    Analyze tags from top-performing videos and suggest optimal tags.
    """
    # Get top performing videos
    top_videos = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:30]

    # Collect all tags from top videos with their performance
    tag_performance = defaultdict(lambda: {'count': 0, 'total_virality': 0, 'videos': []})

    for v in top_videos:
        tags = v.get('tags', [])
        for tag in tags:
            tag_lower = tag.lower()
            tag_performance[tag_lower]['count'] += 1
            tag_performance[tag_lower]['total_virality'] += v.get('virality_score', 0)
            tag_performance[tag_lower]['videos'].append(v['title'][:30])

    # Calculate average virality per tag
    for tag, data in tag_performance.items():
        data['avg_virality'] = data['total_virality'] / data['count'] if data['count'] > 0 else 0

    # Sort by combination of frequency and performance
    sorted_tags = sorted(
        tag_performance.items(),
        key=lambda x: (x[1]['count'] * 0.4 + x[1]['avg_virality'] * 0.6),
        reverse=True
    )

    # Get top recommended tags
    recommended = [tag for tag, _ in sorted_tags[:30]]

    # Categorize tags
    high_performing = [tag for tag, data in sorted_tags if data['avg_virality'] > 0.8][:10]
    frequently_used = [tag for tag, data in sorted_tags if data['count'] >= 3][:10]

    # Generate tag suggestions for target video if provided
    suggestions_for_video = []
    if target_video:
        title_words = set(re.findall(r'\b\w+\b', target_video['title'].lower()))
        current_tags = set(t.lower() for t in target_video.get('tags', []))

        for tag, data in sorted_tags[:50]:
            if tag not in current_tags:
                # Check relevance to title
                tag_words = set(tag.split())
                if tag_words & title_words or data['count'] >= 5:
                    suggestions_for_video.append({
                        'tag': tag,
                        'reason': f"Used in {data['count']} top videos, avg virality: {data['avg_virality']:.2f}"
                    })

        suggestions_for_video = suggestions_for_video[:15]

    return {
        'recommended_tags': recommended,
        'high_performing_tags': high_performing,
        'frequently_used_tags': frequently_used,
        'suggestions_for_video': suggestions_for_video,
        'tag_stats': {tag: {'count': data['count'], 'avg_virality': round(data['avg_virality'], 3)}
                      for tag, data in sorted_tags[:20]},
        'total_unique_tags': len(tag_performance),
    }


# =============================================================================
# WHITE-LABEL REPORTS
# =============================================================================

def generate_white_label_html(videos: list[dict], analytics: dict, channel_info: dict,
                               output_path: str, branding: dict = None) -> None:
    """
    Generate white-label HTML dashboard with custom branding.
    """
    branding = branding or {}
    company_name = branding.get('company_name', 'Analytics Report')
    logo_url = branding.get('logo_url', '')
    primary_color = branding.get('primary_color', '#667eea')
    secondary_color = branding.get('secondary_color', '#764ba2')

    # Prepare data
    health = analytics.get('health_score', {})
    overview = analytics.get('overview', {})

    logo_html = f'<img src="{logo_url}" alt="Logo" style="height:40px;margin-right:15px;">' if logo_url else ''

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{channel_info['title']} - {company_name}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, {primary_color} 0%, {secondary_color} 100%); min-height: 100vh; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ background: rgba(255,255,255,0.95); border-radius: 15px; padding: 25px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; }}
        .header-left {{ display: flex; align-items: center; }}
        .header h1 {{ font-size: 1.8em; color: #1a1a2e; }}
        .header .subtitle {{ color: #666; margin-top: 5px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .card {{ background: rgba(255,255,255,0.95); border-radius: 12px; padding: 20px; text-align: center; }}
        .card h3 {{ color: #666; font-size: 0.85em; text-transform: uppercase; margin-bottom: 8px; }}
        .card .value {{ font-size: 2em; font-weight: bold; color: {primary_color}; }}
        .card .subvalue {{ font-size: 0.8em; color: #888; margin-top: 5px; }}
        .chart-container {{ background: rgba(255,255,255,0.95); border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
        .chart-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: {primary_color}; color: white; }}
        tr:hover {{ background: #f5f5f5; }}
        .footer {{ text-align: center; padding: 20px; color: rgba(255,255,255,0.8); font-size: 0.9em; }}
        .score-badge {{ display: inline-block; padding: 5px 15px; border-radius: 20px; background: {primary_color}; color: white; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-left">
                {logo_html}
                <div>
                    <h1>{channel_info['title']}</h1>
                    <div class="subtitle">Channel Analysis Report - {datetime.now().strftime('%B %d, %Y')}</div>
                </div>
            </div>
            <div class="score-badge">Health: {health.get('total_score', 0):.0f}/100 ({health.get('grade', 'N/A')})</div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Subscribers</h3>
                <div class="value">{format_number(channel_info.get('subscriber_count', 0))}</div>
            </div>
            <div class="card">
                <h3>Videos Analyzed</h3>
                <div class="value">{overview.get('total_videos_analyzed', 0)}</div>
            </div>
            <div class="card">
                <h3>Total Views</h3>
                <div class="value">{format_number(overview.get('total_views', 0))}</div>
            </div>
            <div class="card">
                <h3>Avg Virality</h3>
                <div class="value">{overview.get('average_virality_score', 0):.3f}</div>
            </div>
            <div class="card">
                <h3>Est. Revenue</h3>
                <div class="value">{format_currency(analytics.get('revenue_analysis', {}).get('total_estimated_mid', 0))}</div>
            </div>
            <div class="card">
                <h3>Viral Videos</h3>
                <div class="value">{analytics.get('viral_videos', {}).get('count', 0)}</div>
                <div class="subvalue">{analytics.get('viral_videos', {}).get('percentage', 0):.1f}% of total</div>
            </div>
        </div>

        <div class="chart-container">
            <h3>Top 15 Videos by Performance</h3>
            <table>
                <tr><th>Title</th><th>Views</th><th>Virality</th><th>Est. Revenue</th></tr>
                {''.join(f"<tr><td>{v['title'][:50]}...</td><td>{format_number(v.get('view_count', 0))}</td><td>{v.get('virality_score', 0):.3f}</td><td>{format_currency(v.get('estimated_revenue_mid', 0))}</td></tr>" for v in sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:15])}
            </table>
        </div>

        <div class="chart-container">
            <h3>Recommendations</h3>
            <ul style="padding-left: 20px; line-height: 2;">
                {''.join(f"<li>{rec}</li>" for rec in analytics.get('recommendations', [])[:10])}
            </ul>
        </div>

        <div class="footer">
            <p>Generated by {company_name} | {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
    </div>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Saved white-label report: {output_path}")


# =============================================================================
# PARALLEL BATCH PROCESSING
# =============================================================================

def process_batch_parallel(youtube, channels: list[str], output_dir: str, formats: list[str],
                           config: dict = None, max_workers: int = 3, **kwargs) -> list[dict]:
    """
    Process multiple channels in parallel using ThreadPoolExecutor.
    """
    results = []
    errors = []

    print(f"\n🚀 Parallel processing {len(channels)} channels (max {max_workers} concurrent)")

    def analyze_single(channel):
        try:
            result = analyze_channel(youtube, channel, output_dir, formats, config=config, **kwargs)
            return {'channel': channel, 'status': 'success', 'data': result}
        except Exception as e:
            return {'channel': channel, 'status': 'error', 'error': str(e)}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_channel = {executor.submit(analyze_single, ch): ch for ch in channels}

        for i, future in enumerate(as_completed(future_to_channel), 1):
            channel = future_to_channel[future]
            try:
                result = future.result()
                if result['status'] == 'success':
                    results.append(result)
                    print(f"✅ [{i}/{len(channels)}] {channel} - Complete")
                else:
                    errors.append(result)
                    print(f"❌ [{i}/{len(channels)}] {channel} - Error: {result['error']}")
            except Exception as e:
                errors.append({'channel': channel, 'status': 'error', 'error': str(e)})
                print(f"❌ [{i}/{len(channels)}] {channel} - Exception: {e}")

    print(f"\n📊 Completed: {len(results)} success, {len(errors)} errors")

    return results


# =============================================================================
# PROGRESS RESUME - SAVE/LOAD STATE
# =============================================================================

PROGRESS_FILE = '.youtube_analyzer_progress.pkl'


def save_progress(data: dict, output_dir: str = './output'):
    """Save analysis progress for later resumption."""
    progress_path = os.path.join(output_dir, PROGRESS_FILE)
    os.makedirs(output_dir, exist_ok=True)

    progress = {
        'timestamp': datetime.now().isoformat(),
        'data': data,
        'version': '1.0',
    }

    with open(progress_path, 'wb') as f:
        pickle.dump(progress, f)

    print(f"💾 Progress saved to {progress_path}")


def load_progress(output_dir: str = './output') -> Optional[dict]:
    """Load saved progress if available."""
    progress_path = os.path.join(output_dir, PROGRESS_FILE)

    if not os.path.exists(progress_path):
        return None

    try:
        with open(progress_path, 'rb') as f:
            progress = pickle.load(f)

        # Check if progress is recent (within 24 hours)
        saved_time = datetime.fromisoformat(progress['timestamp'])
        if (datetime.now() - saved_time).days >= 1:
            print("⚠️ Saved progress is more than 24 hours old, starting fresh")
            return None

        print(f"📂 Found saved progress from {saved_time.strftime('%Y-%m-%d %H:%M')}")
        return progress['data']
    except Exception as e:
        print(f"⚠️ Could not load progress: {e}")
        return None


def clear_progress(output_dir: str = './output'):
    """Clear saved progress file."""
    progress_path = os.path.join(output_dir, PROGRESS_FILE)
    if os.path.exists(progress_path):
        os.remove(progress_path)
        print("🗑️ Progress cleared")


def analyze_channel_with_resume(youtube, channel_input: str, output_dir: str, formats: list[str],
                                 resume: bool = True, **kwargs) -> dict:
    """
    Analyze channel with progress saving for resumption.
    """
    progress_key = f"channel_{hashlib.md5(channel_input.encode()).hexdigest()[:8]}"

    if resume:
        saved = load_progress(output_dir)
        if saved and progress_key in saved:
            print(f"📂 Resuming analysis for {channel_input}")
            # Could implement partial resume here
            # For now, just return saved data
            return saved[progress_key]

    # Run full analysis
    result = analyze_channel(youtube, channel_input, output_dir, formats, **kwargs)

    # Save progress
    progress_data = load_progress(output_dir) or {}
    progress_data[progress_key] = result
    save_progress(progress_data, output_dir)

    return result


# =============================================================================
# CHANNEL RESOLUTION
# =============================================================================

def extract_channel_id_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    path = parsed.path.strip('/')

    if path.startswith('channel/'):
        return path.split('/')[1]
    if path.startswith('@'):
        return path
    if path.startswith('c/'):
        return path
    if path.startswith('user/'):
        return path
    return None


def resolve_channel_id(youtube, identifier: str) -> tuple[str, str]:
    if identifier.startswith('UC') and len(identifier) == 24:
        response = retry_with_backoff(lambda: youtube.channels().list(
            part='snippet', id=identifier
        ).execute())
        if response.get('items'):
            return identifier, response['items'][0]['snippet']['title']
        raise ValueError(f"Channel not found: {identifier}")

    if identifier.startswith('@'):
        handle = identifier[1:]
        response = retry_with_backoff(lambda: youtube.channels().list(
            part='snippet', forHandle=handle
        ).execute())
        if response.get('items'):
            item = response['items'][0]
            return item['id'], item['snippet']['title']
        raise ValueError(f"Channel not found: {identifier}")

    if identifier.startswith('c/'):
        custom_name = identifier[2:]
        response = retry_with_backoff(lambda: youtube.search().list(
            part='snippet', q=custom_name, type='channel', maxResults=5
        ).execute())
        for item in response.get('items', []):
            return item['snippet']['channelId'], item['snippet']['channelTitle']
        raise ValueError(f"Channel not found: {identifier}")

    if identifier.startswith('user/'):
        username = identifier[5:]
        response = retry_with_backoff(lambda: youtube.channels().list(
            part='snippet', forUsername=username
        ).execute())
        if response.get('items'):
            item = response['items'][0]
            return item['id'], item['snippet']['title']
        raise ValueError(f"Channel not found: {identifier}")

    # Try handle then ID
    response = retry_with_backoff(lambda: youtube.channels().list(
        part='snippet', forHandle=identifier
    ).execute())
    if response.get('items'):
        item = response['items'][0]
        return item['id'], item['snippet']['title']

    response = retry_with_backoff(lambda: youtube.channels().list(
        part='snippet', id=identifier
    ).execute())
    if response.get('items'):
        return identifier, response['items'][0]['snippet']['title']

    raise ValueError(f"Could not resolve: {identifier}")


def get_channel_info(youtube, channel_id: str) -> dict:
    response = retry_with_backoff(lambda: youtube.channels().list(
        part='snippet,statistics,contentDetails,brandingSettings',
        id=channel_id
    ).execute())

    if not response.get('items'):
        raise ValueError(f"Channel not found: {channel_id}")

    item = response['items'][0]

    return {
        'channel_id': channel_id,
        'title': item['snippet']['title'],
        'description': item['snippet'].get('description', ''),
        'custom_url': item['snippet'].get('customUrl', ''),
        'published_at': item['snippet'].get('publishedAt', ''),
        'country': item['snippet'].get('country', ''),
        'subscriber_count': int(item['statistics'].get('subscriberCount', 0)),
        'video_count': int(item['statistics'].get('videoCount', 0)),
        'view_count': int(item['statistics'].get('viewCount', 0)),
        'uploads_playlist_id': item['contentDetails']['relatedPlaylists']['uploads'],
        'thumbnail_url': item['snippet'].get('thumbnails', {}).get('high', {}).get('url', ''),
    }


# =============================================================================
# VIDEO FETCHING
# =============================================================================

def fetch_video_ids_from_playlist(youtube, playlist_id: str,
                                   since: Optional[datetime] = None,
                                   until: Optional[datetime] = None,
                                   limit: Optional[int] = None) -> list[str]:
    video_ids = []
    next_page_token = None

    print("Fetching video IDs...")

    while True:
        response = retry_with_backoff(lambda: youtube.playlistItems().list(
            part='contentDetails,snippet',
            playlistId=playlist_id,
            maxResults=MAX_RESULTS_PER_PAGE,
            pageToken=next_page_token
        ).execute())

        for item in response.get('items', []):
            video_id = item['contentDetails']['videoId']
            published_at_str = item['snippet'].get('publishedAt', '')

            if published_at_str:
                published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                if since and published_at.replace(tzinfo=None) < since:
                    continue
                if until and published_at.replace(tzinfo=None) > until:
                    continue

            video_ids.append(video_id)

            if limit and len(video_ids) >= limit:
                return video_ids

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    print(f"Found {len(video_ids)} videos")
    return video_ids


def fetch_video_metadata_batch(youtube, video_ids: list[str], channel_info: dict,
                                min_views: Optional[int] = None) -> list[dict]:
    all_videos = []
    channel_subscribers = channel_info.get('subscriber_count', 0)

    print(f"\nFetching metadata for {len(video_ids)} videos...")

    batches = [video_ids[i:i + MAX_RESULTS_PER_PAGE]
               for i in range(0, len(video_ids), MAX_RESULTS_PER_PAGE)]

    for batch in progress_bar(batches, desc="Fetching"):
        response = retry_with_backoff(lambda b=batch: youtube.videos().list(
            part='snippet,statistics,contentDetails,topicDetails,status',
            id=','.join(b)
        ).execute())

        for item in response.get('items', []):
            stats = item.get('statistics', {})
            view_count = int(stats.get('viewCount', 0))

            if min_views and view_count < min_views:
                continue

            snippet = item['snippet']
            content_details = item.get('contentDetails', {})
            status = item.get('status', {})

            like_count = int(stats.get('likeCount', 0))
            comment_count = int(stats.get('commentCount', 0))
            engagement_rate = ((like_count + comment_count) / view_count * 100) if view_count > 0 else 0
            duration_seconds = parse_duration(content_details.get('duration', ''))

            title_patterns = analyze_title_patterns(snippet['title'])
            title_formula = extract_title_formula(snippet['title'])
            series_info = detect_series(snippet['title'])
            collab_info = detect_collaboration(snippet['title'], snippet.get('description', ''))
            description_links = extract_links_from_description(snippet.get('description', ''))

            category_name = VIDEO_CATEGORIES.get(snippet.get('categoryId', ''), 'Unknown')
            revenue_est = estimate_revenue({'view_count': view_count}, category_name)

            video_data = {
                'video_id': item['id'],
                'title': snippet['title'],
                'description': snippet.get('description', ''),
                'publish_date': snippet['publishedAt'],
                'channel_id': snippet['channelId'],
                'channel_title': snippet['channelTitle'],

                'view_count': view_count,
                'like_count': like_count,
                'comment_count': comment_count,
                'engagement_rate': round(engagement_rate, 4),

                'duration_seconds': duration_seconds,
                'duration_formatted': format_duration(duration_seconds),
                'definition': content_details.get('definition', ''),
                'caption': content_details.get('caption', 'false'),

                'category_id': snippet.get('categoryId', ''),
                'category_name': category_name,
                'tags': snippet.get('tags', []),
                'tags_count': len(snippet.get('tags', [])),

                'thumbnail_default': snippet.get('thumbnails', {}).get('default', {}).get('url', ''),
                'thumbnail_high': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                'thumbnail_maxres': snippet.get('thumbnails', {}).get('maxres', {}).get('url', ''),

                'publish_day_of_week': '',
                'publish_hour': 0,
                'publish_month': '',
                'title_length': len(snippet['title']),
                'description_length': len(snippet.get('description', '')),
                'has_tags': len(snippet.get('tags', [])) > 0,
                'is_short': 0 < duration_seconds <= 60,
                'is_long_form': duration_seconds > 600,

                'title_hook_score': title_patterns['title_hook_score'],
                'title_has_number': title_patterns['has_number'],
                'title_is_question': title_patterns['is_question'],
                'title_has_emotional_word': title_patterns['has_emotional_word'],
                'title_has_brackets': title_patterns['has_brackets'] or title_patterns['has_parentheses'],
                'title_formula': title_formula,

                'is_series': series_info['is_series'],
                'series_number': series_info['series_number'],
                'is_collab': collab_info['is_collab'],

                'description_link_count': description_links['total_links'],
                'has_affiliate_links': description_links['has_affiliate_links'],

                'estimated_revenue_low': revenue_est['estimated_revenue_low'],
                'estimated_revenue_mid': revenue_est['estimated_revenue_mid'],
                'estimated_revenue_high': revenue_est['estimated_revenue_high'],

                'virality_score': 0.0,
            }

            try:
                pub_date = datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00'))
                video_data['publish_day_of_week'] = pub_date.strftime('%A')
                video_data['publish_hour'] = pub_date.hour
                video_data['publish_month'] = pub_date.strftime('%B')
            except:
                pass

            video_data['virality_score'] = calculate_virality_score(video_data, channel_subscribers)

            all_videos.append(video_data)

    return all_videos


# =============================================================================
# ANALYTICS
# =============================================================================

def generate_analytics(videos: list[dict], channel_info: dict) -> dict:
    if not videos:
        return {}

    analytics = {
        'overview': {},
        'top_videos': {},
        'viral_videos': {},
        'posting_schedule': {},
        'content_analysis': {},
        'shorts_analysis': {},
        'long_form_analysis': {},
        'title_analysis': {},
        'keyword_analysis': {},
        'series_analysis': {},
        'collab_analysis': {},
        'revenue_analysis': {},
        'seasonality': {},
        'consistency': {},
        'health_score': {},
        'publishing_gaps': {},
        'recommendations': []
    }

    # Overview
    total_views = sum(v['view_count'] for v in videos)
    total_likes = sum(v['like_count'] for v in videos)
    total_comments = sum(v['comment_count'] for v in videos)
    avg_views = total_views // len(videos)
    avg_engagement = sum(v['engagement_rate'] for v in videos) / len(videos)
    avg_virality = sum(v['virality_score'] for v in videos) / len(videos)

    analytics['overview'] = {
        'total_videos_analyzed': len(videos),
        'total_views': total_views,
        'total_likes': total_likes,
        'total_comments': total_comments,
        'average_views_per_video': avg_views,
        'average_engagement_rate': round(avg_engagement, 4),
        'average_virality_score': round(avg_virality, 4),
        'channel_subscribers': channel_info.get('subscriber_count', 0),
    }

    # Top videos
    sorted_by_views = sorted(videos, key=lambda x: x['view_count'], reverse=True)
    sorted_by_virality = sorted(videos, key=lambda x: x['virality_score'], reverse=True)

    analytics['top_videos'] = {
        'by_views': [{'title': v['title'], 'video_id': v['video_id'],
                      'views': v['view_count'], 'virality': v['virality_score']}
                     for v in sorted_by_views[:10]],
        'by_virality': [{'title': v['title'], 'video_id': v['video_id'],
                        'virality': v['virality_score'], 'views': v['view_count']}
                       for v in sorted_by_virality[:10]],
    }

    # Viral videos
    viral_videos = [v for v in videos if v['virality_score'] > 1.0]
    analytics['viral_videos'] = {
        'count': len(viral_videos),
        'percentage': round(len(viral_videos) / len(videos) * 100, 2),
        'videos': [{'title': v['title'], 'video_id': v['video_id'],
                   'virality': v['virality_score']} for v in sorted_by_virality[:15]],
    }

    # Posting schedule
    day_counts = Counter(v['publish_day_of_week'] for v in videos if v['publish_day_of_week'])
    hour_counts = Counter(v['publish_hour'] for v in videos)

    day_performance = {}
    for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
        day_videos = [v for v in videos if v['publish_day_of_week'] == day]
        if day_videos:
            day_performance[day] = {
                'count': len(day_videos),
                'avg_views': sum(v['view_count'] for v in day_videos) // len(day_videos),
                'avg_virality': round(sum(v['virality_score'] for v in day_videos) / len(day_videos), 4),
            }

    # Publishing frequency
    if len(videos) >= 2:
        dates = sorted([datetime.fromisoformat(v['publish_date'].replace('Z', '+00:00')) for v in videos])
        total_days = (dates[-1] - dates[0]).days or 1
        videos_per_week = len(videos) / (total_days / 7)
    else:
        videos_per_week = 0

    analytics['posting_schedule'] = {
        'videos_by_day': dict(day_counts),
        'videos_by_hour': dict(sorted(hour_counts.items())),
        'day_performance': day_performance,
        'best_day_by_views': max(day_performance.items(), key=lambda x: x[1]['avg_views'])[0] if day_performance else None,
        'best_day_by_virality': max(day_performance.items(), key=lambda x: x[1]['avg_virality'])[0] if day_performance else None,
        'videos_per_week': round(videos_per_week, 2),
    }

    # Publishing gaps
    all_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    analytics['publishing_gaps'] = {
        'low_competition_days': [d for d in all_days if day_counts.get(d, 0) < len(videos) / 14],
        'high_performance_gaps': [
            {'day': d, 'virality': day_performance[d]['avg_virality']}
            for d in all_days
            if d in day_performance and day_counts.get(d, 0) < len(videos) / 10
            and day_performance[d]['avg_virality'] > avg_virality
        ]
    }

    # Content analysis
    durations = [v['duration_seconds'] for v in videos if v['duration_seconds'] > 0]
    avg_duration = sum(durations) // len(durations) if durations else 0

    duration_buckets = {
        'shorts': len([v for v in videos if v['is_short']]),
        'short': len([v for v in videos if 60 < v['duration_seconds'] <= 300]),
        'medium': len([v for v in videos if 300 < v['duration_seconds'] <= 900]),
        'long': len([v for v in videos if 900 < v['duration_seconds'] <= 1800]),
        'very_long': len([v for v in videos if v['duration_seconds'] > 1800]),
    }

    analytics['content_analysis'] = {
        'average_duration_seconds': avg_duration,
        'average_duration_formatted': format_duration(avg_duration),
        'duration_distribution': duration_buckets,
        'category_distribution': dict(Counter(v['category_name'] for v in videos).most_common()),
        'hd_videos': len([v for v in videos if v['definition'] == 'hd']),
        'videos_with_captions': len([v for v in videos if v['caption'] == 'true']),
    }

    # Shorts analysis
    shorts = [v for v in videos if v['is_short']]
    if shorts:
        analytics['shorts_analysis'] = {
            'count': len(shorts),
            'percentage': round(len(shorts) / len(videos) * 100, 2),
            'avg_views': sum(v['view_count'] for v in shorts) // len(shorts),
            'avg_virality': round(sum(v['virality_score'] for v in shorts) / len(shorts), 4),
        }
    else:
        analytics['shorts_analysis'] = {'count': 0, 'percentage': 0}

    # Long-form analysis
    long_form = [v for v in videos if v['is_long_form']]
    if long_form:
        analytics['long_form_analysis'] = {
            'count': len(long_form),
            'percentage': round(len(long_form) / len(videos) * 100, 2),
            'avg_views': sum(v['view_count'] for v in long_form) // len(long_form),
            'avg_virality': round(sum(v['virality_score'] for v in long_form) / len(long_form), 4),
        }
    else:
        analytics['long_form_analysis'] = {'count': 0, 'percentage': 0}

    # Title analysis
    title_pattern_performance = {}
    for pattern, field in [('questions', 'title_is_question'), ('numbers', 'title_has_number'),
                           ('emotional', 'title_has_emotional_word'), ('brackets', 'title_has_brackets')]:
        pattern_videos = [v for v in videos if v.get(field)]
        if pattern_videos:
            title_pattern_performance[pattern] = {
                'count': len(pattern_videos),
                'avg_views': sum(v['view_count'] for v in pattern_videos) // len(pattern_videos),
                'avg_virality': round(sum(v['virality_score'] for v in pattern_videos) / len(pattern_videos), 4),
            }

    analytics['title_analysis'] = {
        'pattern_performance': title_pattern_performance,
        'common_formulas': dict(Counter(v['title_formula'] for v in videos).most_common(10)),
        'avg_title_length': sum(v['title_length'] for v in videos) // len(videos),
        'avg_hook_score': round(sum(v['title_hook_score'] for v in videos) / len(videos), 2),
    }

    # Keyword analysis
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                  'of', 'with', 'by', 'from', 'is', 'it', 'this', 'that', 'i', 'you', 'we'}

    title_words = []
    for v in videos:
        words = re.findall(r'\b\w+\b', v['title'].lower())
        title_words.extend([w for w in words if w not in stop_words and len(w) > 2])

    all_tags = []
    for v in videos:
        all_tags.extend([t.lower() for t in v.get('tags', [])])

    top_videos_words = []
    for v in sorted_by_virality[:max(len(videos) // 5, 1)]:
        words = re.findall(r'\b\w+\b', v['title'].lower())
        top_videos_words.extend([w for w in words if w not in stop_words and len(w) > 2])

    analytics['keyword_analysis'] = {
        'top_title_words': dict(Counter(title_words).most_common(30)),
        'top_tags': dict(Counter(all_tags).most_common(30)),
        'high_performing_keywords': dict(Counter(top_videos_words).most_common(20)),
    }

    # Series analysis
    series_videos = [v for v in videos if v['is_series']]
    analytics['series_analysis'] = {
        'count': len(series_videos),
        'percentage': round(len(series_videos) / len(videos) * 100, 2),
        'avg_virality': round(sum(v['virality_score'] for v in series_videos) / len(series_videos), 4) if series_videos else 0,
    }

    # Collab analysis
    collab_videos = [v for v in videos if v['is_collab']]
    analytics['collab_analysis'] = {
        'count': len(collab_videos),
        'percentage': round(len(collab_videos) / len(videos) * 100, 2),
        'avg_virality': round(sum(v['virality_score'] for v in collab_videos) / len(collab_videos), 4) if collab_videos else 0,
        'videos': [{'title': v['title'], 'virality': v['virality_score']}
                   for v in sorted(collab_videos, key=lambda x: x['virality_score'], reverse=True)[:5]]
    }

    # Revenue analysis
    total_revenue_low = sum(v['estimated_revenue_low'] for v in videos)
    total_revenue_mid = sum(v['estimated_revenue_mid'] for v in videos)
    total_revenue_high = sum(v['estimated_revenue_high'] for v in videos)

    analytics['revenue_analysis'] = {
        'total_estimated_low': round(total_revenue_low, 2),
        'total_estimated_mid': round(total_revenue_mid, 2),
        'total_estimated_high': round(total_revenue_high, 2),
        'avg_per_video_mid': round(total_revenue_mid / len(videos), 2),
        'top_earners': [{'title': v['title'], 'views': v['view_count'],
                        'estimated_revenue': v['estimated_revenue_mid']}
                       for v in sorted(videos, key=lambda x: x['estimated_revenue_mid'], reverse=True)[:10]]
    }

    # Seasonality
    analytics['seasonality'] = analyze_seasonality(videos)

    # Consistency
    analytics['consistency'] = calculate_upload_consistency(videos)

    # Health score
    analytics['health_score'] = calculate_channel_health_score(channel_info, analytics)

    # Traffic drivers analysis - find what makes your best videos work
    analytics['traffic_drivers'] = analyze_traffic_drivers(videos, channel_info)

    # Recommendations
    recommendations = []

    if analytics['posting_schedule']['best_day_by_virality']:
        recommendations.append(
            f"Best posting day: {analytics['posting_schedule']['best_day_by_virality']} (highest virality)"
        )

    if analytics['publishing_gaps']['high_performance_gaps']:
        gap = analytics['publishing_gaps']['high_performance_gaps'][0]
        recommendations.append(
            f"Opportunity: {gap['day']} has low competition but high performance"
        )

    if analytics['seasonality'].get('best_month_by_virality'):
        recommendations.append(
            f"Best month: {analytics['seasonality']['best_month_by_virality']}"
        )

    shorts_virality = analytics['shorts_analysis'].get('avg_virality', 0)
    long_virality = analytics['long_form_analysis'].get('avg_virality', 0)
    if shorts_virality > long_virality * 1.5 and shorts_virality > 0:
        recommendations.append("Shorts outperform long-form - consider more short content")
    elif long_virality > shorts_virality * 1.5 and long_virality > 0:
        recommendations.append("Long-form outperforms Shorts - focus on in-depth content")

    if analytics['collab_analysis']['count'] > 0:
        if analytics['collab_analysis']['avg_virality'] > avg_virality:
            recommendations.append("Collaborations perform above average - do more collabs")

    if analytics['series_analysis']['count'] > 0:
        if analytics['series_analysis']['avg_virality'] > avg_virality:
            recommendations.append("Series content performs well - create more series")

    top_keywords = list(analytics['keyword_analysis']['high_performing_keywords'].keys())[:5]
    if top_keywords:
        recommendations.append(f"High-performing keywords: {', '.join(top_keywords)}")

    analytics['recommendations'] = recommendations

    return analytics


def cluster_videos_by_topic(videos: list[dict], num_clusters: int = 10) -> dict:
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}

    video_keywords = []
    for v in videos:
        words = set(re.findall(r'\b\w+\b', v['title'].lower()))
        words = {w for w in words if w not in stop_words and len(w) > 3}
        video_keywords.append(words)

    all_keywords = Counter()
    for keywords in video_keywords:
        all_keywords.update(keywords)

    top_keywords = [kw for kw, _ in all_keywords.most_common(num_clusters * 3)]

    clusters = defaultdict(list)
    for i, v in enumerate(videos):
        keywords = video_keywords[i]
        for cluster_keyword in top_keywords:
            if cluster_keyword in keywords:
                clusters[cluster_keyword].append({
                    'video_id': v['video_id'],
                    'title': v['title'],
                    'views': v['view_count'],
                    'virality_score': v['virality_score'],
                })
                break

    sorted_clusters = sorted(clusters.items(), key=lambda x: sum(v['views'] for v in x[1]), reverse=True)[:num_clusters]

    return {
        'clusters': {
            topic: {
                'videos': vids,
                'count': len(vids),
                'total_views': sum(v['views'] for v in vids),
                'avg_virality': round(sum(v['virality_score'] for v in vids) / len(vids), 4) if vids else 0,
            }
            for topic, vids in sorted_clusters
        }
    }


# =============================================================================
# WEBHOOK ALERTS
# =============================================================================

def send_discord_webhook(webhook_url: str, message: str, embeds: list = None) -> bool:
    """Send notification to Discord webhook."""
    try:
        data = {'content': message}
        if embeds:
            data['embeds'] = embeds

        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Discord webhook error: {e}")
        return False


def send_slack_webhook(webhook_url: str, message: str, blocks: list = None) -> bool:
    """Send notification to Slack webhook."""
    try:
        data = {'text': message}
        if blocks:
            data['blocks'] = blocks

        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Slack webhook error: {e}")
        return False


def send_new_video_alert(config: dict, channel_name: str, new_videos: list[dict]) -> None:
    """Send alerts for new videos."""
    if not new_videos:
        return

    message = f"🎬 **{channel_name}** posted {len(new_videos)} new video(s)!\n\n"
    for v in new_videos[:5]:
        message += f"• {v['title']}\n  Views: {format_number(v['view_count'])}\n"
        message += f"  https://youtube.com/watch?v={v['video_id']}\n\n"

    # Discord
    discord_url = config.get('webhooks', {}).get('discord')
    if discord_url:
        send_discord_webhook(discord_url, message)
        print("Sent Discord alert")

    # Slack
    slack_url = config.get('webhooks', {}).get('slack')
    if slack_url:
        send_slack_webhook(slack_url, message.replace('**', '*'))
        print("Sent Slack alert")


# =============================================================================
# OUTPUT FUNCTIONS
# =============================================================================

def save_to_csv(videos: list[dict], output_path: str) -> None:
    if not videos:
        return

    videos_for_csv = []
    for v in videos:
        v_copy = v.copy()
        v_copy['tags'] = '|'.join(v_copy.get('tags', []))
        videos_for_csv.append(v_copy)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(videos_for_csv[0].keys()))
        writer.writeheader()
        writer.writerows(videos_for_csv)

    print(f"Saved CSV: {output_path}")


def save_to_json(data: dict, output_path: str) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"Saved JSON: {output_path}")


def save_to_markdown(analytics: dict, channel_info: dict, output_path: str) -> None:
    """Save report as Markdown."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# Competitive Analysis: {channel_info.get('title', 'Unknown')}\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        # Health Score
        health = analytics.get('health_score', {})
        f.write(f"## Channel Health Score: {health.get('total_score', 0)}/100 ({health.get('grade', 'N/A')})\n\n")

        breakdown = health.get('breakdown', {})
        f.write("| Metric | Score |\n|--------|-------|\n")
        for metric, score in breakdown.items():
            f.write(f"| {metric.title()} | {score}/25 |\n")
        f.write("\n")

        # Overview
        overview = analytics.get('overview', {})
        f.write("## Overview\n\n")
        f.write(f"- **Subscribers**: {format_number(channel_info.get('subscriber_count', 0))}\n")
        f.write(f"- **Videos Analyzed**: {format_number(overview.get('total_videos_analyzed', 0))}\n")
        f.write(f"- **Total Views**: {format_number(overview.get('total_views', 0))}\n")
        f.write(f"- **Avg Views/Video**: {format_number(overview.get('average_views_per_video', 0))}\n")
        f.write(f"- **Avg Virality**: {overview.get('average_virality_score', 0):.4f}\n")
        f.write(f"- **Avg Engagement**: {overview.get('average_engagement_rate', 0):.2%}\n\n")

        # Revenue
        revenue = analytics.get('revenue_analysis', {})
        f.write("## Estimated Revenue\n\n")
        f.write(f"- **Low Estimate**: {format_currency(revenue.get('total_estimated_low', 0))}\n")
        f.write(f"- **Mid Estimate**: {format_currency(revenue.get('total_estimated_mid', 0))}\n")
        f.write(f"- **High Estimate**: {format_currency(revenue.get('total_estimated_high', 0))}\n\n")

        # Top Videos
        f.write("## Top Viral Videos\n\n")
        f.write("| Title | Views | Virality |\n|-------|-------|----------|\n")
        for v in analytics.get('viral_videos', {}).get('videos', [])[:10]:
            title = v.get('title', '')[:50]
            f.write(f"| {title} | {format_number(v.get('views', 0))} | {v.get('virality', 0):.2f} |\n")
        f.write("\n")

        # Recommendations
        f.write("## Recommendations\n\n")
        for rec in analytics.get('recommendations', []):
            f.write(f"- {rec}\n")

        # Competitor Analysis (if available)
        neighborhood = analytics.get('neighborhood')
        if neighborhood:
            competitors = neighborhood.get('competitors', {}).get('competitors', [])
            if competitors:
                f.write("\n## Competitor Channels\n\n")
                f.write("| Channel | Relevance Score | Discovery Reason |\n")
                f.write("|---------|-----------------|------------------|\n")
                for comp in competitors[:15]:
                    reason = comp.get('discovery_reasons', ['N/A'])[0] if comp.get('discovery_reasons') else 'N/A'
                    f.write(f"| {comp['title'][:40]} | {comp['relevance_score']} | {reason[:40]} |\n")

            network = neighborhood.get('video_network', {})
            stats = network.get('network_stats', {})
            if stats:
                f.write("\n## Video Network Analysis\n\n")
                f.write(f"- **Videos Analyzed**: {stats.get('videos_analyzed', 0)}\n")
                f.write(f"- **Unique Related Channels**: {stats.get('unique_related_channels', 0)}\n")
                f.write(f"- **Most Connected Channel**: {stats.get('most_connected_channel', 'N/A')}\n")
                f.write(f"- **Avg Connections/Video**: {stats.get('avg_connections_per_video', 0)}\n")

            insights = neighborhood.get('insights', [])
            if insights:
                f.write("\n### Network Insights\n\n")
                for insight in insights:
                    f.write(f"- {insight}\n")

    print(f"Saved Markdown: {output_path}")


def generate_competitors_html(analytics: dict) -> str:
    """Generate HTML section for competitor analysis."""
    neighborhood = analytics.get('neighborhood')
    if not neighborhood:
        return ""

    competitors = neighborhood.get('competitors', {}).get('competitors', [])
    network = neighborhood.get('video_network', {})
    network_stats = network.get('network_stats', {})
    insights = neighborhood.get('insights', [])

    if not competitors and not network_stats:
        return ""

    html = '''
        <div class="chart-container" style="margin-top: 30px;">
            <h3>🎯 Competitor Channels</h3>
    '''

    if competitors:
        html += '''
            <table>
                <tr><th>Channel</th><th>Relevance</th><th>Why Related</th></tr>
        '''
        for comp in competitors[:15]:
            reason = comp.get('discovery_reasons', ['N/A'])[0] if comp.get('discovery_reasons') else 'N/A'
            html += f"<tr><td>{comp['title'][:50]}</td><td>{comp['relevance_score']}</td><td>{reason[:50]}</td></tr>"
        html += '</table>'

    html += '</div>'

    if network_stats.get('unique_related_channels'):
        html += f'''
        <div class="chart-container">
            <h3>🌐 Video Network Analysis</h3>
            <div class="grid" style="margin-top:15px;">
                <div class="card">
                    <h3>Unique Related Channels</h3>
                    <div class="value">{network_stats.get('unique_related_channels', 0)}</div>
                </div>
                <div class="card">
                    <h3>Most Connected</h3>
                    <div class="value" style="font-size:1.2em">{network_stats.get('most_connected_channel', 'N/A')[:25]}</div>
                    <div class="subvalue">{network_stats.get('most_connected_appearances', 0)} appearances</div>
                </div>
                <div class="card">
                    <h3>Avg Connections/Video</h3>
                    <div class="value">{network_stats.get('avg_connections_per_video', 0)}</div>
                </div>
            </div>
        '''

        # Add related channels table
        related_channels = network.get('related_channels', [])
        if related_channels:
            html += f'''
            <div style="margin-top:25px;">
                <h4>📡 Related Channels in Your Network ({len(related_channels)} channels found)</h4>
                <p style="color:#a0aec0;font-size:0.9em;margin-bottom:15px;">
                    These channels appear in YouTube's recommendations alongside your content.
                    Higher appearances = stronger content relationship.
                </p>
                <table>
                    <tr>
                        <th>Channel</th>
                        <th>Appearances</th>
                        <th>Connection Strength</th>
                        <th>Sample Related Videos</th>
                    </tr>
            '''
            for ch in related_channels:  # Show all related channels
                appearances = ch.get('appearances', 0)
                # Calculate connection strength
                if appearances >= 5:
                    strength = '<span style="color:#38ef7d;">●●●●● Strong</span>'
                elif appearances >= 3:
                    strength = '<span style="color:#ffc107;">●●●○○ Medium</span>'
                else:
                    strength = '<span style="color:#a0aec0;">●○○○○ Weak</span>'

                # Get sample videos
                videos_list = ch.get('videos', [])
                sample_videos = ', '.join([v.get('related_video', '')[:30] + '...' for v in videos_list[:2]]) if videos_list else 'N/A'

                html += f'''
                    <tr>
                        <td><strong>{ch.get('title', 'Unknown')[:40]}</strong></td>
                        <td style="text-align:center;">{appearances}</td>
                        <td>{strength}</td>
                        <td style="font-size:0.85em;color:#a0aec0;">{sample_videos[:60]}</td>
                    </tr>
                '''
            html += '</table>'

            # Add explanation
            html += '''
            <div style="margin-top:15px;padding:15px;background:rgba(102,126,234,0.1);border-radius:8px;">
                <strong>💡 How to use this data:</strong>
                <ul style="margin:10px 0 0 20px;color:#a0aec0;">
                    <li>Channels with high appearances are your closest content neighbors</li>
                    <li>Consider collaborating with strongly connected channels</li>
                    <li>Study their content strategy - you share the same audience</li>
                    <li>These are potential competitors OR collaboration partners</li>
                </ul>
            </div>
            '''
            html += '</div>'

        if insights:
            html += '<div style="margin-top:20px;"><h4>🔍 Network Insights</h4><ul>'
            for insight in insights:
                html += f'<li style="margin:8px 0;">{insight}</li>'
            html += '</ul></div>'

        html += '</div>'

    return html


def save_to_html_dashboard(videos: list[dict], analytics: dict, channel_info: dict,
                           output_path: str, clusters: dict = None) -> None:
    """Generate interactive HTML dashboard with charts."""

    # Prepare data for charts
    day_data = analytics.get('posting_schedule', {}).get('day_performance', {})
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_views = [day_data.get(d, {}).get('avg_views', 0) for d in days]
    day_virality = [day_data.get(d, {}).get('avg_virality', 0) for d in days]

    monthly_data = analytics.get('seasonality', {}).get('monthly_performance', {})
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    month_views = [monthly_data.get(m, {}).get('avg_views', 0) for m in months]

    # Year-month data for detailed chart
    year_month_data = analytics.get('seasonality', {}).get('year_month_performance', {})
    year_month_labels = list(year_month_data.keys())[-24:]  # Last 24 months
    year_month_views = [year_month_data.get(ym, {}).get('avg_views', 0) for ym in year_month_labels]
    year_month_counts = [year_month_data.get(ym, {}).get('count', 0) for ym in year_month_labels]

    # Yearly performance
    yearly_data = analytics.get('seasonality', {}).get('yearly_performance', {})
    years = list(yearly_data.keys())
    year_views = [yearly_data.get(y, {}).get('avg_views', 0) for y in years]
    year_counts = [yearly_data.get(y, {}).get('count', 0) for y in years]

    # YoY comparison
    yoy_data = analytics.get('seasonality', {}).get('yoy_comparison', {})

    top_videos = analytics.get('top_videos', {}).get('by_views', [])[:10]
    top_titles = [v['title'][:30] + '...' if len(v['title']) > 30 else v['title'] for v in top_videos]
    top_views = [v['views'] for v in top_videos]

    duration_dist = analytics.get('content_analysis', {}).get('duration_distribution', {})

    health = analytics.get('health_score', {})
    health_breakdown = health.get('breakdown', {})

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Analysis: {channel_info.get('title', 'Channel')}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ text-align: center; margin-bottom: 30px; font-size: 2.5em; }}
        .health-score {{
            text-align: center;
            padding: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 20px;
            margin-bottom: 30px;
        }}
        .health-score .score {{ font-size: 4em; font-weight: bold; }}
        .health-score .grade {{ font-size: 2em; opacity: 0.9; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }}
        .card h3 {{ margin-bottom: 15px; color: #a0aec0; font-size: 0.9em; text-transform: uppercase; }}
        .card .value {{ font-size: 2em; font-weight: bold; }}
        .card .subvalue {{ color: #a0aec0; font-size: 0.9em; }}
        .chart-container {{
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .chart-container h3 {{ margin-bottom: 15px; }}
        .chart-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        th {{ color: #a0aec0; font-weight: 500; }}
        .recommendations {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            border-radius: 15px;
            padding: 25px;
            margin-top: 30px;
        }}
        .recommendations h3 {{ margin-bottom: 15px; }}
        .recommendations li {{ margin: 10px 0; padding-left: 10px; }}
        .revenue {{ color: #38ef7d; }}
        .footer {{ text-align: center; margin-top: 40px; opacity: 0.6; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 {channel_info.get('title', 'Channel')} Analysis</h1>

        <div class="health-score">
            <div class="score">{health.get('total_score', 0):.0f}</div>
            <div class="grade">Grade: {health.get('grade', 'N/A')}</div>
            <p style="margin-top:10px;opacity:0.8">Channel Health Score</p>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Subscribers</h3>
                <div class="value">{format_number(channel_info.get('subscriber_count', 0))}</div>
            </div>
            <div class="card">
                <h3>Videos Analyzed</h3>
                <div class="value">{format_number(analytics.get('overview', {}).get('total_videos_analyzed', 0))}</div>
            </div>
            <div class="card">
                <h3>Total Views</h3>
                <div class="value">{format_number(analytics.get('overview', {}).get('total_views', 0))}</div>
            </div>
            <div class="card">
                <h3>Avg Views/Video</h3>
                <div class="value">{format_number(analytics.get('overview', {}).get('average_views_per_video', 0))}</div>
            </div>
            <div class="card">
                <h3>Avg Virality Score</h3>
                <div class="value">{analytics.get('overview', {}).get('average_virality_score', 0):.3f}</div>
                <div class="subvalue">&gt;1.0 = Viral</div>
            </div>
            <div class="card">
                <h3>Viral Videos</h3>
                <div class="value">{analytics.get('viral_videos', {}).get('count', 0)}</div>
                <div class="subvalue">{analytics.get('viral_videos', {}).get('percentage', 0):.1f}% of total</div>
            </div>
            <div class="card">
                <h3>Est. Revenue (Mid)</h3>
                <div class="value revenue">{format_currency(analytics.get('revenue_analysis', {}).get('total_estimated_mid', 0))}</div>
                <div class="subvalue">Range: {format_currency(analytics.get('revenue_analysis', {}).get('total_estimated_low', 0))} - {format_currency(analytics.get('revenue_analysis', {}).get('total_estimated_high', 0))}</div>
            </div>
            <div class="card">
                <h3>Upload Consistency</h3>
                <div class="value">{analytics.get('consistency', {}).get('consistency_score', 0):.0f}/100</div>
                <div class="subvalue">Avg {analytics.get('consistency', {}).get('avg_days_between', 0):.1f} days between uploads</div>
            </div>
        </div>

        <div class="chart-row">
            <div class="chart-container">
                <h3>📅 Performance by Day of Week</h3>
                <canvas id="dayChart"></canvas>
            </div>
            <div class="chart-container">
                <h3>📆 Performance by Month (All Years)</h3>
                <canvas id="monthChart"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <h3>📊 Performance by Month & Year (Last 24 Months)</h3>
            <canvas id="yearMonthChart"></canvas>
        </div>

        <div class="chart-row">
            <div class="chart-container">
                <h3>📈 Yearly Performance</h3>
                <canvas id="yearlyChart"></canvas>
            </div>
            <div class="chart-container">
                <h3>🔄 Year-over-Year Comparison</h3>
                {''.join(f"""
                <div style="background:rgba(255,255,255,0.05);border-radius:10px;padding:15px;margin:10px 0;">
                    <h4 style="color:#667eea;margin-bottom:10px;">{period}</h4>
                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:15px;">
                        <div>
                            <div style="color:#a0aec0;font-size:0.85em;">Avg Views</div>
                            <div style="font-size:1.3em;color:{'#38ef7d' if data['views_change_pct'] > 0 else '#ff6b6b'};">
                                {'+' if data['views_change_pct'] > 0 else ''}{data['views_change_pct']}%
                            </div>
                            <div style="font-size:0.8em;color:#a0aec0;">{format_number(data['prev_avg_views'])} → {format_number(data['curr_avg_views'])}</div>
                        </div>
                        <div>
                            <div style="color:#a0aec0;font-size:0.85em;">Virality</div>
                            <div style="font-size:1.3em;color:{'#38ef7d' if data['virality_change_pct'] > 0 else '#ff6b6b'};">
                                {'+' if data['virality_change_pct'] > 0 else ''}{data['virality_change_pct']}%
                            </div>
                        </div>
                        <div>
                            <div style="color:#a0aec0;font-size:0.85em;">Uploads</div>
                            <div style="font-size:1.3em;color:{'#38ef7d' if data['upload_change_pct'] > 0 else '#ff6b6b'};">
                                {'+' if data['upload_change_pct'] > 0 else ''}{data['upload_change_pct']}%
                            </div>
                            <div style="font-size:0.8em;color:#a0aec0;">{data['prev_uploads']} → {data['curr_uploads']} videos</div>
                        </div>
                    </div>
                </div>
                """ for period, data in yoy_data.items()) if yoy_data else '<p style="color:#a0aec0;">Not enough data for YoY comparison (need 2+ years)</p>'}
            </div>
        </div>

        <div class="chart-row">
            <div class="chart-container">
                <h3>🎬 Top 10 Videos by Views</h3>
                <canvas id="topVideosChart"></canvas>
            </div>
            <div class="chart-container">
                <h3>⏱️ Video Duration Distribution</h3>
                <canvas id="durationChart"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <h3>💪 Health Score Breakdown</h3>
            <canvas id="healthChart" style="max-height:300px"></canvas>
        </div>

        <div class="chart-container">
            <h3>🔥 Top Viral Videos</h3>
            <table>
                <tr><th>Title</th><th>Views</th><th>Virality</th><th>Est. Revenue</th></tr>
                {''.join(f"<tr><td>{v['title'][:60]}...</td><td>{format_number(v.get('views', 0))}</td><td>{v.get('virality', 0):.2f}</td><td>{format_currency(v.get('estimated_revenue_mid', 0))}</td></tr>" for v in sorted(videos, key=lambda x: x['virality_score'], reverse=True)[:15])}
            </table>
        </div>

        <div class="recommendations">
            <h3>🎯 Strategic Recommendations</h3>
            <ul>
                {''.join(f"<li>{rec}</li>" for rec in analytics.get('recommendations', []))}
            </ul>
        </div>

        {generate_competitors_html(analytics)}

        {generate_traffic_drivers_html(
            analytics.get('traffic_drivers', {}),
            analytics.get('content_gaps', {}),
            channel_info
        )}

        <div class="footer">
            <p>Generated by YouTube Competitive Analysis Tool | {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
    </div>

    <script>
        const chartColors = {{
            primary: 'rgba(102, 126, 234, 0.8)',
            secondary: 'rgba(118, 75, 162, 0.8)',
            success: 'rgba(56, 239, 125, 0.8)',
            warning: 'rgba(255, 193, 7, 0.8)',
        }};

        // Day of Week Chart
        new Chart(document.getElementById('dayChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(days)},
                datasets: [{{
                    label: 'Avg Views',
                    data: {json.dumps(day_views)},
                    backgroundColor: chartColors.primary,
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ labels: {{ color: '#fff' }} }} }},
                scales: {{
                    y: {{ ticks: {{ color: '#a0aec0' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                    x: {{ ticks: {{ color: '#a0aec0' }}, grid: {{ display: false }} }}
                }}
            }}
        }});

        // Monthly Chart (all years combined)
        new Chart(document.getElementById('monthChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(months)},
                datasets: [{{
                    label: 'Avg Views',
                    data: {json.dumps(month_views)},
                    borderColor: chartColors.success,
                    backgroundColor: 'rgba(56, 239, 125, 0.2)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ labels: {{ color: '#fff' }} }} }},
                scales: {{
                    y: {{ ticks: {{ color: '#a0aec0' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                    x: {{ ticks: {{ color: '#a0aec0' }}, grid: {{ display: false }} }}
                }}
            }}
        }});

        // Year-Month Chart (detailed timeline)
        new Chart(document.getElementById('yearMonthChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(year_month_labels)},
                datasets: [{{
                    label: 'Avg Views',
                    data: {json.dumps(year_month_views)},
                    backgroundColor: chartColors.primary,
                    yAxisID: 'y',
                }}, {{
                    label: 'Videos Published',
                    data: {json.dumps(year_month_counts)},
                    type: 'line',
                    borderColor: chartColors.warning,
                    backgroundColor: 'transparent',
                    yAxisID: 'y1',
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ labels: {{ color: '#fff' }} }} }},
                scales: {{
                    y: {{
                        type: 'linear',
                        position: 'left',
                        ticks: {{ color: '#a0aec0' }},
                        grid: {{ color: 'rgba(255,255,255,0.1)' }},
                        title: {{ display: true, text: 'Avg Views', color: '#a0aec0' }}
                    }},
                    y1: {{
                        type: 'linear',
                        position: 'right',
                        ticks: {{ color: '#ffc107' }},
                        grid: {{ display: false }},
                        title: {{ display: true, text: 'Videos', color: '#ffc107' }}
                    }},
                    x: {{ ticks: {{ color: '#a0aec0', maxRotation: 45 }}, grid: {{ display: false }} }}
                }}
            }}
        }});

        // Yearly Performance Chart
        new Chart(document.getElementById('yearlyChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps([str(y) for y in years])},
                datasets: [{{
                    label: 'Avg Views',
                    data: {json.dumps(year_views)},
                    backgroundColor: chartColors.secondary,
                    yAxisID: 'y',
                }}, {{
                    label: 'Videos Published',
                    data: {json.dumps(year_counts)},
                    type: 'line',
                    borderColor: chartColors.success,
                    backgroundColor: 'transparent',
                    yAxisID: 'y1',
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ labels: {{ color: '#fff' }} }} }},
                scales: {{
                    y: {{
                        type: 'linear',
                        position: 'left',
                        ticks: {{ color: '#a0aec0' }},
                        grid: {{ color: 'rgba(255,255,255,0.1)' }},
                        title: {{ display: true, text: 'Avg Views', color: '#a0aec0' }}
                    }},
                    y1: {{
                        type: 'linear',
                        position: 'right',
                        ticks: {{ color: '#38ef7d' }},
                        grid: {{ display: false }},
                        title: {{ display: true, text: 'Videos', color: '#38ef7d' }}
                    }},
                    x: {{ ticks: {{ color: '#a0aec0' }}, grid: {{ display: false }} }}
                }}
            }}
        }});

        // Top Videos Chart
        new Chart(document.getElementById('topVideosChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(top_titles)},
                datasets: [{{
                    label: 'Views',
                    data: {json.dumps(top_views)},
                    backgroundColor: chartColors.secondary,
                }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ ticks: {{ color: '#a0aec0' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                    y: {{ ticks: {{ color: '#a0aec0' }}, grid: {{ display: false }} }}
                }}
            }}
        }});

        // Duration Chart
        new Chart(document.getElementById('durationChart'), {{
            type: 'doughnut',
            data: {{
                labels: {json.dumps(list(duration_dist.keys()))},
                datasets: [{{
                    data: {json.dumps(list(duration_dist.values()))},
                    backgroundColor: ['#667eea', '#764ba2', '#38ef7d', '#ffc107', '#ff6b6b']
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ labels: {{ color: '#fff' }}, position: 'right' }} }}
            }}
        }});

        // Health Score Chart
        new Chart(document.getElementById('healthChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps([k.title() for k in health_breakdown.keys()])},
                datasets: [{{
                    label: 'Score (out of 25)',
                    data: {json.dumps(list(health_breakdown.values()))},
                    backgroundColor: [chartColors.primary, chartColors.secondary, chartColors.success, chartColors.warning],
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{ max: 25, ticks: {{ color: '#a0aec0' }}, grid: {{ color: 'rgba(255,255,255,0.1)' }} }},
                    x: {{ ticks: {{ color: '#a0aec0' }}, grid: {{ display: false }} }}
                }}
            }}
        }});
    </script>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Saved HTML Dashboard: {output_path}")


def save_to_sqlite(videos: list[dict], analytics: dict, channel_info: dict, output_path: str) -> None:
    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (
        channel_id TEXT PRIMARY KEY, title TEXT, subscriber_count INTEGER,
        video_count INTEGER, view_count INTEGER, fetched_at TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS videos (
        video_id TEXT PRIMARY KEY, channel_id TEXT, title TEXT, publish_date TEXT,
        view_count INTEGER, like_count INTEGER, comment_count INTEGER,
        engagement_rate REAL, duration_seconds INTEGER, virality_score REAL,
        title_hook_score INTEGER, is_short INTEGER, is_series INTEGER, is_collab INTEGER,
        estimated_revenue_mid REAL, thumbnail_high TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS historical_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, snapshot_date TEXT,
        subscriber_count INTEGER, total_views INTEGER, avg_virality REAL
    )''')

    cursor.execute('''INSERT OR REPLACE INTO channels VALUES (?,?,?,?,?,?)''',
        (channel_info['channel_id'], channel_info['title'],
         channel_info.get('subscriber_count', 0), channel_info.get('video_count', 0),
         channel_info.get('view_count', 0), datetime.now().isoformat()))

    for v in videos:
        cursor.execute('''INSERT OR REPLACE INTO videos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (v['video_id'], v['channel_id'], v['title'], v['publish_date'],
             v['view_count'], v['like_count'], v['comment_count'],
             v['engagement_rate'], v['duration_seconds'], v['virality_score'],
             v['title_hook_score'], 1 if v['is_short'] else 0,
             1 if v['is_series'] else 0, 1 if v['is_collab'] else 0,
             v['estimated_revenue_mid'], v['thumbnail_high']))

    cursor.execute('''INSERT INTO historical_snapshots (channel_id, snapshot_date, subscriber_count, total_views, avg_virality) VALUES (?,?,?,?,?)''',
        (channel_info['channel_id'], datetime.now().isoformat(),
         channel_info.get('subscriber_count', 0),
         analytics.get('overview', {}).get('total_views', 0),
         analytics.get('overview', {}).get('average_virality_score', 0)))

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_views ON videos(view_count DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_virality ON videos(virality_score DESC)')

    conn.commit()
    conn.close()
    print(f"Saved SQLite: {output_path}")


def save_to_excel(videos: list[dict], analytics: dict, channel_info: dict, output_path: str) -> None:
    if not EXCEL_AVAILABLE:
        print("Excel export skipped (pip install openpyxl)")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Overview"

    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    ws['A1'] = f"Analysis: {channel_info.get('title', '')}"
    ws['A1'].font = Font(bold=True, size=16)

    health = analytics.get('health_score', {})
    ws['A3'] = f"Health Score: {health.get('total_score', 0):.0f}/100 (Grade: {health.get('grade', 'N/A')})"

    overview_data = [
        ("Subscribers", format_number(channel_info.get('subscriber_count', 0))),
        ("Videos", analytics.get('overview', {}).get('total_videos_analyzed', 0)),
        ("Total Views", format_number(analytics.get('overview', {}).get('total_views', 0))),
        ("Avg Virality", f"{analytics.get('overview', {}).get('average_virality_score', 0):.4f}"),
        ("Est. Revenue", format_currency(analytics.get('revenue_analysis', {}).get('total_estimated_mid', 0))),
    ]

    for i, (label, value) in enumerate(overview_data, start=5):
        ws[f'A{i}'] = label
        ws[f'B{i}'] = value

    # Videos sheet
    ws_videos = wb.create_sheet("Videos")
    fields = ['video_id', 'title', 'view_count', 'virality_score', 'estimated_revenue_mid']
    for col, field in enumerate(fields, 1):
        cell = ws_videos.cell(row=1, column=col, value=field)
        cell.fill = header_fill
        cell.font = header_font

    for row, v in enumerate(sorted(videos, key=lambda x: x['view_count'], reverse=True), 2):
        for col, field in enumerate(fields, 1):
            ws_videos.cell(row=row, column=col, value=v.get(field, ''))

    wb.save(output_path)
    print(f"Saved Excel: {output_path}")


def generate_cron_setup(channel: str, output_dir: str) -> str:
    """Generate cron job setup instructions."""
    script_path = os.path.abspath(__file__)

    cron_daily = f"0 9 * * * cd {os.path.dirname(script_path)} && python {script_path} {channel} --incremental -o {output_dir}"
    cron_weekly = f"0 9 * * 1 cd {os.path.dirname(script_path)} && python {script_path} {channel} -o {output_dir}"

    instructions = f"""
# ============================================
# CRON SETUP FOR AUTOMATED MONITORING
# ============================================

# Daily incremental check (9 AM):
{cron_daily}

# Weekly full analysis (Monday 9 AM):
{cron_weekly}

# To install, run: crontab -e
# Then paste the desired line above

# For Windows Task Scheduler, create a task with:
# Program: python
# Arguments: {script_path} {channel} --incremental -o {output_dir}
# Schedule: Daily at 9:00 AM
"""
    return instructions


# =============================================================================
# INTERACTIVE CLI
# =============================================================================

def interactive_mode(youtube) -> None:
    """Interactive CLI mode."""
    print("\n" + "=" * 60)
    print("  YouTube Competitive Analysis - Interactive Mode")
    print("=" * 60)

    config = load_config()

    while True:
        print("\n📋 Menu:")
        print("  1. Analyze a channel")
        print("  2. Compare multiple channels")
        print("  3. Check for new videos (watchlist)")
        print("  4. View cron setup instructions")
        print("  5. Exit")

        choice = input("\nSelect option (1-5): ").strip()

        if choice == '1':
            channel = input("Enter channel (@handle, URL, or ID): ").strip()
            if not channel:
                continue

            output_dir = input("Output directory [./output]: ").strip() or './output'
            do_network = input("Analyze video network & discover competitors? (y/N): ").strip().lower() == 'y'

            try:
                result = analyze_channel(youtube, channel, output_dir,
                                        ['csv', 'json', 'excel', 'sqlite', 'html', 'markdown'],
                                        analyze_network=do_network, config=config)
                print("\n✅ Analysis complete!")
            except Exception as e:
                print(f"\n❌ Error: {e}")

        elif choice == '2':
            channels = []
            print("Enter channels (empty line to finish):")
            while True:
                ch = input("  Channel: ").strip()
                if not ch:
                    break
                channels.append(ch)

            if len(channels) < 2:
                print("Need at least 2 channels")
                continue

            output_dir = input("Output directory [./output]: ").strip() or './output'

            # Create temp file
            temp_file = os.path.join(output_dir, '.temp_channels.txt')
            os.makedirs(output_dir, exist_ok=True)
            with open(temp_file, 'w') as f:
                f.write('\n'.join(channels))

            try:
                process_batch(youtube, temp_file, output_dir,
                             ['csv', 'json', 'excel', 'sqlite', 'html', 'markdown'],
                             config=config)
                os.remove(temp_file)
                print("\n✅ Comparison complete!")
            except Exception as e:
                print(f"\n❌ Error: {e}")

        elif choice == '3':
            watchlist = config.get('watchlist', [])
            if not watchlist:
                print("No watchlist configured in config.yaml")
                continue

            output_dir = config.get('output_dir', './output')
            for channel in watchlist:
                try:
                    print(f"\nChecking {channel}...")
                    analyze_channel(youtube, channel, output_dir,
                                   ['sqlite'], incremental=True, config=config)
                except Exception as e:
                    print(f"Error: {e}")

        elif choice == '4':
            channel = input("Channel to monitor: ").strip()
            output_dir = input("Output directory [./output]: ").strip() or './output'
            print(generate_cron_setup(channel, output_dir))

        elif choice == '5':
            print("\nGoodbye! 👋")
            break


# =============================================================================
# MAIN ANALYSIS
# =============================================================================

def analyze_channel(youtube, channel_input: str, output_dir: str, formats: list[str],
                    since: Optional[datetime] = None, until: Optional[datetime] = None,
                    limit: Optional[int] = None, min_views: Optional[int] = None,
                    incremental: bool = False, download_thumbs: bool = False,
                    analyze_network: bool = False, config: dict = None) -> dict:
    """Main analysis function."""
    config = config or {}

    print(f"\n🔍 Analyzing: {channel_input}")

    if channel_input.startswith('http'):
        identifier = extract_channel_id_from_url(channel_input)
        if not identifier:
            raise ValueError(f"Invalid URL: {channel_input}")
    else:
        identifier = channel_input

    channel_id, channel_title = resolve_channel_id(youtube, identifier)
    print(f"📺 Channel: {channel_title}")

    channel_info = get_channel_info(youtube, channel_id)
    print(f"👥 Subscribers: {format_number(channel_info['subscriber_count'])}")

    safe_title = safe_filename(channel_title)

    # Create channel-specific output folder
    channel_output_dir = os.path.join(output_dir, safe_title)
    os.makedirs(channel_output_dir, exist_ok=True)

    # Check existing videos for incremental
    db_path = os.path.join(channel_output_dir, f"{safe_title}.db")
    existing_ids = set()
    if incremental and os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT video_id FROM videos WHERE channel_id = ?', (channel_id,))
            existing_ids = {row[0] for row in cursor.fetchall()}
            conn.close()
            print(f"📁 Found {len(existing_ids)} existing videos")
        except:
            pass

    # Fetch videos
    video_ids = fetch_video_ids_from_playlist(
        youtube, channel_info['uploads_playlist_id'],
        since=since, until=until, limit=limit
    )

    if existing_ids:
        video_ids = [vid for vid in video_ids if vid not in existing_ids]
        print(f"🆕 New videos: {len(video_ids)}")

    if not video_ids:
        print("No new videos")
        return {'channel_info': channel_info, 'videos': [], 'analytics': {}}

    videos = fetch_video_metadata_batch(youtube, video_ids, channel_info, min_views=min_views)

    if not videos:
        print("No videos match criteria")
        return {'channel_info': channel_info, 'videos': [], 'analytics': {}}

    # New video alerts
    if incremental and config.get('webhooks'):
        send_new_video_alert(config, channel_title, videos)

    # Analytics
    print("\n📊 Generating analytics...")
    analytics = generate_analytics(videos, channel_info)
    clusters = cluster_videos_by_topic(videos)

    # Growth rate
    growth = calculate_growth_rate(db_path, channel_id)
    analytics['growth_rate'] = growth

    # Network analysis (competitor discovery)
    neighborhood = None
    if analyze_network:
        neighborhood = analyze_content_neighborhood(youtube, channel_info, videos)
        analytics['neighborhood'] = neighborhood

        # Content gaps from network
        if neighborhood and neighborhood.get('video_network'):
            content_gaps = analyze_content_gaps_from_network(
                videos,
                neighborhood.get('video_network', {})
            )
            analytics['content_gaps'] = content_gaps
            print(f"   📊 Found {content_gaps.get('summary', {}).get('total_gaps_found', 0)} content gaps from network")

    # Thumbnails
    if download_thumbs:
        thumbs_dir = os.path.join(channel_output_dir, 'thumbnails')
        os.makedirs(thumbs_dir, exist_ok=True)
        for v in sorted(videos, key=lambda x: x['view_count'], reverse=True)[:50]:
            if v.get('thumbnail_high'):
                try:
                    urllib.request.urlretrieve(
                        v['thumbnail_high'],
                        os.path.join(thumbs_dir, f"{v['video_id']}.jpg")
                    )
                except:
                    pass
        print(f"📸 Downloaded thumbnails to {thumbs_dir}")

    # Save outputs
    data = {
        'channel': channel_info,
        'analytics': analytics,
        'videos': videos,
        'clusters': clusters,
        'neighborhood': neighborhood,
        'exported_at': datetime.now().isoformat(),
    }

    if 'csv' in formats:
        save_to_csv(videos, os.path.join(channel_output_dir, f"videos.csv"))
    if 'json' in formats:
        save_to_json(data, os.path.join(channel_output_dir, f"analysis.json"))
    if 'excel' in formats:
        save_to_excel(videos, analytics, channel_info, os.path.join(channel_output_dir, f"report.xlsx"))
    if 'sqlite' in formats:
        save_to_sqlite(videos, analytics, channel_info, os.path.join(channel_output_dir, f"data.db"))
    if 'html' in formats:
        save_to_html_dashboard(videos, analytics, channel_info, os.path.join(channel_output_dir, f"dashboard.html"), clusters)
    if 'markdown' in formats:
        save_to_markdown(analytics, channel_info, os.path.join(channel_output_dir, f"report.md"))
    if 'pdf' in formats:
        save_to_pdf(analytics, channel_info, videos, os.path.join(channel_output_dir, f"report.pdf"))
    if 'rss' in formats:
        generate_rss_feed(channel_info, videos, os.path.join(channel_output_dir, f"feed.xml"))

    # Summary
    health = analytics.get('health_score', {})
    print("\n" + "=" * 50)
    print(f"✅ ANALYSIS COMPLETE: {channel_title}")
    print("=" * 50)
    print(f"🏆 Health Score: {health.get('total_score', 0):.0f}/100 ({health.get('grade', 'N/A')})")
    print(f"📈 Viral Videos: {analytics.get('viral_videos', {}).get('count', 0)}")
    print(f"💰 Est. Revenue: {format_currency(analytics.get('revenue_analysis', {}).get('total_estimated_mid', 0))}")

    # Traffic drivers summary
    traffic_drivers = analytics.get('traffic_drivers', {})
    if traffic_drivers.get('top_drivers'):
        print(f"\n🚀 Top Traffic Drivers:")
        for driver in traffic_drivers['top_drivers'][:3]:
            print(f"   • {driver['title'][:45]}... (views: {format_number(driver['views'])}, virality: {driver['virality']:.2f})")

    if neighborhood:
        competitors = neighborhood.get('competitors', {}).get('competitors', [])
        network_stats = neighborhood.get('video_network', {}).get('network_stats', {})
        if competitors:
            print(f"\n🎯 Top Competitors Found: {len(competitors)}")
            for comp in competitors[:5]:
                print(f"   • {comp['title']} (score: {comp['relevance_score']})")
        if network_stats.get('most_connected_channel'):
            print(f"\n🌐 Most Connected Channel: {network_stats['most_connected_channel']}")
            print(f"   Unique channels in network: {network_stats.get('unique_related_channels', 0)}")

        # Content gaps summary
        content_gaps = analytics.get('content_gaps', {})
        if content_gaps.get('summary'):
            summary = content_gaps['summary']
            print(f"\n🔍 Content Gaps from Network:")
            print(f"   Topic gaps found: {summary.get('total_gaps_found', 0)}")
            print(f"   High opportunity: {summary.get('high_opportunity_gaps', 0)}")
            print(f"   Video ideas: {summary.get('video_opportunities', 0)}")

    print(f"\n📁 Output: {channel_output_dir}")

    # Add channel_output_dir to return for other functions to use
    data['output_dir'] = channel_output_dir

    return data


def process_batch(youtube, channels_file: str, output_dir: str, formats: list[str],
                  config: dict = None, **kwargs) -> None:
    """Process multiple channels."""
    with open(channels_file, 'r') as f:
        channels = [l.strip() for l in f if l.strip() and not l.startswith('#')]

    print(f"\n📊 Analyzing {len(channels)} channels...")

    os.makedirs(output_dir, exist_ok=True)
    results = []

    for i, channel in enumerate(channels, 1):
        print(f"\n{'='*50}")
        print(f"Channel {i}/{len(channels)}")
        print('='*50)

        try:
            result = analyze_channel(youtube, channel, output_dir, formats, config=config, **kwargs)
            results.append(result)
        except Exception as e:
            print(f"❌ Error: {e}")

        if i < len(channels):
            time.sleep(1)

    # Comparison report
    if len(results) >= 2:
        print("\n📊 Generating comparison...")

        comparison = []
        for r in results:
            if r.get('analytics'):
                comparison.append({
                    'name': r['channel_info']['title'],
                    'subscribers': r['channel_info'].get('subscriber_count', 0),
                    'videos': r['analytics'].get('overview', {}).get('total_videos_analyzed', 0),
                    'total_views': r['analytics'].get('overview', {}).get('total_views', 0),
                    'avg_virality': r['analytics'].get('overview', {}).get('average_virality_score', 0),
                    'health_score': r['analytics'].get('health_score', {}).get('total_score', 0),
                    'revenue': r['analytics'].get('revenue_analysis', {}).get('total_estimated_mid', 0),
                })

        # Save to comparisons folder
        comparisons_dir = os.path.join(output_dir, 'comparisons')
        os.makedirs(comparisons_dir, exist_ok=True)

        with open(os.path.join(comparisons_dir, 'batch_comparison.json'), 'w') as f:
            json.dump(comparison, f, indent=2)

        # Markdown comparison
        with open(os.path.join(comparisons_dir, 'batch_comparison.md'), 'w') as f:
            f.write("# Channel Comparison\n\n")
            f.write("| Channel | Subscribers | Health | Virality | Est. Revenue |\n")
            f.write("|---------|-------------|--------|----------|-------------|\n")
            for c in sorted(comparison, key=lambda x: x['health_score'], reverse=True):
                f.write(f"| {c['name']} | {format_number(c['subscribers'])} | {c['health_score']:.0f} | {c['avg_virality']:.3f} | {format_currency(c['revenue'])} |\n")

        print(f"📁 Saved comparison to {comparisons_dir}")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='YouTube Competitive Analysis Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('channel', nargs='?', help='Channel to analyze')
    parser.add_argument('--api-key', help='YouTube API key')
    parser.add_argument('--output', '-o', default='./output', help='Output directory')
    parser.add_argument('--format', '-f', nargs='+',
                        choices=['csv', 'json', 'excel', 'sqlite', 'html', 'markdown', 'pdf', 'rss'],
                        default=['csv', 'json', 'excel', 'sqlite', 'html', 'markdown'])
    parser.add_argument('--since', help='Videos after date (YYYY-MM-DD)')
    parser.add_argument('--until', help='Videos before date (YYYY-MM-DD)')
    parser.add_argument('--limit', type=int, help='Max videos')
    parser.add_argument('--min-views', type=int, help='Min view count')
    parser.add_argument('--batch', help='File with channel list')
    parser.add_argument('--incremental', action='store_true', help='Only new videos')
    parser.add_argument('--thumbnails', action='store_true', help='Download thumbnails')
    parser.add_argument('--network', action='store_true', help='Analyze video network & discover competitors')
    parser.add_argument('--vs', metavar='COMPETITOR', help='Analyze traffic capture opportunities vs a competitor')
    parser.add_argument('--interactive', '-i', action='store_true', help='Interactive mode')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--pdf', action='store_true', help='Generate PDF report')
    parser.add_argument('--rss', action='store_true', help='Generate RSS feed')
    parser.add_argument('--api', action='store_true', help='Run as API server')
    parser.add_argument('--port', type=int, default=8080, help='API server port (default: 8080)')
    parser.add_argument('--alerts', action='store_true', help='Check watchlist for trend alerts')
    parser.add_argument('--ideas', action='store_true', help='Generate video ideas')
    parser.add_argument('--calendar', action='store_true', help='Generate content calendar')
    parser.add_argument('--keywords', nargs='+', help='Track keyword rankings')
    parser.add_argument('--watch', action='store_true', help='Continuous monitoring mode')
    parser.add_argument('--interval', type=float, default=6.0, help='Watch mode interval in hours (default: 6)')
    parser.add_argument('--compare', action='store_true', help='Compare this week vs last week')
    parser.add_argument('--tags', action='store_true', help='Optimize tags based on top performers')
    parser.add_argument('--white-label', dest='white_label', metavar='COMPANY', help='Generate white-label report with company name')
    parser.add_argument('--logo', help='Logo URL for white-label reports')
    parser.add_argument('--primary-color', dest='primary_color', default='#667eea', help='Primary color for white-label')
    parser.add_argument('--ai', action='store_true', help='Generate AI-powered recommendations (uses ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY)')
    parser.add_argument('--parallel', action='store_true', help='Process batch channels in parallel')
    parser.add_argument('--workers', type=int, default=3, help='Number of parallel workers (default: 3)')
    parser.add_argument('--resume', action='store_true', help='Resume interrupted analysis')
    parser.add_argument('--clear-progress', dest='clear_progress', action='store_true', help='Clear saved progress')

    args = parser.parse_args()

    api_key = args.api_key or os.environ.get('YOUTUBE_API_KEY')
    if not api_key:
        print("❌ No API key. Set YOUTUBE_API_KEY or use --api-key")
        print("\n🔗 Get free key: https://console.cloud.google.com/apis/credentials")
        sys.exit(1)

    config = load_config(args.config)
    youtube = build('youtube', 'v3', developerKey=api_key)

    # Clear progress mode
    if args.clear_progress:
        clear_progress(args.output)
        print("✅ Cleared saved progress")
        return

    # Watch mode (continuous monitoring)
    if args.watch:
        watchlist = config.get('watchlist', [])
        if not watchlist:
            print("❌ No channels in watchlist. Add to config.yaml")
            sys.exit(1)
        run_watch_mode(youtube, config, interval_hours=args.interval)
        return

    # API Server mode
    if args.api:
        run_api_server(youtube, port=args.port, config=config)
        return

    # Interactive mode
    if args.interactive:
        interactive_mode(youtube)
        return

    # Trend alerts mode
    if args.alerts:
        watchlist = config.get('watchlist', [])
        if not watchlist:
            print("❌ No channels in watchlist. Add to config.yaml")
            sys.exit(1)

        print(f"🔔 Checking {len(watchlist)} channels for alerts...")
        alerts = check_trend_alerts(youtube, watchlist, './output/alerts.db', config)

        if alerts:
            print(f"\n📢 Found {len(alerts)} alerts:\n")
            for alert in alerts:
                print(format_alert_message(alert))

            # Send webhooks if configured
            discord_url = config.get('webhooks', {}).get('discord')
            slack_url = config.get('webhooks', {}).get('slack')

            for alert in alerts:
                msg = format_alert_message(alert)
                if discord_url:
                    send_discord_webhook(discord_url, msg)
                if slack_url:
                    send_slack_webhook(slack_url, msg)
        else:
            print("✅ No new alerts")
        return

    if not args.channel and not args.batch:
        parser.error("Provide channel or --batch or --interactive or --api or --alerts")

    since = datetime.strptime(args.since, '%Y-%m-%d') if args.since else None
    until = datetime.strptime(args.until, '%Y-%m-%d') if args.until else None

    try:
        if args.batch:
            # Read channels from file
            with open(args.batch, 'r') as f:
                channels = [l.strip() for l in f if l.strip() and not l.startswith('#')]

            if args.parallel:
                # Parallel batch processing
                print(f"🚀 Processing {len(channels)} channels in parallel ({args.workers} workers)")
                results = process_batch_parallel(
                    youtube, channels, args.output, args.format,
                    config=config, max_workers=args.workers,
                    since=since, until=until, limit=args.limit,
                    min_views=args.min_views, incremental=args.incremental,
                    download_thumbs=args.thumbnails
                )
                print(f"\n✅ Completed {len(results)} channels")
            else:
                # Sequential batch processing
                process_batch(youtube, args.batch, args.output, args.format,
                             config=config, since=since, until=until,
                             limit=args.limit, min_views=args.min_views,
                             incremental=args.incremental, download_thumbs=args.thumbnails)
        else:
            # Add pdf/rss to formats if requested
            formats = list(args.format)
            if args.pdf and 'pdf' not in formats:
                formats.append('pdf')
            if args.rss and 'rss' not in formats:
                formats.append('rss')

            # Use resume-capable analysis if requested
            if args.resume:
                result = analyze_channel_with_resume(
                    youtube, args.channel, args.output, formats,
                    resume=True, since=since, until=until, limit=args.limit,
                    min_views=args.min_views, incremental=args.incremental,
                    download_thumbs=args.thumbnails, analyze_network=args.network,
                    config=config
                )
            else:
                result = analyze_channel(youtube, args.channel, args.output, formats,
                               since=since, until=until, limit=args.limit,
                               min_views=args.min_views, incremental=args.incremental,
                               download_thumbs=args.thumbnails, analyze_network=args.network,
                               config=config)

            # Time comparison (this week vs last week)
            if args.compare and result.get('videos'):
                print("\n📊 Time Period Comparison:")
                comparison = compare_time_periods(result['videos'], result['channel'])
                print(format_time_comparison(comparison))

            # Tag optimization
            if args.tags and result.get('videos'):
                print("\n🏷️ Tag Optimization Analysis:")
                tag_analysis = optimize_tags(result['videos'])
                print(f"\n  Top recommended tags ({len(tag_analysis['recommended_tags'])}):")
                for tag in tag_analysis['recommended_tags'][:15]:
                    print(f"    • {tag}")
                if tag_analysis.get('high_performing_tags'):
                    print(f"\n  High-performing tags (from viral videos):")
                    for tag in tag_analysis['high_performing_tags'][:10]:
                        stats = tag_analysis.get('tag_stats', {}).get(tag, {})
                        virality = stats.get('avg_virality', 0)
                        print(f"    • {tag} (avg virality: {virality:.2f})")

            # White-label report
            if args.white_label and result.get('videos'):
                branding = {
                    'company_name': args.white_label,
                    'logo_url': args.logo,
                    'primary_color': args.primary_color,
                }
                channel_dir = result.get('output_dir', args.output)
                wl_path = os.path.join(channel_dir, f"whitelabel_report.html")
                generate_white_label_html(result['videos'], result['analytics'],
                                         result['channel'], wl_path, branding)
                print(f"\n🏢 White-label report: {wl_path}")

            # Additional features
            if args.ideas:
                print("\n💡 Generating video ideas...")
                ideas = generate_video_ideas(result['videos'], result['analytics'], result.get('neighborhood'))
                print(f"\n📝 Generated {ideas['total_ideas']} video ideas:\n")
                for category, idea_list in ideas['ideas'].items():
                    if idea_list:
                        print(f"  {category.upper()}:")
                        for idea in idea_list[:3]:
                            print(f"    • {idea['idea']}")
                            if idea.get('suggested_title'):
                                print(f"      Title: \"{idea['suggested_title']}\"")

            if args.calendar:
                print("\n📅 Generating content calendar...")
                calendar = build_content_calendar(result['analytics'])
                print(f"\n  Suggested posting days: {', '.join(calendar['posting_days'])}")
                print(f"  Suggested frequency: {calendar['suggested_frequency']}\n")
                print("  Upcoming schedule:")
                for slot in calendar['calendar'][:8]:
                    print(f"    {slot['date']} ({slot['day']}) at {slot['suggested_time']}")

            if args.keywords:
                print(f"\n🔍 Tracking keywords: {', '.join(args.keywords)}")
                channel_id = result['channel']['channel_id']
                channel_dir = result.get('output_dir', args.output)
                db_path = os.path.join(channel_dir, f"data.db")
                rankings = track_keyword_rankings(youtube, args.keywords, channel_id, db_path)
                print(f"\n  In top 10: {rankings['in_top_10']}/{len(args.keywords)}")
                print(f"  In top 50: {rankings['in_top_50']}/{len(args.keywords)}")
                for kw, data in rankings['rankings'].items():
                    pos = data.get('position', 'Not found')
                    print(f"    '{kw}': Position {pos}")

            # Competitor traffic capture analysis
            if args.vs and result.get('videos'):
                print(f"\n🎯 Analyzing traffic opportunities vs {args.vs}...")

                # Analyze competitor channel
                comp_result = analyze_channel(youtube, args.vs, args.output, ['json'],
                                             since=since, until=until, limit=args.limit,
                                             min_views=args.min_views, config=config)

                if comp_result.get('videos'):
                    traffic_analysis = analyze_competitor_traffic_opportunities(
                        result['videos'],
                        result['channel'],
                        comp_result['videos'],
                        comp_result['channel']
                    )

                    # Print analysis
                    print(format_traffic_analysis(traffic_analysis))

                    # Save to comparisons folder
                    safe_your = safe_filename(result['channel']['title'])
                    safe_comp = safe_filename(comp_result['channel']['title'])

                    comparisons_dir = os.path.join(args.output, 'comparisons')
                    os.makedirs(comparisons_dir, exist_ok=True)

                    # JSON
                    analysis_path = os.path.join(comparisons_dir, f"{safe_your}_vs_{safe_comp}.json")
                    with open(analysis_path, 'w', encoding='utf-8') as f:
                        json.dump(traffic_analysis, f, indent=2, ensure_ascii=False)
                    print(f"\n📁 JSON saved: {analysis_path}")

                    # HTML
                    html_path = os.path.join(comparisons_dir, f"{safe_your}_vs_{safe_comp}.html")
                    generate_traffic_analysis_html(traffic_analysis, html_path)

                    # AI-powered recommendations for comparison
                    if args.ai:
                        ai_result = get_ai_recommendations(
                            your_channel=result['channel'],
                            your_analytics=result['analytics'],
                            your_videos=result['videos'],
                            competitor_channel=comp_result['channel'],
                            competitor_analytics=comp_result['analytics'],
                            traffic_analysis=traffic_analysis,
                            output_dir=comparisons_dir,
                        )

                        if ai_result.get('recommendations'):
                            print("\n" + "=" * 60)
                            print("🤖 AI-POWERED RECOMMENDATIONS")
                            print("=" * 60)
                            print(ai_result['recommendations'])

                            # Save to markdown file
                            ai_path = os.path.join(comparisons_dir, f"{safe_your}_vs_{safe_comp}_ai_recommendations.md")
                            save_ai_recommendations(ai_result, ai_path)
                else:
                    print(f"❌ Could not analyze competitor: {args.vs}")

            # AI analysis for single channel (without --vs)
            elif args.ai and result.get('videos'):
                channel_dir = result.get('output_dir', args.output)
                ai_result = get_ai_recommendations(
                    your_channel=result['channel'],
                    your_analytics=result['analytics'],
                    your_videos=result['videos'],
                    output_dir=channel_dir,
                )

                if ai_result.get('recommendations'):
                    print("\n" + "=" * 60)
                    print("🤖 AI-POWERED RECOMMENDATIONS")
                    print("=" * 60)
                    print(ai_result['recommendations'])

                    # Save to markdown file
                    safe_name = safe_filename(result['channel']['title'])
                    ai_path = os.path.join(channel_dir, f"ai_recommendations.md")
                    save_ai_recommendations(ai_result, ai_path)

    except HttpError as e:
        print(f"\n❌ API Error: {e.resp.status}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
