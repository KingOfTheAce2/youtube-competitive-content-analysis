"""Recommendations with titles and their HTML."""

from .common import *
from .recommend import generate_recommendations
from .store import get_competitive_db_path, get_my_channel_id, list_competitors

def generate_title_suggestions(topic: str, competitor_videos: list, num_suggestions: int = 5) -> list:
    """
    Generate context-aware video title suggestions based on topic type.
    """
    topic_lower = topic.lower()
    topic_title = topic.title()

    # Detect topic type for context-appropriate templates
    countries = {
        'russia', 'spain', 'georgia', 'portugal', 'dubai', 'uae', 'malaysia',
        'thailand', 'singapore', 'australia', 'canada', 'uk', 'usa', 'germany',
        'france', 'italy', 'netherlands', 'ireland', 'cyprus', 'malta', 'greece',
        'panama', 'costa rica', 'mexico', 'colombia', 'brazil', 'argentina',
        'japan', 'korea', 'vietnam', 'indonesia', 'philippines', 'india'
    }

    visa_terms = {'visa', 'golden visa', 'residency', 'citizenship', 'passport', 'permit'}
    tax_terms = {'tax', 'taxes', 'taxation', 'deduction', 'write-off', 'cfc', 'tax-free'}
    finance_terms = {'invest', 'investment', 'banking', 'account', 'money', 'wealth', 'retire'}
    expat_terms = {'expat', 'move', 'moving', 'relocate', 'living', 'life abroad', 'digital nomad'}

    # Check what type of topic this is
    is_country = any(c in topic_lower for c in countries)
    is_visa = any(v in topic_lower for v in visa_terms)
    is_tax = any(t in topic_lower for t in tax_terms)
    is_finance = any(f in topic_lower for f in finance_terms)
    is_expat = any(e in topic_lower for e in expat_terms)

    templates = []

    # Country-specific templates
    if is_country:
        templates = [
            f"Moving to {topic_title}: Complete Guide for Expats (2025)",
            f"{topic_title} for Digital Nomads: Cost of Living, Visas & Taxes",
            f"Why {topic_title} is the Best Country for Tax Optimization",
            f"Living in {topic_title}: What Nobody Tells You Before Moving",
            f"{topic_title} Residency: How to Get It & What It Costs",
            f"I Moved to {topic_title} - Here's My Honest Review After 1 Year",
            f"{topic_title} vs Portugal: Which is Better for Expats?",
            f"The REAL Cost of Living in {topic_title} (2025 Breakdown)",
            f"5 Mistakes to Avoid When Moving to {topic_title}",
            f"{topic_title} Tax System Explained: What Expats Need to Know",
        ]
    # Visa-specific templates
    elif is_visa:
        templates = [
            f"{topic_title} Explained: Requirements, Costs & Timeline",
            f"How to Get a {topic_title} (Step-by-Step Guide)",
            f"{topic_title}: Is It Still Worth It in 2025?",
            f"The TRUTH About {topic_title} Nobody Tells You",
            f"{topic_title} vs Other Options: Which Should You Choose?",
            f"I Got My {topic_title} - Here's How (And What It Cost)",
            f"5 Countries with the Best {topic_title} Programs",
            f"{topic_title} Application: Common Mistakes to Avoid",
        ]
    # Tax-specific templates
    elif is_tax:
        templates = [
            f"{topic_title}: Complete Guide for Expats & Digital Nomads",
            f"How to Legally Minimize Your {topic_title}",
            f"{topic_title} Explained: What You Need to Know",
            f"The TRUTH About {topic_title} (Most People Get This Wrong)",
            f"5 Legal Ways to Reduce Your {topic_title}",
            f"{topic_title} Planning: Strategies That Actually Work",
            f"Avoid These {topic_title} Mistakes (They're Costly)",
            f"{topic_title} for Remote Workers: The Complete Guide",
        ]
    # Finance-specific templates
    elif is_finance:
        templates = [
            f"{topic_title} for Expats: Complete Guide (2025)",
            f"How to {topic_title} as a Digital Nomad",
            f"{topic_title}: What Nobody Tells You",
            f"5 {topic_title} Strategies for Location-Independent People",
            f"The TRUTH About {topic_title} Abroad",
            f"{topic_title}: Biggest Mistakes to Avoid",
        ]
    # Expat lifestyle templates
    elif is_expat:
        templates = [
            f"{topic_title}: Everything You Need to Know",
            f"How to Start {topic_title} (Complete Beginner's Guide)",
            f"{topic_title}: My Honest Experience After 2 Years",
            f"The REAL Cost of {topic_title}",
            f"5 Things I Wish I Knew Before {topic_title}",
            f"{topic_title}: Pros, Cons & What to Expect",
        ]
    # Generic but improved templates
    else:
        templates = [
            f"{topic_title}: Complete Guide for Expats (2025)",
            f"How {topic_title} Works (Simple Explanation)",
            f"{topic_title} Explained: What You Need to Know",
            f"The TRUTH About {topic_title} Nobody Tells You",
            f"5 Things to Know About {topic_title}",
            f"{topic_title}: Common Mistakes to Avoid",
        ]

    # Find relevant competitor videos to learn from their patterns
    topic_words = set(topic_lower.split())
    relevant_videos = []
    for v in competitor_videos:
        title_lower = v.get('title', '').lower()
        if any(word in title_lower for word in topic_words if len(word) > 3):
            relevant_videos.append(v)

    relevant_videos.sort(key=lambda x: x.get('virality_score', 0), reverse=True)

    # Add patterns from top-performing competitor videos
    if relevant_videos:
        for vid in relevant_videos[:3]:
            title = vid.get('title', '')
            # Learn from high-performing competitor titles
            if vid.get('view_count', 0) > 50000:
                # Extract the pattern and create a variant
                if ':' in title:
                    templates.insert(0, f"{topic_title}: Why It Matters for Your Tax Strategy")
                if '?' in title:
                    templates.insert(0, f"Should You Move to {topic_title}? (Honest Analysis)")
                if any(c.isdigit() for c in title[:2]):
                    templates.insert(0, f"7 Reasons {topic_title} is Perfect for Tax Optimization")

    # Return unique suggestions
    seen = set()
    suggestions = []
    for t in templates:
        t_lower = t.lower()
        if t_lower not in seen:
            seen.add(t_lower)
            suggestions.append(t)
            if len(suggestions) >= num_suggestions:
                break

    return suggestions


def generate_recommendations_with_titles(youtube, config: dict, output_dir: str, top_n: int = 20) -> dict:
    """
    Generate recommendations with title suggestions included.
    """
    # Get base recommendations
    recs = generate_recommendations(youtube, config, output_dir, top_n)

    if 'error' in recs:
        return recs

    # Get competitor videos for title generation
    db_path = get_competitive_db_path(output_dir)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    my_channel_id, _ = get_my_channel_id(youtube, config, db_path)
    competitors = list_competitors(db_path, my_channel_id)
    competitor_ids = [c['channel_id'] for c in competitors]

    if competitor_ids:
        placeholders = ','.join('?' * len(competitor_ids))
        cursor.execute(f'''
            SELECT video_id, title, view_count, virality_score FROM videos
            WHERE channel_id IN ({placeholders})
            ORDER BY virality_score DESC LIMIT 500
        ''', competitor_ids)
        comp_videos = [{'video_id': r[0], 'title': r[1], 'view_count': r[2],
                        'virality_score': r[3]} for r in cursor.fetchall()]
    else:
        comp_videos = []

    conn.close()

    # Add title suggestions to each recommendation
    for rec in recs.get('recommendations', []):
        rec['title_suggestions'] = generate_title_suggestions(rec['topic'], comp_videos, 3)

    return recs


def format_recommendations_with_titles(recommendations: dict) -> str:
    """Format recommendations with title suggestions."""
    if 'error' in recommendations:
        return f"❌ {recommendations['error']}"

    recs = recommendations.get('recommendations', [])
    if not recs:
        return "No recommendations found."

    lines = []
    lines.append("")
    lines.append("=" * 75)
    lines.append(f"  TOP VIDEO OPPORTUNITIES FOR {recommendations['my_channel']}")
    lines.append("=" * 75)

    for i, rec in enumerate(recs, 1):
        lines.append("")
        rec_type = rec['recommendation_type']
        type_emoji = {'GAP': '🔴', 'ALIGN': '🟢', 'TRENDING': '🟡', 'MIXED': '⚪'}
        emoji = type_emoji.get(rec_type, '⚪')

        lines.append(f"{emoji} #{i}  {rec['topic'].upper()}")
        lines.append(f"   Score: {rec['opportunity_score']:.1f}  |  Type: {rec_type}  |  "
                    f"Competitors: {rec['competitor_coverage']}  |  Avg Views: {rec['competitor_avg_views']:,}")

        # Title suggestions
        if rec.get('title_suggestions'):
            lines.append("   📝 Title Ideas:")
            for title in rec['title_suggestions']:
                lines.append(f"      • {title}")

    lines.append("")
    lines.append("-" * 75)
    lines.append(f"📊 Analyzed {recommendations['my_videos_analyzed']} of your videos vs "
                f"{recommendations['competitor_videos_analyzed']} competitor videos")
    lines.append(f"🎯 {recommendations['total_opportunities']} total opportunities found")

    return '\n'.join(lines)


def generate_recommendations_html(recommendations: dict, output_path: str) -> None:
    """Generate an HTML dashboard for recommendations."""
    if 'error' in recommendations:
        return

    recs = recommendations.get('recommendations', [])

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Recommendations - {recommendations.get('my_channel', 'Analysis')}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #eee;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{
            text-align: center;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.5em;
        }}
        .subtitle {{
            text-align: center;
            color: #888;
            margin-bottom: 30px;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 40px;
            flex-wrap: wrap;
        }}
        .stat-box {{
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 20px 30px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #888; margin-top: 5px; }}
        .recommendations {{ display: grid; gap: 20px; }}
        .rec-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .rec-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        .rec-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .rec-rank {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }}
        .rec-topic {{ font-size: 1.4em; font-weight: bold; flex: 1; margin-left: 15px; }}
        .rec-score {{
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
        }}
        .rec-type {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            margin-right: 10px;
        }}
        .type-GAP {{ background: #ff4757; color: white; }}
        .type-ALIGN {{ background: #2ed573; color: white; }}
        .type-TRENDING {{ background: #ffa502; color: black; }}
        .type-MIXED {{ background: #747d8c; color: white; }}
        .rec-metrics {{
            display: flex;
            gap: 20px;
            margin: 15px 0;
            flex-wrap: wrap;
        }}
        .metric {{ color: #888; }}
        .metric strong {{ color: #eee; }}
        .titles {{ margin-top: 15px; }}
        .titles h4 {{ color: #667eea; margin-bottom: 10px; }}
        .title-idea {{
            background: rgba(102, 126, 234, 0.1);
            padding: 10px 15px;
            border-radius: 8px;
            margin-bottom: 8px;
            border-left: 3px solid #667eea;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 Video Opportunities</h1>
        <p class="subtitle">Recommendations for {recommendations.get('my_channel', 'Your Channel')}</p>

        <div class="stats">
            <div class="stat-box">
                <div class="stat-value">{len(recs)}</div>
                <div class="stat-label">Top Opportunities</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{recommendations.get('my_videos_analyzed', 0)}</div>
                <div class="stat-label">Your Videos Analyzed</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{recommendations.get('competitor_videos_analyzed', 0)}</div>
                <div class="stat-label">Competitor Videos</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{recommendations.get('competitors_count', 0)}</div>
                <div class="stat-label">Competitors</div>
            </div>
        </div>

        <div class="recommendations">
'''

    for i, rec in enumerate(recs, 1):
        rec_type = rec['recommendation_type']
        titles_html = ""
        if rec.get('title_suggestions'):
            titles_html = '<div class="titles"><h4>💡 Title Ideas:</h4>'
            for title in rec['title_suggestions']:
                titles_html += f'<div class="title-idea">{title}</div>'
            titles_html += '</div>'

        html += f'''
            <div class="rec-card">
                <div class="rec-header">
                    <div class="rec-rank">{i}</div>
                    <div class="rec-topic">{rec['topic'].title()}</div>
                    <div class="rec-score">{rec['opportunity_score']:.0f}</div>
                </div>
                <div>
                    <span class="rec-type type-{rec_type}">{rec_type}</span>
                </div>
                <div class="rec-metrics">
                    <div class="metric">Gap: <strong>{rec['gap_score']:.0f}</strong></div>
                    <div class="metric">Performance: <strong>{rec['performance_score']:.0f}</strong></div>
                    <div class="metric">Alignment: <strong>{rec['alignment_score']:.0f}</strong></div>
                    <div class="metric">Competitors: <strong>{rec['competitor_coverage']}</strong></div>
                    <div class="metric">Avg Views: <strong>{rec['competitor_avg_views']:,}</strong></div>
                </div>
                {titles_html}
            </div>
'''

    html += f'''
        </div>

        <div class="footer">
            Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by YouTube Competitive Analysis Tool
        </div>
    </div>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

