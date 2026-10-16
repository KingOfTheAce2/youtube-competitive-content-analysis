"""Growth quality analysis."""

from .common import *

def analyze_growth_quality(db_path: str, channel_id: str, recent_n: int = 15) -> dict:
    """
    Distinguish a real audience-growth trend from a views-only algorithm bump
    (e.g. YouTube pushing a channel's videos into Shorts/Browse feeds without
    the audience actually converting into subscribers or engaged viewers).

    Views are easy for the algorithm to inflate; subscriber conversion and
    engagement rate are not, because they require someone to act, not just
    be shown a thumbnail. So we compare the recent-video trend in views
    against the trend in engagement rate and views-per-subscriber, and
    against the channel-level subscriber trajectory when snapshot history
    is available. A verdict of "algorithm-driven" means views moved a lot
    more than those harder-to-inflate signals did.
    """
    if not os.path.exists(db_path):
        return {'error': 'Database not found'}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    channel_row = cursor.execute(
        'SELECT title, subscriber_count FROM channels WHERE channel_id = ?', (channel_id,)
    ).fetchone()
    if not channel_row:
        conn.close()
        return {'error': f'Channel {channel_id} not found'}
    channel_title, current_subs = channel_row

    videos = cursor.execute('''
        SELECT view_count, like_count, comment_count, publish_date
        FROM videos WHERE channel_id = ?
        ORDER BY publish_date DESC
    ''', (channel_id,)).fetchall()

    def period_stats(rows):
        if not rows:
            return None
        views = [r[0] or 0 for r in rows]
        eng_rates = [((r[1] or 0) + (r[2] or 0)) / r[0] for r in rows if r[0]]
        avg_views = sum(views) / len(views)
        avg_eng = sum(eng_rates) / len(eng_rates) if eng_rates else 0
        avg_views_per_sub = avg_views / current_subs if current_subs else 0
        return {
            'avg_views': round(avg_views, 1),
            'avg_engagement_rate_pct': round(avg_eng * 100, 3),
            'avg_views_per_subscriber': round(avg_views_per_sub, 4),
            'n': len(rows),
        }

    recent = period_stats(videos[:recent_n])
    prior = period_stats(videos[recent_n:recent_n * 2])

    def pct_change(new, old):
        if not old:
            return None
        return round((new - old) / old * 100, 1)

    view_growth = pct_change(recent['avg_views'], prior['avg_views']) if recent and prior else None
    engagement_growth = pct_change(recent['avg_engagement_rate_pct'], prior['avg_engagement_rate_pct']) if recent and prior else None

    # Channel-level subscriber trend, if we have more than one snapshot day
    sub_snapshots = cursor.execute('''
        SELECT snapshot_date, subscriber_count, view_count FROM channel_snapshots
        WHERE channel_id = ? ORDER BY snapshot_date ASC
    ''', (channel_id,)).fetchall()
    conn.close()

    sub_trend = None
    if len(sub_snapshots) >= 2:
        first, last = sub_snapshots[0], sub_snapshots[-1]
        sub_growth = pct_change(last[1], first[1])
        channel_view_growth = pct_change(last[2], first[2])
        sub_trend = {
            'from': first[0], 'to': last[0],
            'subscriber_growth_pct': sub_growth,
            'total_view_count_growth_pct': channel_view_growth,
        }

    verdict = 'insufficient_data'
    notes = []
    if view_growth is not None and engagement_growth is not None:
        # Views jumped a lot while engagement rate (a harder-to-inflate,
        # per-viewer signal) stayed flat or fell -> looks algorithm-driven.
        if view_growth > 25 and engagement_growth <= view_growth / 3:
            verdict = 'likely_algorithm_driven'
            notes.append(
                f"Views per video up {view_growth}% but engagement rate only moved "
                f"{engagement_growth}% — views likely came from wider algorithmic "
                f"placement (Shorts/Browse), not a more engaged audience."
            )
        elif view_growth > 0 and engagement_growth > 0:
            verdict = 'likely_organic'
            notes.append(
                f"Views (+{view_growth}%) and engagement ({'+' if engagement_growth>=0 else ''}{engagement_growth}%) "
                f"moved together — consistent with real audience growth, not just an algorithm push."
            )
        else:
            verdict = 'mixed_or_declining'

    if sub_trend and sub_trend['subscriber_growth_pct'] is not None:
        notes.append(
            f"Subscriber count changed {sub_trend['subscriber_growth_pct']}% between "
            f"{sub_trend['from']} and {sub_trend['to']}, vs total channel views "
            f"{sub_trend['total_view_count_growth_pct']}% — subscriber conversion is "
            f"the hardest signal for an algorithm bump to fake, so weight it heavily "
            f"once you have a few weeks of snapshots."
        )
    else:
        notes.append(
            "Only one channel_snapshots datapoint exists so far — run --snapshot "
            "again in a week or two to get a real subscriber-vs-view growth comparison."
        )

    return {
        'channel_id': channel_id,
        'channel_title': channel_title,
        'recent_period': recent,
        'prior_period': prior,
        'view_growth_pct': view_growth,
        'engagement_growth_pct': engagement_growth,
        'subscriber_trend': sub_trend,
        'verdict': verdict,
        'notes': notes,
    }


def format_growth_quality(result: dict) -> str:
    if 'error' in result:
        return f"❌ {result['error']}"

    lines = []
    lines.append(f"\n{'='*60}\n  ORGANIC vs ALGORITHM-DRIVEN GROWTH CHECK\n{'='*60}")
    lines.append(f"Channel: {result['channel_title']} ({result['channel_id']})\n")

    r, p = result['recent_period'], result['prior_period']
    if r and p:
        lines.append(f"Recent {r['n']} videos  : avg views {r['avg_views']:.0f} | engagement {r['avg_engagement_rate_pct']:.3f}% | views/sub {r['avg_views_per_subscriber']:.4f}")
        lines.append(f"Prior  {p['n']} videos  : avg views {p['avg_views']:.0f} | engagement {p['avg_engagement_rate_pct']:.3f}% | views/sub {p['avg_views_per_subscriber']:.4f}")
        lines.append(f"\nView growth: {result['view_growth_pct']}%   Engagement growth: {result['engagement_growth_pct']}%")
    else:
        lines.append("Not enough videos yet to compare recent vs prior periods.")

    verdict_labels = {
        'likely_algorithm_driven': '⚠️  LIKELY ALGORITHM-DRIVEN (views up, engagement not keeping pace)',
        'likely_organic': '✅ LIKELY ORGANIC (views and engagement moving together)',
        'mixed_or_declining': '➖ MIXED / DECLINING',
        'insufficient_data': 'ℹ️  INSUFFICIENT DATA',
    }
    lines.append(f"\nVerdict: {verdict_labels.get(result['verdict'], result['verdict'])}\n")
    for n in result['notes']:
        lines.append(f"  • {n}")
    lines.append("")
    return '\n'.join(lines)

