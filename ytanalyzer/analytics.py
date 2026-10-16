"""generate_analytics and topic clustering."""

from .common import *
from .metrics import analyze_seasonality, calculate_channel_health_score, calculate_upload_consistency
from .traffic import analyze_traffic_drivers

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

