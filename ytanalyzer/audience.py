"""Collaboration ROI and audience overlap."""

from .common import *

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

