"""Competitor traffic capture and traffic driver analysis (data and HTML)."""

from .common import *

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

