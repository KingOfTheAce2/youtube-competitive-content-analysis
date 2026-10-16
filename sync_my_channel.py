"""
One-shot: sync only your own channel with a deep lookback.

Parameterized so a second channel can be synced without editing this file:
    python sync_my_channel.py --channel @OtherChannel --output otherchannel/output
With no --channel it uses my_channel from my_channels.yaml (git-ignored).
"""
import argparse, os, sys, sqlite3, ssl
ssl._create_default_https_context = ssl._create_unverified_context

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '.')
from youtube_analyzer import (
    build, resolve_channel_id, get_channel_info,
    fetch_video_ids_from_playlist, fetch_video_metadata_batch,
    migrate_competitive_database, get_competitive_db_path, load_config
)
import httplib2
from datetime import datetime, timedelta

parser = argparse.ArgumentParser(description="Sync your own channel with a deep lookback")
parser.add_argument('--channel', default=load_config().get('my_channel'), help='Your channel handle (default: my_channel in my_channels.yaml)')
parser.add_argument('--output', default='./output', help='Output directory (default: ./output)')
parser.add_argument('--lookback-days', type=int, default=1500, help='Days to look back (default: 1500)')
args = parser.parse_args()
if not args.channel:
    parser.error('no --channel given and my_channel is not set in my_channels.yaml')

OUTPUT_DIR = args.output
CHANNEL    = args.channel
LOOKBACK   = args.lookback_days  # days — enough to capture all videos

api_key = os.environ.get('YOUTUBE_API_KEY')
if not api_key:
    print('ERROR: YOUTUBE_API_KEY not set'); sys.exit(1)

http = httplib2.Http(disable_ssl_certificate_validation=True)
youtube = build('youtube', 'v3', developerKey=api_key, http=http)

db_path = get_competitive_db_path(OUTPUT_DIR)
migrate_competitive_database(db_path)

print(f'Resolving channel {CHANNEL}...')
channel_id, channel_title = resolve_channel_id(youtube, CHANNEL)
channel_info = get_channel_info(youtube, channel_id)
print(f'Channel: {channel_title}  ({channel_id})')
print(f'YouTube reports {channel_info.get("video_count", "?")} total videos')

since = datetime.now() - timedelta(days=LOOKBACK)
print(f'Fetching video IDs since {since.date()} ...')
video_ids = fetch_video_ids_from_playlist(
    youtube, channel_info['uploads_playlist_id'],
    since=since, until=None, limit=None
)
print(f'Found {len(video_ids)} video IDs in playlist')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT video_id FROM videos WHERE channel_id = ?', (channel_id,))
existing = {r[0] for r in cursor.fetchall()}
new_ids = [v for v in video_ids if v not in existing]
print(f'Already in DB: {len(existing)}  |  New to fetch: {len(new_ids)}')

if new_ids:
    print(f'Fetching metadata for {len(new_ids)} new videos...')
    new_videos = fetch_video_metadata_batch(youtube, new_ids, channel_info)
    for v in new_videos:
        cursor.execute('''
            INSERT OR REPLACE INTO videos
            (video_id, channel_id, title, publish_date, view_count, like_count,
             comment_count, engagement_rate, duration_seconds, virality_score,
             title_hook_score, is_short, is_series, is_collab, estimated_revenue_mid, thumbnail_high)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            v['video_id'], v['channel_id'], v['title'], v['publish_date'],
            v['view_count'], v['like_count'], v['comment_count'],
            v['engagement_rate'], v['duration_seconds'], v['virality_score'],
            v['title_hook_score'], 1 if v['is_short'] else 0,
            1 if v['is_series'] else 0, 1 if v['is_collab'] else 0,
            v['estimated_revenue_mid'], v['thumbnail_high']
        ))

cursor.execute('''
    INSERT OR REPLACE INTO channels
    (channel_id, title, subscriber_count, video_count, view_count,
     fetched_at, last_fetched_at, is_my_channel, handle)
    VALUES (?,?,?,?,?,?,?,1,?)
''', (
    channel_id, channel_title,
    channel_info.get('subscriber_count', 0),
    channel_info.get('video_count', 0),
    channel_info.get('view_count', 0),
    datetime.now().isoformat(), datetime.now().isoformat(),
    CHANNEL
))
conn.commit()

total = cursor.execute('SELECT COUNT(*) FROM videos WHERE channel_id=?', (channel_id,)).fetchone()[0]
conn.close()
print(f'\nDone. Total {CHANNEL} videos now in DB: {total}')
