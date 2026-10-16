"""Channel sync, comment sync, snapshots, trends."""

from .common import *
from .fetch import fetch_video_ids_from_playlist, fetch_video_metadata_batch, get_channel_info, resolve_channel_id
from .store import get_competitive_db_path, list_competitors, migrate_competitive_database, save_competitor_to_db

# =============================================================================
# INCREMENTAL SYNC
# =============================================================================

def sync_channel(youtube, channel_input: str, db_path: str, config: dict,
                 force_refresh: bool = False) -> dict:
    """
    Sync a channel - only fetch new videos since last sync.
    Returns summary of what was synced.
    """
    migrate_competitive_database(db_path)

    try:
        channel_id, channel_title = resolve_channel_id(youtube, channel_input)
    except Exception as e:
        return {'error': str(e), 'channel': channel_input}

    try:
        channel_info = get_channel_info(youtube, channel_id)
    except Exception as e:
        return {'error': str(e), 'channel': channel_input}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get last fetch time
    cursor.execute('SELECT last_fetched_at FROM channels WHERE channel_id = ?', (channel_id,))
    row = cursor.fetchone()
    last_fetched = row[0] if row else None

    # Determine since date
    sync_config = config.get('sync', {})
    lookback_days = sync_config.get('default_lookback_days', 30)

    if force_refresh or not last_fetched:
        since = datetime.now() - timedelta(days=lookback_days)
    else:
        since = datetime.fromisoformat(last_fetched.replace('Z', '+00:00')).replace(tzinfo=None)

    # Fetch video IDs
    try:
        video_ids = fetch_video_ids_from_playlist(
            youtube, channel_info['uploads_playlist_id'],
            since=since, until=None, limit=None
        )
    except Exception as e:
        conn.close()
        return {'error': str(e), 'channel': channel_input}

    # Filter out existing videos unless force refresh
    if not force_refresh:
        cursor.execute('SELECT video_id FROM videos WHERE channel_id = ?', (channel_id,))
        existing_ids = {row[0] for row in cursor.fetchall()}
        new_video_ids = [vid for vid in video_ids if vid not in existing_ids]
    else:
        new_video_ids = video_ids
        existing_ids = set()

    # Fetch metadata for new videos
    new_videos = []
    if new_video_ids:
        new_videos = fetch_video_metadata_batch(youtube, new_video_ids, channel_info)

        # Save to database
        for v in new_videos:
            cursor.execute('''
                INSERT OR REPLACE INTO videos
                (video_id, channel_id, title, publish_date, view_count, like_count,
                 comment_count, engagement_rate, duration_seconds, virality_score,
                 title_hook_score, is_short, is_series, is_collab, estimated_revenue_mid, thumbnail_high)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                v['video_id'], v['channel_id'], v['title'], v['publish_date'],
                v['view_count'], v['like_count'], v['comment_count'],
                v['engagement_rate'], v['duration_seconds'], v['virality_score'],
                v['title_hook_score'], 1 if v['is_short'] else 0,
                1 if v['is_series'] else 0, 1 if v['is_collab'] else 0,
                v['estimated_revenue_mid'], v['thumbnail_high']
            ))

    # Update channel info
    cursor.execute('''
        INSERT OR REPLACE INTO channels
        (channel_id, title, subscriber_count, video_count, view_count, fetched_at, last_fetched_at, handle)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        channel_id, channel_title, channel_info.get('subscriber_count', 0),
        channel_info.get('video_count', 0), channel_info.get('view_count', 0),
        datetime.now().isoformat(), datetime.now().isoformat(),
        channel_input if channel_input.startswith('@') else None
    ))

    conn.commit()
    conn.close()

    return {
        'channel_id': channel_id,
        'title': channel_title,
        'new_videos': len(new_videos),
        'existing_videos': len(existing_ids),
        'total_fetched': len(video_ids),
        'since': since.isoformat(),
        'force_refresh': force_refresh,
    }


def sync_all(youtube, config: dict, output_dir: str, force_refresh: bool = False) -> dict:
    """
    Sync my channel and all competitors.
    """
    db_path = get_competitive_db_path(output_dir)
    migrate_competitive_database(db_path)

    results = {'my_channel': None, 'competitors': [], 'errors': []}

    # Sync my channel first
    my_channel = config.get('my_channel')
    if my_channel:
        print(f"\n📺 Syncing my channel: {my_channel}")
        result = sync_channel(youtube, my_channel, db_path, config, force_refresh)
        results['my_channel'] = result
        if 'error' not in result:
            print(f"   ✅ {result['title']}: {result['new_videos']} new videos")

            # Mark as my channel in DB
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE channels SET is_my_channel = 1 WHERE channel_id = ?',
                          (result['channel_id'],))
            conn.commit()
            conn.close()
        else:
            print(f"   ❌ Error: {result['error']}")
            results['errors'].append(result)

    # Get my channel ID for competitor lookup
    my_channel_id = results['my_channel'].get('channel_id') if results['my_channel'] else None

    # Sync seed competitors from config
    seed_competitors = config.get('seed_competitors') or []
    for comp in seed_competitors:
        print(f"\n🎯 Syncing competitor: {comp}")
        result = sync_channel(youtube, comp, db_path, config, force_refresh)
        results['competitors'].append(result)
        if 'error' not in result:
            print(f"   ✅ {result['title']}: {result['new_videos']} new videos")

            # Save as competitor in DB
            if my_channel_id:
                save_competitor_to_db(youtube, comp, my_channel_id, 1.0, 'seed_config', db_path)
        else:
            print(f"   ❌ Error: {result['error']}")
            results['errors'].append(result)

    # Sync discovered competitors from database
    if my_channel_id:
        db_competitors = list_competitors(db_path, my_channel_id)
        for comp in db_competitors:
            # Skip if already synced as seed
            if any(c.get('channel_id') == comp['channel_id'] for c in results['competitors']):
                continue

            print(f"\n🔍 Syncing discovered competitor: {comp['title']}")
            result = sync_channel(youtube, comp['channel_id'], db_path, config, force_refresh)
            results['competitors'].append(result)
            if 'error' not in result:
                print(f"   ✅ {result['title']}: {result['new_videos']} new videos")
            else:
                print(f"   ❌ Error: {result['error']}")

    if config.get('comment_sync', {}).get('channels'):
        print("\n💬 Syncing comments...")
        results['comments'] = sync_comments(youtube, config, db_path)

    return results


def sync_comments(youtube, config: dict, db_path: str) -> dict:
    """
    Sync top-level comments on the top videos of the channels listed under
    `comment_sync.channels` in the config (my_channels.yaml).

    Videos with no stored comments are backfilled in relevance order up to
    `max_per_video`; videos that already have comments are read newest-first and
    stop at the first page that reaches a stored comment. Each page is committed
    immediately, so an interrupted run resumes without losing finished pages.
    """
    cs = config.get('comment_sync') or {}
    channels = cs.get('channels') or []
    top_videos = int(cs.get('top_videos', 25))
    top_videos_by_channel = cs.get('top_videos_by_channel') or {}
    max_per_video = int(cs.get('max_per_video', 200))

    migrate_competitive_database(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    summary = {'channels': [], 'new_comments': 0, 'errors': []}

    for ch in channels:
        cursor.execute('SELECT channel_id, title FROM channels WHERE lower(handle) = lower(?)', (ch,))
        row = cursor.fetchone()
        if row:
            channel_id, channel_title = row
        else:
            try:
                channel_id, channel_title = resolve_channel_id(youtube, ch)
            except Exception as e:
                summary['errors'].append({'channel': ch, 'error': str(e)})
                print(f"   ❌ {ch}: {e}")
                continue

        cursor.execute('''
            SELECT video_id FROM videos
            WHERE channel_id = ? AND COALESCE(is_short, 0) = 0 AND COALESCE(comment_count, 0) > 0
            ORDER BY view_count DESC LIMIT ?
        ''', (channel_id, int(top_videos_by_channel.get(ch, top_videos))))
        video_ids = [r[0] for r in cursor.fetchall()]

        channel_new = 0
        for video_id in video_ids:
            cursor.execute('SELECT comment_id FROM comments WHERE video_id = ?', (video_id,))
            known = {r[0] for r in cursor.fetchall()}
            order = 'time' if known else 'relevance'
            fetched = 0
            page_token = None

            while fetched < max_per_video:
                try:
                    resp = retry_with_backoff(lambda: youtube.commentThreads().list(
                        part='snippet', videoId=video_id, maxResults=100, pageToken=page_token,
                        order=order, textFormat='plainText'
                    ).execute())
                except HttpError as e:
                    reason = ''
                    try:
                        reason = e.error_details[0].get('reason', '')
                    except Exception:
                        pass
                    if reason == 'quotaExceeded':
                        conn.close()
                        summary['errors'].append({'channel': ch, 'error': 'quotaExceeded'})
                        print("   ❌ API quota exceeded, stopping comment sync (progress saved)")
                        return summary
                    break  # comments disabled or video unavailable: skip this video

                reached_known = False
                now = datetime.now().isoformat()
                for item in resp.get('items', []):
                    top = item['snippet']['topLevelComment']
                    s = top['snippet']
                    if top['id'] in known:
                        reached_known = True
                    else:
                        channel_new += 1
                    cursor.execute('''
                        INSERT INTO comments
                        (comment_id, video_id, channel_id, author, text, like_count, reply_count, published_at, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(comment_id) DO UPDATE SET
                            like_count = excluded.like_count, reply_count = excluded.reply_count,
                            fetched_at = excluded.fetched_at
                    ''', (top['id'], video_id, channel_id, s.get('authorDisplayName'),
                          s.get('textDisplay'), s.get('likeCount', 0),
                          item['snippet'].get('totalReplyCount', 0), s.get('publishedAt'), now))
                    fetched += 1
                conn.commit()

                page_token = resp.get('nextPageToken')
                if not page_token or (order == 'time' and reached_known):
                    break

        summary['channels'].append({'channel': ch, 'title': channel_title,
                                    'videos': len(video_ids), 'new_comments': channel_new})
        summary['new_comments'] += channel_new
        print(f"   ✅ {channel_title}: {channel_new} new comments across {len(video_ids)} videos")

    conn.close()
    return summary


def take_snapshot(db_path: str) -> dict:
    """
    Take a snapshot of current view/like counts for all videos.
    Used for trend tracking over time.
    """
    if not os.path.exists(db_path):
        return {'error': 'Database not found'}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all videos
    cursor.execute('SELECT video_id, view_count, like_count, comment_count FROM videos')
    videos = cursor.fetchall()

    snapshot_date = datetime.now().strftime('%Y-%m-%d')
    inserted = 0

    for video_id, views, likes, comments in videos:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO video_snapshots
                (video_id, snapshot_date, view_count, like_count, comment_count)
                VALUES (?, ?, ?, ?, ?)
            ''', (video_id, snapshot_date, views, likes, comments))
            if cursor.rowcount > 0:
                inserted += 1
        except sqlite3.IntegrityError:
            pass  # Already have snapshot for today

    # Channel-level snapshot (subscribers/views/videos) so we can later tell
    # a real audience-growth trend apart from a views-only algorithm bump.
    cursor.execute('SELECT channel_id, subscriber_count, view_count, video_count FROM channels')
    channels = cursor.fetchall()
    channels_snapshot = 0
    for channel_id, subs, views, vid_count in channels:
        cursor.execute('''
            INSERT OR IGNORE INTO channel_snapshots
            (channel_id, snapshot_date, subscriber_count, view_count, video_count)
            VALUES (?, ?, ?, ?, ?)
        ''', (channel_id, snapshot_date, subs, views, vid_count))
        if cursor.rowcount > 0:
            channels_snapshot += 1

    conn.commit()
    conn.close()

    return {
        'snapshot_date': snapshot_date,
        'videos_snapshot': inserted,
        'total_videos': len(videos),
        'channels_snapshot': channels_snapshot,
        'total_channels': len(channels),
    }


def get_video_trends(db_path: str, video_id: str, days: int = 30) -> list:
    """Get view count trends for a specific video."""
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    cursor.execute('''
        SELECT snapshot_date, view_count, like_count, comment_count
        FROM video_snapshots
        WHERE video_id = ? AND snapshot_date >= ?
        ORDER BY snapshot_date ASC
    ''', (video_id, since_date))

    rows = cursor.fetchall()
    conn.close()

    trends = []
    prev_views = None
    for date, views, likes, comments in rows:
        daily_growth = views - prev_views if prev_views is not None else 0
        trends.append({
            'date': date,
            'view_count': views,
            'like_count': likes,
            'comment_count': comments,
            'daily_view_growth': daily_growth,
        })
        prev_views = views

    return trends

