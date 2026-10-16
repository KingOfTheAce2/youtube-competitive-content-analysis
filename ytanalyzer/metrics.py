"""Per-video and per-channel metrics: titles, series, virality, health, seasonality, growth, lifecycle, momentum."""

from .common import *

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

