"""
Collect Reddit posts as a source of video topic ideas.

Reads public subreddit Atom feeds (no account or API key). Feeds carry no scores or comment
counts, so a post's rank inside the "top of week / month / year" feed is the popularity signal.

Config (my_channels.yaml):
    reddit_sync:
      subreddits: [expats, IWantOut, digitalnomad]
      feeds: [top_week, top_month, top_year]   # optional, these are the defaults
      limit: 100                               # posts per feed, max 100

    python reddit_topic_scanner.py                  # fetch and store
    python reddit_topic_scanner.py --subreddit tax  # one subreddit, ignoring the config list

Posts go to the reddit_posts / reddit_post_ranks tables in output/competitive_analysis.db.
Each feed is committed as soon as it is fetched, and reruns just refresh ranks.
"""
import argparse, os, re, sqlite3, sys, time
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape

import requests

sys.path.insert(0, '.')
from youtube_analyzer import get_competitive_db_path, load_config, migrate_competitive_database

UA = 'windows:youtube-topic-research:v0.1 (personal research, low volume)'
ATOM = '{http://www.w3.org/2005/Atom}'
DEFAULT_FEEDS = ['top_week', 'top_month', 'top_year']
PAUSE_SECONDS = 3  # be gentle: Reddit rate-limits unauthenticated feeds

parser = argparse.ArgumentParser(description='Collect Reddit posts as video topic ideas')
parser.add_argument('--subreddit', action='append', help='Override the config list (repeatable)')
parser.add_argument('--output', default='./output', help='Output directory (default: ./output)')
args = parser.parse_args()

config = load_config('config.yaml')
rc = config.get('reddit_sync') or {}
subreddits = args.subreddit or rc.get('subreddits') or []
feeds = rc.get('feeds') or DEFAULT_FEEDS
limit = min(int(rc.get('limit', 100)), 100)
if not subreddits:
    sys.exit('No subreddits: add reddit_sync.subreddits to my_channels.yaml or pass --subreddit.')

db_path = get_competitive_db_path(args.output)
migrate_competitive_database(db_path)
conn = sqlite3.connect(db_path)
conn.execute('''CREATE TABLE IF NOT EXISTS reddit_posts (
    post_id TEXT PRIMARY KEY, subreddit TEXT, title TEXT, body TEXT, author TEXT,
    published_at TEXT, url TEXT, fetched_at TEXT)''')
conn.execute('''CREATE TABLE IF NOT EXISTS reddit_post_ranks (
    post_id TEXT, feed TEXT, rank INTEGER, fetched_at TEXT, PRIMARY KEY (post_id, feed))''')
conn.execute('CREATE INDEX IF NOT EXISTS idx_reddit_posts_sub ON reddit_posts(subreddit)')


def clean(html):
    text = re.sub(r'<[^>]+>', ' ', unescape(html or ''))
    text = re.sub(r'\[link\]|\[comments\]|submitted by\s+/u/\S+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def fetch(url):
    for attempt in range(3):
        r = requests.get(url, headers={'User-Agent': UA}, timeout=30)
        if r.status_code == 200:
            return r.text
        if r.status_code in (429, 503):
            wait = int(r.headers.get('retry-after', 30 * (attempt + 1)))
            print(f'    rate limited ({r.status_code}), waiting {wait}s')
            time.sleep(wait)
            continue
        print(f'    HTTP {r.status_code}, skipping')
        return None
    return None


total = 0
for sub in subreddits:
    for feed in feeds:
        kind, _, period = feed.partition('_')
        url = f'https://www.reddit.com/r/{sub}/{kind}/.rss?limit={limit}'
        if period:
            url += f'&t={period}'
        print(f'r/{sub} {feed} ...')
        body = fetch(url)
        time.sleep(PAUSE_SECONDS)
        if not body:
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError as e:
            print(f'    unreadable feed: {e}')
            continue
        now = datetime.now().isoformat()
        n = 0
        for rank, entry in enumerate(root.findall(ATOM + 'entry'), start=1):
            raw_id = entry.findtext(ATOM + 'id') or ''
            post_id = raw_id.replace('t3_', '')
            link = entry.find(ATOM + 'link')
            author = entry.find(ATOM + 'author')
            conn.execute('''
                INSERT INTO reddit_posts (post_id, subreddit, title, body, author, published_at, url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET fetched_at = excluded.fetched_at
            ''', (post_id, sub, entry.findtext(ATOM + 'title'), clean(entry.findtext(ATOM + 'content'))[:1500],
                  author.findtext(ATOM + 'name') if author is not None else None,
                  entry.findtext(ATOM + 'updated'), link.get('href') if link is not None else None, now))
            conn.execute('''
                INSERT INTO reddit_post_ranks (post_id, feed, rank, fetched_at) VALUES (?, ?, ?, ?)
                ON CONFLICT(post_id, feed) DO UPDATE SET rank = excluded.rank, fetched_at = excluded.fetched_at
            ''', (post_id, feed, rank, now))
            n += 1
        conn.commit()
        total += n
        print(f'    {n} posts')

print(f'\nDone: {total} post-feed entries stored in {db_path}')
conn.close()
