"""Shared imports, optional-dependency flags, constants and small helpers."""

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
import ssl
import sys
import time
import urllib.request
import urllib.parse
import http.server
import socketserver
import threading

# Bypass SSL verification for corporate/local cert issues
ssl._create_default_https_context = ssl._create_unverified_context
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
    """Load configuration from YAML file, merging with private my_channels.yaml."""
    if not YAML_AVAILABLE:
        return {}

    config = {}

    # Load main config
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
        except:
            pass

    # Load private config (my_channels.yaml) and merge - this overrides public config
    # This file is gitignored and contains personal channel/competitor data
    private_config_path = os.path.join(os.path.dirname(config_path) or '.', 'my_channels.yaml')
    if os.path.exists(private_config_path):
        try:
            with open(private_config_path, 'r', encoding='utf-8') as f:
                private_config = yaml.safe_load(f) or {}
                # Merge private into main (private takes precedence)
                for key, value in private_config.items():
                    if value is not None:
                        config[key] = value
        except:
            pass

    return config
