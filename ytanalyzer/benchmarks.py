"""Niche benchmarks and custom scoring."""

from .common import *

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

