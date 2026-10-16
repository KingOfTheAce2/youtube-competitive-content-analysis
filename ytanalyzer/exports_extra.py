"""PDF and RSS output."""

from .common import *

# =============================================================================
# ADDITIONAL EXPORT FORMATS
# =============================================================================

def save_to_pdf(analytics: dict, channel_info: dict, videos: list[dict], output_path: str) -> bool:
    """
    Generate a PDF report using reportlab.
    """
    if not PDF_AVAILABLE:
        print("PDF export requires reportlab: pip install reportlab")
        return False

    try:
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph(f"YouTube Analysis Report: {channel_info['title']}", styles['Title']))
        story.append(Spacer(1, 20))

        # Overview
        story.append(Paragraph("Channel Overview", styles['Heading2']))
        overview = analytics.get('overview', {})
        overview_data = [
            ['Metric', 'Value'],
            ['Subscribers', format_number(channel_info.get('subscriber_count', 0))],
            ['Videos Analyzed', str(overview.get('total_videos_analyzed', 0))],
            ['Total Views', format_number(overview.get('total_views', 0))],
            ['Avg Views/Video', format_number(overview.get('average_views_per_video', 0))],
            ['Avg Virality', f"{overview.get('average_virality_score', 0):.4f}"],
        ]

        t = Table(overview_data, colWidths=[200, 200])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(t)
        story.append(Spacer(1, 20))

        # Health Score
        health = analytics.get('health_score', {})
        story.append(Paragraph(f"Channel Health: {health.get('total_score', 0):.0f}/100 ({health.get('grade', 'N/A')})", styles['Heading2']))
        story.append(Spacer(1, 10))

        # Top Videos
        story.append(Paragraph("Top 10 Videos by Virality", styles['Heading2']))
        top_videos = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:10]
        video_data = [['Title', 'Views', 'Virality']]
        for v in top_videos:
            video_data.append([
                v['title'][:40] + '...' if len(v['title']) > 40 else v['title'],
                format_number(v['view_count']),
                f"{v.get('virality_score', 0):.3f}"
            ])

        t2 = Table(video_data, colWidths=[250, 100, 80])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(t2)
        story.append(Spacer(1, 20))

        # Recommendations
        story.append(Paragraph("Strategic Recommendations", styles['Heading2']))
        for rec in analytics.get('recommendations', [])[:10]:
            story.append(Paragraph(f"• {rec}", styles['Normal']))

        # Build PDF
        doc.build(story)
        print(f"Saved PDF: {output_path}")
        return True
    except Exception as e:
        print(f"PDF export error: {e}")
        return False


def generate_rss_feed(channel_info: dict, videos: list[dict], output_path: str) -> None:
    """
    Generate an RSS feed for channel videos.
    """
    rss_items = []
    for v in sorted(videos, key=lambda x: x['publish_date'], reverse=True)[:50]:
        item = f"""    <item>
      <title><![CDATA[{v['title']}]]></title>
      <link>https://www.youtube.com/watch?v={v['video_id']}</link>
      <guid>https://www.youtube.com/watch?v={v['video_id']}</guid>
      <pubDate>{v['publish_date']}</pubDate>
      <description><![CDATA[
Views: {format_number(v['view_count'])}
Virality: {v.get('virality_score', 0):.3f}
Duration: {v.get('duration_formatted', 'N/A')}
      ]]></description>
    </item>"""
        rss_items.append(item)

    rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{channel_info['title']} - Analysis Feed</title>
    <link>https://www.youtube.com/channel/{channel_info['channel_id']}</link>
    <description>YouTube analytics feed for {channel_info['title']}</description>
    <lastBuildDate>{datetime.now().isoformat()}</lastBuildDate>
    <generator>YouTube Competitive Analysis Tool</generator>
{chr(10).join(rss_items)}
  </channel>
</rss>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(rss_content)
    print(f"Saved RSS feed: {output_path}")

