"""
One-off research script: survey Reddit-story-format channels across
sub-niches (AITA/relationship, scary/nosleep, driving) to see what's
actually performing before building an automated pipeline.

Not part of the regular tool CLI -- ad hoc, safe to delete after use.
"""
import os, sys, ssl, json
ssl._create_default_https_context = ssl._create_unverified_context

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '.')
from youtube_analyzer import (
    build, get_channel_info, fetch_video_ids_from_playlist,
    fetch_video_metadata_batch, retry_with_backoff
)
import httplib2
from datetime import datetime, timedelta

api_key = os.environ.get('YOUTUBE_API_KEY')
if not api_key:
    print('ERROR: YOUTUBE_API_KEY not set'); sys.exit(1)

http = httplib2.Http(disable_ssl_certificate_validation=True)
youtube = build('youtube', 'v3', developerKey=api_key, http=http)

QUERIES = {
    'aita_relationship': ['aita reddit stories', 'reddit relationship stories', 'tifu reddit stories'],
    'scary_nosleep': ['scary reddit stories', 'nosleep reddit stories', 'creepy reddit stories'],
    'driving': ['idiots in cars reddit', 'road rage reddit stories', 'driving reddit stories'],
}

def search_channels(query, max_results=10):
    resp = retry_with_backoff(lambda: youtube.search().list(
        part='snippet', q=query, type='channel', maxResults=max_results, relevanceLanguage='en'
    ).execute())
    return [item['snippet']['channelId'] for item in resp.get('items', [])]

results = {}
seen_ids = set()

for bucket, queries in QUERIES.items():
    bucket_channels = []
    ids = []
    for q in queries:
        try:
            ids.extend(search_channels(q))
        except Exception as e:
            print(f'  search error for "{q}": {e}')
    ids = [i for i in dict.fromkeys(ids) if i not in seen_ids]  # dedupe, preserve order
    print(f'\n=== {bucket}: {len(ids)} candidate channels ===')

    for ch_id in ids:
        if ch_id in seen_ids:
            continue
        seen_ids.add(ch_id)
        try:
            info = get_channel_info(youtube, ch_id)
        except Exception as e:
            print(f'  skip {ch_id}: {e}')
            continue

        sub_count = info.get('subscriber_count', 0) or 0
        if sub_count < 5000:
            continue  # skip tiny/irrelevant channels

        since = datetime.now() - timedelta(days=120)
        try:
            vid_ids = fetch_video_ids_from_playlist(
                youtube, info['uploads_playlist_id'], since=since, until=None, limit=30
            )
            videos = fetch_video_metadata_batch(youtube, vid_ids, info) if vid_ids else []
        except Exception as e:
            print(f'  skip {info.get("title")}: video fetch error {e}')
            continue

        if not videos:
            continue

        views = [v['view_count'] for v in videos]
        durations = [v['duration_seconds'] for v in videos]
        avg_views = sum(views) / len(views)
        median_views = sorted(views)[len(views)//2]
        avg_duration = sum(durations) / len(durations)
        upload_rate_per_week = len(videos) / (120/7)
        est_rev = sum(v.get('estimated_revenue_mid', 0) or 0 for v in videos)

        row = {
            'channel': info.get('title'),
            'channel_id': ch_id,
            'subs': sub_count,
            'videos_last_120d': len(videos),
            'uploads_per_week': round(upload_rate_per_week, 2),
            'avg_views': round(avg_views),
            'median_views': median_views,
            'avg_duration_sec': round(avg_duration),
            'est_revenue_120d_usd': round(est_rev, 2),
        }
        bucket_channels.append(row)
        print(f"  {row['channel'][:40]:40s} subs={row['subs']:>9,} vids={row['videos_last_120d']:>3} "
              f"up/wk={row['uploads_per_week']:>4} avg_views={row['avg_views']:>9,} "
              f"dur={row['avg_duration_sec']:>5}s est_rev_120d=${row['est_revenue_120d_usd']:>8,}")

    bucket_channels.sort(key=lambda r: r['avg_views'], reverse=True)
    results[bucket] = bucket_channels

out_path = os.path.join('output', 'reddit_story_scan.json')
os.makedirs('output', exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)
print(f'\nSaved -> {out_path}')
