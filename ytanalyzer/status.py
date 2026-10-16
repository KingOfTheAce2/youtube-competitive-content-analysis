"""Status report."""

from .common import *
from .store import get_competitive_db_path, get_my_channel_id, list_competitors

# =============================================================================
# USER-FRIENDLY ENHANCEMENTS
# =============================================================================

def get_status(youtube, config: dict, output_dir: str) -> dict:
    """
    Get quick status overview - my channel, competitors, last sync, pending actions.
    """
    db_path = get_competitive_db_path(output_dir)

    status = {
        'my_channel': None,
        'competitors': {'count': 0, 'list': []},
        'videos': {'my_count': 0, 'competitor_count': 0},
        'last_sync': None,
        'snapshots': 0,
        'recommendations_available': False,
        'pending_actions': [],
    }

    # Check my_channel
    my_channel = config.get('my_channel')
    if my_channel:
        status['my_channel'] = {'handle': my_channel, 'resolved': False}
        try:
            my_channel_id, my_channel_title = get_my_channel_id(youtube, config, db_path)
            if my_channel_id:
                status['my_channel']['resolved'] = True
                status['my_channel']['title'] = my_channel_title
                status['my_channel']['channel_id'] = my_channel_id
        except:
            pass
    else:
        status['pending_actions'].append("Set your channel: --set-my-channel @YourChannel")

    if not os.path.exists(db_path):
        status['pending_actions'].append("Run first sync: --sync")
        return status

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get my channel stats
    if status['my_channel'] and status['my_channel'].get('channel_id'):
        my_id = status['my_channel']['channel_id']

        cursor.execute('SELECT last_fetched_at, subscriber_count FROM channels WHERE channel_id = ?', (my_id,))
        row = cursor.fetchone()
        if row:
            status['last_sync'] = row[0]
            status['my_channel']['subscribers'] = row[1]

        cursor.execute('SELECT COUNT(*) FROM videos WHERE channel_id = ?', (my_id,))
        status['videos']['my_count'] = cursor.fetchone()[0]

        # Get competitors
        competitors = list_competitors(db_path, my_id)
        status['competitors']['count'] = len(competitors)
        status['competitors']['list'] = competitors[:5]

        if competitors:
            comp_ids = [c['channel_id'] for c in competitors]
            placeholders = ','.join('?' * len(comp_ids))
            cursor.execute(f'SELECT COUNT(*) FROM videos WHERE channel_id IN ({placeholders})', comp_ids)
            status['videos']['competitor_count'] = cursor.fetchone()[0]

    # Snapshots
    cursor.execute('SELECT COUNT(DISTINCT snapshot_date) FROM video_snapshots')
    status['snapshots'] = cursor.fetchone()[0]

    # Recommendations
    cursor.execute('SELECT COUNT(*) FROM topic_recommendations')
    status['recommendations_available'] = cursor.fetchone()[0] > 0

    conn.close()

    # Determine pending actions
    if status['competitors']['count'] == 0:
        status['pending_actions'].append("Add competitors: --add-competitor @Channel or --discover-competitors")

    if status['videos']['my_count'] == 0:
        status['pending_actions'].append("Sync your channel: --sync")

    if status['videos']['competitor_count'] == 0 and status['competitors']['count'] > 0:
        status['pending_actions'].append("Sync competitor videos: --sync")

    if not status['recommendations_available'] and status['videos']['competitor_count'] > 0:
        status['pending_actions'].append("Generate recommendations: --recommend")

    return status


def format_status(status: dict) -> str:
    """Format status as nice CLI output."""
    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  YOUTUBE COMPETITIVE ANALYSIS - STATUS")
    lines.append("=" * 60)

    # My Channel
    lines.append("")
    if status['my_channel']:
        mc = status['my_channel']
        if mc.get('resolved'):
            subs = f" ({mc.get('subscribers', 0):,} subs)" if mc.get('subscribers') else ""
            lines.append(f"📺 My Channel: {mc['title']}{subs}")
        else:
            lines.append(f"📺 My Channel: {mc['handle']} (not synced yet)")
    else:
        lines.append("📺 My Channel: Not set")

    # Competitors
    lines.append("")
    lines.append(f"🎯 Competitors Tracked: {status['competitors']['count']}")
    if status['competitors']['list']:
        for comp in status['competitors']['list'][:3]:
            lines.append(f"   • {comp['title'][:35]}")
        if status['competitors']['count'] > 3:
            lines.append(f"   ... and {status['competitors']['count'] - 3} more")

    # Videos
    lines.append("")
    lines.append(f"📊 Videos in Database:")
    lines.append(f"   • Your videos: {status['videos']['my_count']:,}")
    lines.append(f"   • Competitor videos: {status['videos']['competitor_count']:,}")

    # Last Sync
    lines.append("")
    if status['last_sync']:
        try:
            sync_date = datetime.fromisoformat(status['last_sync'].replace('Z', '+00:00'))
            days_ago = (datetime.now(sync_date.tzinfo) - sync_date).days
            if days_ago == 0:
                sync_str = "Today"
            elif days_ago == 1:
                sync_str = "Yesterday"
            else:
                sync_str = f"{days_ago} days ago"
            lines.append(f"🔄 Last Sync: {sync_str}")
        except:
            lines.append(f"🔄 Last Sync: {status['last_sync'][:10]}")
    else:
        lines.append("🔄 Last Sync: Never")

    lines.append(f"📸 Snapshots: {status['snapshots']}")
    lines.append(f"💡 Recommendations: {'Available' if status['recommendations_available'] else 'Not generated'}")

    # Pending Actions
    if status['pending_actions']:
        lines.append("")
        lines.append("⚡ NEXT STEPS:")
        for action in status['pending_actions'][:3]:
            lines.append(f"   → {action}")

    lines.append("")
    lines.append("=" * 60)

    return '\n'.join(lines)

