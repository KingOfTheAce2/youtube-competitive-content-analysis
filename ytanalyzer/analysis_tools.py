"""Period comparison, tag optimisation, white-label report, parallel batch."""

from .common import *
from .analyze import analyze_channel

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

