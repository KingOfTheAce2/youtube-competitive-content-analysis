"""Competitor discovery, topic extraction, opportunity scoring, recommendations, gap analysis."""

from .common import *
from .discovery import discover_competitor_channels
from .fetch import fetch_video_ids_from_playlist, fetch_video_metadata_batch, get_channel_info, resolve_channel_id
from .store import get_competitive_db_path, get_my_channel_id, list_competitors, migrate_competitive_database, save_competitor_to_db

# =============================================================================
# COMPETITOR DISCOVERY (ENHANCED)
# =============================================================================

def discover_and_save_competitors(youtube, config: dict, output_dir: str,
                                   max_competitors: int = None) -> dict:
    """
    Discover competitors from seed channels and save to database.
    """
    db_path = get_competitive_db_path(output_dir)
    migrate_competitive_database(db_path)

    my_channel_id, my_channel_title = get_my_channel_id(youtube, config, db_path)
    if not my_channel_id:
        return {'error': 'my_channel not set in config. Use --set-my-channel first.'}

    discovery_config = config.get('discovery', {})
    max_comp = max_competitors or discovery_config.get('max_competitors', 25)
    min_relevance = discovery_config.get('min_relevance_score', 0.3)

    print(f"\n🔍 Discovering competitors for {my_channel_title}...")

    # Get my channel's videos for analysis
    my_channel_info = get_channel_info(youtube, my_channel_id)
    video_ids = fetch_video_ids_from_playlist(
        youtube, my_channel_info['uploads_playlist_id'],
        limit=100
    )
    my_videos = fetch_video_metadata_batch(youtube, video_ids[:50], my_channel_info)

    # Use existing discover function
    discovered = discover_competitor_channels(youtube, my_channel_info, my_videos, max_channels=max_comp)

    # Also discover from seed competitors
    seed_competitors = config.get('seed_competitors') or []
    for seed in seed_competitors:
        try:
            seed_id, seed_title = resolve_channel_id(youtube, seed)
            seed_info = get_channel_info(youtube, seed_id)
            seed_video_ids = fetch_video_ids_from_playlist(
                youtube, seed_info['uploads_playlist_id'],
                limit=50
            )
            seed_videos = fetch_video_metadata_batch(youtube, seed_video_ids[:30], seed_info)

            seed_discovered = discover_competitor_channels(youtube, seed_info, seed_videos, max_channels=10)

            # Merge discoveries
            for comp in seed_discovered.get('competitors', []):
                if comp['channel_id'] != my_channel_id:
                    # Check if already in list
                    existing = next((c for c in discovered['competitors']
                                   if c['channel_id'] == comp['channel_id']), None)
                    if existing:
                        existing['relevance_score'] += comp['relevance_score'] * 0.5
                    else:
                        comp['relevance_score'] *= 0.5  # Lower weight for indirect discovery
                        discovered['competitors'].append(comp)
        except Exception as e:
            print(f"   Warning: Could not analyze seed competitor {seed}: {e}")

    # Normalize relevance scores to 0-1 range
    if discovered['competitors']:
        max_score = max(c['relevance_score'] for c in discovered['competitors'])
        for comp in discovered['competitors']:
            comp['relevance_score'] = round(comp['relevance_score'] / max_score, 3) if max_score > 0 else 0

    # Filter by minimum relevance and save to database
    saved = []
    for comp in discovered['competitors']:
        if comp['relevance_score'] >= min_relevance:
            result = save_competitor_to_db(
                youtube, comp['channel_id'], my_channel_id,
                comp['relevance_score'],
                'auto_discovery',
                db_path
            )
            if 'error' not in result:
                saved.append({
                    'channel_id': comp['channel_id'],
                    'title': comp.get('title', result.get('title', 'Unknown')),
                    'relevance_score': comp['relevance_score'],
                })

    return {
        'my_channel': my_channel_title,
        'total_discovered': len(discovered['competitors']),
        'saved': len(saved),
        'competitors': saved,
        'search_keywords': discovered.get('search_keywords', []),
    }


# =============================================================================
# TOPIC EXTRACTION & RECOMMENDATIONS
# =============================================================================

def extract_topics_from_videos(videos: list[dict]) -> dict:
    """
    Extract topics from video titles and tags using n-gram analysis.
    Returns weighted topics based on video performance.
    """
    topic_scores = defaultdict(lambda: {
        'count': 0,
        'total_views': 0,
        'total_virality': 0,
        'videos': [],
    })

    # Common stop words to exclude
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'is', 'it', 'this', 'that', 'was', 'are',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall',
        'i', 'you', 'he', 'she', 'we', 'they', 'my', 'your', 'his', 'her',
        'its', 'our', 'their', 'what', 'which', 'who', 'when', 'where', 'why',
        'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
        'some', 'such', 'no', 'not', 'only', 'own', 'same', 'so', 'than',
        'too', 'very', 'just', 'can', 'now', 'new', 'one', 'two', 'first',
        'about', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'between', 'under', 'again', 'further', 'then', 'once',
        'here', 'there', 'out', 'up', 'down', 'off', 'over', 'any', 'get',
        'got', 'make', 'made', 'like', 'use', 'using', 'used', 'video',
        'videos', 'part', 'episode', 'ep', 'full', 'official', 'watch',
    }

    for v in videos:
        title = v.get('title', '')
        tags = v.get('tags', [])
        views = v.get('view_count', 0)
        virality = v.get('virality_score', 0)

        # Clean title - remove special chars, split into words
        title_clean = re.sub(r'[^\w\s]', ' ', title.lower())
        words = [w for w in title_clean.split() if len(w) > 2 and w not in stop_words]

        # Extract 1-grams, 2-grams, and 3-grams
        for n in [1, 2, 3]:
            for i in range(len(words) - n + 1):
                topic = ' '.join(words[i:i+n])
                if len(topic) > 3:  # Minimum topic length
                    topic_scores[topic]['count'] += 1
                    topic_scores[topic]['total_views'] += views
                    topic_scores[topic]['total_virality'] += virality
                    topic_scores[topic]['videos'].append({
                        'video_id': v['video_id'],
                        'title': v['title'],
                        'views': views,
                        'virality': virality,
                    })

        # Tags are high-signal topics
        for tag in tags:
            tag_clean = tag.lower().strip()
            if len(tag_clean) > 2 and tag_clean not in stop_words:
                topic_scores[tag_clean]['count'] += 2  # Higher weight for tags
                topic_scores[tag_clean]['total_views'] += views * 1.5
                topic_scores[tag_clean]['total_virality'] += virality * 1.5
                topic_scores[tag_clean]['videos'].append({
                    'video_id': v['video_id'],
                    'title': v['title'],
                    'views': views,
                    'virality': virality,
                    'from_tag': True,
                })

    # Calculate scores and filter
    topics = []
    for topic, data in topic_scores.items():
        if data['count'] >= 2:  # Minimum 2 occurrences
            avg_views = data['total_views'] / data['count']
            avg_virality = data['total_virality'] / data['count']

            topics.append({
                'topic': topic,
                'count': data['count'],
                'avg_views': int(avg_views),
                'avg_virality': round(avg_virality, 4),
                'total_views': data['total_views'],
                'video_count': len(set(v['video_id'] for v in data['videos'])),
            })

    # Sort by a combination of frequency and performance
    topics.sort(key=lambda x: x['count'] * (1 + x['avg_virality']) * math.log10(max(x['avg_views'], 1)), reverse=True)

    return {
        'topics': topics[:100],  # Top 100 topics
        'total_extracted': len(topics),
    }


def calculate_opportunity_score(topic: str, my_topics: dict, competitor_topics: dict,
                                 my_videos: list, competitor_videos: list) -> dict:
    """
    Calculate opportunity score for a topic.

    Opportunity = (Gap × 0.35) + (Performance × 0.40) + (Alignment × 0.25)

    Gap: How much competitors cover this vs you (100 = pure gap)
    Performance: How well this topic performs for competitors
    Alignment: How similar to your best-performing topics
    """
    my_topic_data = my_topics.get(topic, {'count': 0, 'avg_views': 0, 'avg_virality': 0})
    comp_topic_data = competitor_topics.get(topic, {'count': 0, 'avg_views': 0, 'avg_virality': 0})

    # GAP SCORE (0-100)
    # Higher if competitors cover it but you don't
    my_coverage = my_topic_data.get('count', 0)
    comp_coverage = comp_topic_data.get('count', 0)

    if comp_coverage > 0 and my_coverage == 0:
        gap_score = 100  # Pure gap - competitors have it, you don't
    elif comp_coverage > my_coverage:
        gap_score = min(100, ((comp_coverage - my_coverage) / max(comp_coverage, 1)) * 100)
    else:
        gap_score = 0  # You cover it as much or more

    # PERFORMANCE SCORE (0-100)
    # Based on how well this topic performs for competitors
    comp_avg_views = comp_topic_data.get('avg_views', 0)
    comp_avg_virality = comp_topic_data.get('avg_virality', 0)

    # Calculate overall avg performance across all competitor videos
    if competitor_videos:
        overall_avg_views = sum(v['view_count'] for v in competitor_videos) / len(competitor_videos)
        overall_avg_virality = sum(v.get('virality_score', 0) for v in competitor_videos) / len(competitor_videos)
    else:
        overall_avg_views = 1
        overall_avg_virality = 0.1

    # Performance relative to average
    view_performance = min(100, (comp_avg_views / max(overall_avg_views, 1)) * 50)
    virality_performance = min(100, (comp_avg_virality / max(overall_avg_virality, 0.01)) * 50)
    performance_score = (view_performance + virality_performance) / 2

    # ALIGNMENT SCORE (0-100)
    # How similar to your top-performing topics
    # Find topics from your best videos
    if my_videos:
        top_my_videos = sorted(my_videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:10]
        my_top_topics = set()
        for v in top_my_videos:
            title_words = re.findall(r'\b\w+\b', v['title'].lower())
            my_top_topics.update(title_words)
            my_top_topics.update([t.lower() for t in v.get('tags', [])])

        topic_words = set(topic.lower().split())
        overlap = len(topic_words & my_top_topics)
        alignment_score = min(100, overlap * 33)  # Max 100 with 3 word overlap
    else:
        alignment_score = 50  # Neutral if no data

    # COMBINED OPPORTUNITY SCORE
    opportunity_score = (gap_score * 0.35) + (performance_score * 0.40) + (alignment_score * 0.25)

    # Determine recommendation type
    if gap_score > 70:
        rec_type = 'GAP'
    elif alignment_score > 60:
        rec_type = 'ALIGN'
    elif performance_score > 70:
        rec_type = 'TRENDING'
    else:
        rec_type = 'MIXED'

    return {
        'topic': topic,
        'opportunity_score': round(opportunity_score, 1),
        'gap_score': round(gap_score, 1),
        'performance_score': round(performance_score, 1),
        'alignment_score': round(alignment_score, 1),
        'recommendation_type': rec_type,
        'my_coverage': my_coverage,
        'competitor_coverage': comp_coverage,
        'competitor_avg_views': int(comp_avg_views),
        'competitor_avg_virality': round(comp_avg_virality, 4),
    }


def generate_recommendations(youtube, config: dict, output_dir: str, top_n: int = 20) -> dict:
    """
    Generate ranked topic recommendations based on competitive analysis.
    """
    db_path = get_competitive_db_path(output_dir)
    migrate_competitive_database(db_path)

    my_channel_id, my_channel_title = get_my_channel_id(youtube, config, db_path)
    if not my_channel_id:
        return {'error': 'my_channel not set in config. Use --set-my-channel first.'}

    print(f"\n📊 Generating recommendations for {my_channel_title}...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get my videos from database
    cursor.execute('''
        SELECT video_id, title, view_count, like_count, virality_score, publish_date
        FROM videos WHERE channel_id = ?
        ORDER BY publish_date DESC LIMIT 200
    ''', (my_channel_id,))
    my_video_rows = cursor.fetchall()
    my_videos = [{
        'video_id': r[0], 'title': r[1], 'view_count': r[2],
        'like_count': r[3], 'virality_score': r[4], 'publish_date': r[5],
        'tags': [],  # Tags not stored in DB, extract from title
    } for r in my_video_rows]

    # Get competitor channel IDs
    competitors = list_competitors(db_path, my_channel_id)
    if not competitors:
        conn.close()
        return {'error': 'No competitors found. Use --discover-competitors first.'}

    competitor_ids = [c['channel_id'] for c in competitors]

    # Get competitor videos
    placeholders = ','.join('?' * len(competitor_ids))
    cursor.execute(f'''
        SELECT video_id, title, view_count, like_count, virality_score, publish_date, channel_id
        FROM videos WHERE channel_id IN ({placeholders})
        ORDER BY publish_date DESC
    ''', competitor_ids)
    comp_video_rows = cursor.fetchall()
    competitor_videos = [{
        'video_id': r[0], 'title': r[1], 'view_count': r[2],
        'like_count': r[3], 'virality_score': r[4], 'publish_date': r[5],
        'channel_id': r[6], 'tags': [],
    } for r in comp_video_rows]

    conn.close()

    if not competitor_videos:
        return {'error': 'No competitor videos in database. Run --sync first.'}

    print(f"   Analyzing {len(my_videos)} of your videos vs {len(competitor_videos)} competitor videos...")

    # Extract topics
    my_topics_data = extract_topics_from_videos(my_videos)
    comp_topics_data = extract_topics_from_videos(competitor_videos)

    # Build topic lookup dicts
    my_topics = {t['topic']: t for t in my_topics_data['topics']}
    comp_topics = {t['topic']: t for t in comp_topics_data['topics']}

    # Get all unique topics from competitors
    all_topics = set(comp_topics.keys())

    # Calculate opportunity scores
    recommendations = []
    for topic in all_topics:
        if len(topic) > 3:  # Filter very short topics
            score = calculate_opportunity_score(
                topic, my_topics, comp_topics, my_videos, competitor_videos
            )
            if score['opportunity_score'] > 30:  # Minimum threshold
                recommendations.append(score)

    # Sort by opportunity score
    recommendations.sort(key=lambda x: x['opportunity_score'], reverse=True)

    # Save to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for rec in recommendations[:50]:  # Save top 50
        cursor.execute('''
            INSERT OR REPLACE INTO topic_recommendations
            (my_channel_id, topic_name, opportunity_score, gap_score, performance_score,
             alignment_score, competitor_coverage, my_coverage, avg_competitor_views,
             avg_competitor_virality, recommendation_type, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            my_channel_id, rec['topic'], rec['opportunity_score'], rec['gap_score'],
            rec['performance_score'], rec['alignment_score'], rec['competitor_coverage'],
            rec['my_coverage'], rec['competitor_avg_views'], rec['competitor_avg_virality'],
            rec['recommendation_type'], datetime.now().isoformat()
        ))

    conn.commit()
    conn.close()

    return {
        'my_channel': my_channel_title,
        'my_videos_analyzed': len(my_videos),
        'competitor_videos_analyzed': len(competitor_videos),
        'competitors_count': len(competitors),
        'recommendations': recommendations[:top_n],
        'total_opportunities': len(recommendations),
    }


def format_recommendations_table(recommendations: dict) -> str:
    """Format recommendations as a nice table for CLI output."""
    if 'error' in recommendations:
        return f"❌ {recommendations['error']}"

    recs = recommendations.get('recommendations', [])
    if not recs:
        return "No recommendations found."

    lines = []
    lines.append("")
    lines.append("┌" + "─" * 73 + "┐")
    lines.append(f"│  TOP VIDEO OPPORTUNITIES FOR {recommendations['my_channel'][:40]:<40} │")
    lines.append("├─────┬" + "─" * 32 + "┬───────┬────────┬─────────────┤")
    lines.append("│  #  │ Topic                          │ Score │ Type   │ Why?        │")
    lines.append("├─────┼" + "─" * 32 + "┼───────┼────────┼─────────────┤")

    for i, rec in enumerate(recs, 1):
        topic = rec['topic'][:30]
        score = f"{rec['opportunity_score']:.1f}"
        rec_type = rec['recommendation_type']

        # Build "why" string
        if rec_type == 'GAP':
            why = f"{rec['competitor_coverage']} competitors"
        elif rec_type == 'ALIGN':
            why = f"Your style"
        elif rec_type == 'TRENDING':
            why = f"{rec['competitor_avg_views']:,} avg views"[:12]
        else:
            why = f"Score {score}"

        lines.append(f"│ {i:>3} │ {topic:<30} │ {score:>5} │ {rec_type:<6} │ {why:<11} │")

        # Add detail line for top 5
        if i <= 5:
            detail = f"avg {rec['competitor_avg_views']:,} views" if rec['competitor_avg_views'] else ""
            lines.append(f"│     │ {'':<30} │       │        │ {detail:<11} │")

    lines.append("└─────┴" + "─" * 32 + "┴───────┴────────┴─────────────┘")
    lines.append("")
    lines.append(f"📊 Analyzed {recommendations['my_videos_analyzed']} of your videos vs {recommendations['competitor_videos_analyzed']} competitor videos")
    lines.append(f"🎯 {recommendations['total_opportunities']} total opportunities found")

    return '\n'.join(lines)


def generate_gap_analysis(youtube, config: dict, output_dir: str) -> dict:
    """
    Generate a comprehensive gap analysis report.
    """
    db_path = get_competitive_db_path(output_dir)
    migrate_competitive_database(db_path)

    my_channel_id, my_channel_title = get_my_channel_id(youtube, config, db_path)
    if not my_channel_id:
        return {'error': 'my_channel not set in config. Use --set-my-channel first.'}

    print(f"\n📊 Generating gap analysis for {my_channel_title}...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get my videos
    cursor.execute('''
        SELECT video_id, title, view_count, virality_score FROM videos
        WHERE channel_id = ? ORDER BY view_count DESC
    ''', (my_channel_id,))
    my_videos = [{'video_id': r[0], 'title': r[1], 'view_count': r[2],
                  'virality_score': r[3], 'tags': []} for r in cursor.fetchall()]

    # Get competitors
    competitors = list_competitors(db_path, my_channel_id)
    competitor_ids = [c['channel_id'] for c in competitors]

    if not competitor_ids:
        conn.close()
        return {'error': 'No competitors found. Use --discover-competitors first.'}

    # Get competitor videos
    placeholders = ','.join('?' * len(competitor_ids))
    cursor.execute(f'''
        SELECT video_id, title, view_count, virality_score, channel_id FROM videos
        WHERE channel_id IN ({placeholders}) ORDER BY view_count DESC
    ''', competitor_ids)
    comp_videos = [{'video_id': r[0], 'title': r[1], 'view_count': r[2],
                    'virality_score': r[3], 'channel_id': r[4], 'tags': []}
                   for r in cursor.fetchall()]

    conn.close()

    # Extract topics
    my_topics_data = extract_topics_from_videos(my_videos)
    comp_topics_data = extract_topics_from_videos(comp_videos)

    my_topics = {t['topic']: t for t in my_topics_data['topics']}
    comp_topics = {t['topic']: t for t in comp_topics_data['topics']}

    # GAPS: Topics competitors have that you don't
    gaps = []
    for topic, data in comp_topics.items():
        if topic not in my_topics and data['count'] >= 3:
            gaps.append({
                'topic': topic,
                'competitor_count': data['video_count'],
                'avg_views': data['avg_views'],
                'avg_virality': data['avg_virality'],
            })
    gaps.sort(key=lambda x: x['avg_views'], reverse=True)

    # STRENGTHS: Topics you have that competitors don't or you do better
    strengths = []
    for topic, data in my_topics.items():
        comp_data = comp_topics.get(topic, {'avg_views': 0, 'count': 0})
        if data['count'] >= 2:
            if topic not in comp_topics:
                strengths.append({
                    'topic': topic,
                    'your_videos': data['video_count'],
                    'your_avg_views': data['avg_views'],
                    'unique': True,
                    'vs_competitor': 'N/A',
                })
            elif data['avg_views'] > comp_data['avg_views'] * 1.2:
                pct_better = ((data['avg_views'] - comp_data['avg_views']) / max(comp_data['avg_views'], 1)) * 100
                strengths.append({
                    'topic': topic,
                    'your_videos': data['video_count'],
                    'your_avg_views': data['avg_views'],
                    'unique': False,
                    'vs_competitor': f"+{pct_better:.0f}%",
                })
    strengths.sort(key=lambda x: x['your_avg_views'], reverse=True)

    # BENCHMARKS: Topics you both cover
    benchmarks = []
    for topic, data in my_topics.items():
        if topic in comp_topics and data['count'] >= 2 and comp_topics[topic]['count'] >= 2:
            comp_data = comp_topics[topic]
            diff = data['avg_views'] - comp_data['avg_views']
            pct_diff = (diff / max(comp_data['avg_views'], 1)) * 100

            benchmarks.append({
                'topic': topic,
                'your_avg': data['avg_views'],
                'competitor_avg': comp_data['avg_views'],
                'gap': diff,
                'gap_pct': round(pct_diff, 1),
                'status': 'winning' if pct_diff > 10 else 'losing' if pct_diff < -10 else 'even',
            })
    benchmarks.sort(key=lambda x: abs(x['gap']), reverse=True)

    return {
        'my_channel': my_channel_title,
        'competitor_count': len(competitors),
        'my_videos': len(my_videos),
        'competitor_videos': len(comp_videos),
        'gaps': gaps[:20],
        'strengths': strengths[:15],
        'benchmarks': benchmarks[:15],
    }


def format_gap_analysis(analysis: dict) -> str:
    """Format gap analysis as markdown report."""
    if 'error' in analysis:
        return f"❌ {analysis['error']}"

    lines = []
    lines.append(f"\n# Gap Analysis: {analysis['my_channel']} vs {analysis['competitor_count']} Competitors\n")

    # Gaps section
    lines.append("## Topics Competitors Cover That You Don't\n")
    if analysis['gaps']:
        lines.append("| Topic | # Competitors | Avg Views | Avg Virality |")
        lines.append("|-------|--------------|-----------|--------------|")
        for gap in analysis['gaps'][:10]:
            lines.append(f"| {gap['topic'][:25]} | {gap['competitor_count']} | {gap['avg_views']:,} | {gap['avg_virality']:.2f} |")
    else:
        lines.append("*No significant gaps found - great coverage!*")

    # Strengths section
    lines.append("\n## Your Unique Strengths (Topics You Own)\n")
    if analysis['strengths']:
        lines.append("| Topic | Your Videos | Avg Views | vs Competitor Avg |")
        lines.append("|-------|-------------|-----------|-------------------|")
        for strength in analysis['strengths'][:10]:
            vs = strength['vs_competitor'] if not strength['unique'] else "Unique to you"
            lines.append(f"| {strength['topic'][:25]} | {strength['your_videos']} | {strength['your_avg_views']:,} | {vs} |")
    else:
        lines.append("*Analyze more videos to identify strengths*")

    # Benchmarks section
    lines.append("\n## Topics You Both Cover (Benchmark)\n")
    if analysis['benchmarks']:
        lines.append("| Topic | Your Avg | Competitor Avg | Gap |")
        lines.append("|-------|----------|----------------|-----|")
        for bench in analysis['benchmarks'][:10]:
            status = f"({bench['status']})"
            lines.append(f"| {bench['topic'][:25]} | {bench['your_avg']:,} | {bench['competitor_avg']:,} | {bench['gap_pct']:+.0f}% {status} |")
    else:
        lines.append("*No common topics found for benchmarking*")

    lines.append(f"\n---\n*Based on {analysis['my_videos']} of your videos vs {analysis['competitor_videos']} competitor videos*")

    return '\n'.join(lines)

