"""
Pull detailed owner-only analytics for your own channel (YouTube Analytics API, OAuth).

First run opens a browser once to sign in as the channel owner; the token is cached in
youtube_oauth_token.json. Needs client_secret.json (OAuth "Desktop app" client) next to this file.

    python my_channel_analytics.py                      # since 2024-10-01 up to 2 days ago
    python my_channel_analytics.py --days 90            # last 90 days only
    python my_channel_analytics.py --no-revenue         # skip monetary scope and revenue columns
    python my_channel_analytics.py --retention-top 25   # retention curves for the 25 most viewed videos

Writes CSVs plus analytics_summary.md to output/analytics/<run date>/. Each report is written as
soon as it finishes, and one failing report does not stop the others.
"""
import argparse, csv, os, sys
from datetime import date, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

HERE = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET = os.path.join(HERE, 'client_secret.json')
TOKEN_FILE = os.path.join(HERE, 'youtube_oauth_token.json')

SCOPE_ANALYTICS = 'https://www.googleapis.com/auth/yt-analytics.readonly'
SCOPE_MONEY = 'https://www.googleapis.com/auth/yt-analytics-monetary.readonly'
SCOPE_YT = 'https://www.googleapis.com/auth/youtube.readonly'

parser = argparse.ArgumentParser(description='Detailed analytics for your own channel')
parser.add_argument('--start', default='2024-10-01', help='Start date YYYY-MM-DD (default: 2024-10-01)')
parser.add_argument('--end', default=None, help='End date YYYY-MM-DD (default: 2 days ago, API lag)')
parser.add_argument('--days', type=int, default=None, help='Last N days; overrides --start')
parser.add_argument('--no-revenue', action='store_true', help='Do not request the monetary scope or revenue metrics')
parser.add_argument('--retention-top', type=int, default=15, help='Retention curves for the top N videos (default: 15)')
parser.add_argument('--output', default='./output/analytics', help='Output base directory')
args = parser.parse_args()

end = date.fromisoformat(args.end) if args.end else date.today() - timedelta(days=2)
start = end - timedelta(days=args.days) if args.days else date.fromisoformat(args.start)
OUT = os.path.join(args.output, date.today().isoformat())
os.makedirs(OUT, exist_ok=True)


def get_credentials(scopes):
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, scopes)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())
            return creds
        except Exception:
            pass  # fall through to a fresh sign-in
    if not os.path.exists(CLIENT_SECRET):
        sys.exit(f'Missing {CLIENT_SECRET}. See the setup steps in the docstring / chat.')
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, scopes)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())
    return creds


scopes = [SCOPE_ANALYTICS, SCOPE_YT] + ([] if args.no_revenue else [SCOPE_MONEY])
creds = get_credentials(scopes)
analytics = build('youtubeAnalytics', 'v2', credentials=creds)
youtube = build('youtube', 'v3', credentials=creds)
have_revenue = not args.no_revenue
REV = 'estimatedRevenue'


def query(dimensions, metrics, sort=None, filters=None, max_results=None):
    """Run one Analytics report; returns (headers, rows). Revenue metric dropped if not permitted."""
    global have_revenue
    ms = list(metrics)
    if not have_revenue and REV in ms:
        ms.remove(REV)
    kw = dict(ids='channel==MINE', startDate=start.isoformat(), endDate=end.isoformat(),
              metrics=','.join(ms))
    if dimensions:
        kw['dimensions'] = dimensions
    if sort:
        kw['sort'] = sort
    if filters:
        kw['filters'] = filters
    if max_results:
        kw['maxResults'] = max_results
    try:
        r = analytics.reports().query(**kw).execute()
    except HttpError as e:
        if have_revenue and REV in ms and e.resp.status in (400, 403):
            print('  revenue metric refused (scope not granted or not monetized); retrying without it')
            have_revenue = False
            return query(dimensions, metrics, sort, filters, max_results)
        raise
    return [h['name'] for h in r.get('columnHeaders', [])], r.get('rows', [])


def write_csv(name, headers, rows):
    path = os.path.join(OUT, name)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
        f.flush()
        os.fsync(f.fileno())
    print(f'  wrote {name} ({len(rows)} rows)')


def run(name, fn):
    print(f'{name} ...')
    try:
        return fn()
    except HttpError as e:
        print(f'  FAILED: {e}')
    except Exception as e:
        print(f'  FAILED: {type(e).__name__}: {e}')
    return None


def video_meta(ids):
    meta = {}
    for i in range(0, len(ids), 50):
        r = youtube.videos().list(part='snippet,contentDetails', id=','.join(ids[i:i + 50])).execute()
        for v in r.get('items', []):
            meta[v['id']] = (v['snippet']['title'], v['snippet']['publishedAt'][:10],
                             v['contentDetails']['duration'])
    return meta


core = ['views', 'estimatedMinutesWatched', 'averageViewDuration', 'averageViewPercentage',
        'subscribersGained', 'subscribersLost', 'likes', 'comments', 'shares', REV]
col = {}  # filled by the per-video report for the summary


def per_video():
    h, rows = query('video', core, sort='-views', max_results=200)
    meta = video_meta([r[0] for r in rows])
    h2 = ['title', 'published', 'duration'] + h
    out = []
    for r in rows:
        t, p, d = meta.get(r[0], ('?', '?', '?'))
        out.append([t, p, d] + r)
    write_csv('per_video.csv', h2, out)
    return h2, out


def simple(name, dims, metrics, **kw):
    def go():
        h, rows = query(dims, metrics, **kw)
        write_csv(name, h, rows)
        return h, rows
    return go


def retention(vid_ids):
    path_rows = []
    for vid in vid_ids:
        try:
            h, rows = query('elapsedVideoTimeRatio', ['audienceWatchRatio', 'relativeRetentionPerformance'],
                            filters=f'video=={vid}')
        except HttpError as e:
            print(f'  retention failed for {vid}: {e}')
            continue
        path_rows += [[vid] + r for r in rows]
    write_csv('retention_curves.csv', ['video_id', 'elapsedVideoTimeRatio', 'audienceWatchRatio',
                                       'relativeRetentionPerformance'], path_rows)


pv = run('Per video', per_video)
by_type = run('Shorts vs long-form vs live', simple(
    'by_content_type.csv', 'creatorContentType',
    ['views', 'estimatedMinutesWatched', 'averageViewDuration', 'subscribersGained', REV]))
run('Traffic sources', simple('traffic_sources.csv', 'insightTrafficSourceType',
                              ['views', 'estimatedMinutesWatched', 'averageViewDuration'], sort='-views'))
run('YouTube search terms', simple('search_terms.csv', 'insightTrafficSourceDetail',
                                   ['views', 'estimatedMinutesWatched'], sort='-views', max_results=25,
                                   filters='insightTrafficSourceType==YT_SEARCH'))
countries = run('Countries', simple('countries.csv', 'country',
                                    ['views', 'estimatedMinutesWatched', 'subscribersGained', REV],
                                    sort='-views', max_results=50))
run('Devices', simple('devices.csv', 'deviceType', ['views', 'estimatedMinutesWatched']))
run('Age and gender', simple('age_gender.csv', 'ageGroup,gender', ['viewerPercentage']))
run('Daily', simple('daily.csv', 'day', ['views', 'estimatedMinutesWatched', 'subscribersGained', REV],
                    sort='day'))
if pv and args.retention_top > 0:
    top_ids = [r[3] for r in pv[1][:args.retention_top]]  # column 3 is the video id
    run('Retention curves', lambda: retention(top_ids))


def summary():
    lines = [f'# Channel analytics {start} to {end}', '']
    if by_type:
        h, rows = by_type
        lines += ['## Content type', '', '| Type | Views | Minutes watched | Subs gained | Revenue | RPM |', '|---|---|---|---|---|---|']
        for r in rows:
            d = dict(zip(h, r))
            rev = d.get(REV)
            rpm = f'{rev / d["views"] * 1000:.2f}' if rev is not None and d['views'] else 'n/a'
            lines.append(f'| {d["creatorContentType"]} | {d["views"]} | {d["estimatedMinutesWatched"]} | '
                         f'{d["subscribersGained"]} | {rev if rev is not None else "n/a"} | {rpm} |')
        lines.append('')
    if pv:
        h, rows = pv
        i = {n: k for k, n in enumerate(h)}
        lines += ['## Top 15 videos by minutes watched', '',
                  '| Title | Views | Avg % viewed | Subs gained | Subs per 1k views |', '|---|---|---|---|---|']
        for r in sorted(rows, key=lambda r: -r[i['estimatedMinutesWatched']])[:15]:
            v = r[i['views']]
            sg = r[i['subscribersGained']]
            lines.append(f'| {r[0][:60]} | {v} | {r[i["averageViewPercentage"]]:.0f}% | {sg} | '
                         f'{sg / v * 1000:.1f} |' if v else f'| {r[0][:60]} | 0 | | | |')
        lines.append('')
    if countries:
        h, rows = countries
        lines += ['## Top 10 countries by views', '', '| Country | Views | Revenue |', '|---|---|---|']
        for r in rows[:10]:
            d = dict(zip(h, r))
            lines.append(f'| {d["country"]} | {d["views"]} | {d.get(REV, "n/a")} |')
    with open(os.path.join(OUT, 'analytics_summary.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('  wrote analytics_summary.md')


run('Summary', summary)
print(f'\nDone. Output in {OUT}')
