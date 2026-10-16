"""analyze_channel and process_batch: the full per-channel pipeline."""

from .common import *
from .analytics import cluster_videos_by_topic, generate_analytics
from .discovery import analyze_content_neighborhood
from .excel import save_to_excel
from .exports import save_to_csv, save_to_html_dashboard, save_to_json, save_to_markdown, save_to_sqlite
from .exports_extra import generate_rss_feed, save_to_pdf
from .fetch import extract_channel_id_from_url, fetch_video_ids_from_playlist, fetch_video_metadata_batch, get_channel_info, resolve_channel_id
from .metrics import calculate_growth_rate
from .notify import send_new_video_alert
from .traffic import analyze_content_gaps_from_network

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

