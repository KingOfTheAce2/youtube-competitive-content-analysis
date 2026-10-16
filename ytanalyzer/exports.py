"""CSV, JSON, Markdown, HTML dashboard and SQLite output."""

from .common import *
from .traffic import generate_traffic_drivers_html

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

