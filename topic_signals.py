"""
Rank video topic ideas by combining three demand signals against what you already cover.

Signals (all read from output/competitive_analysis.db):
  - YouTube comments on competitor channels (mentions per 1,000 comments, averaged per channel,
    so one huge channel does not drown the others; question comments count double)
  - Comments on your own channel (your audience asking directly, weighted highest)
  - Reddit posts from reddit_topic_scanner.py (weighted by rank in the top-of-month/year feeds)
Coverage: your own videos and competitor videos whose title mentions the topic, with median views.

    python topic_signals.py                 # prints and writes output/topic_signals.md
    python topic_signals.py --top 50 --min-demand 3

Run `youtube_analyzer.py --sync-comments` and `reddit_topic_scanner.py` first to refresh the inputs.
Topics are matched by keyword (countries from niche_config.yaml plus the concept list below), so
treat the ranking as a shortlist to read, not a verdict.
"""
import argparse, os, re, sqlite3, statistics as st, sys
from collections import defaultdict

import yaml

sys.path.insert(0, '.')
from youtube_analyzer import get_competitive_db_path

parser = argparse.ArgumentParser(description='Rank video topics from comments and Reddit')
parser.add_argument('--output', default='./output')
parser.add_argument('--top', type=int, default=40)
parser.add_argument('--min-demand', type=float, default=2.0, help='Hide topics below this demand score')
args = parser.parse_args()

CONCEPTS = {
    'box 3': r'\bbox ?3\b',
    '30% ruling': r'\b(30|27) ?(%|percent) ruling\b|\b30 ?% facility\b',
    'exit tax': r'\bexit tax\b',
    'departure tax': r'\bdeparture tax\b',
    'wealth tax': r'\bwealth tax\b|\bsolidarity tax\b',
    'unrealized gains tax': r'unrealized (capital )?gains|unrealised (capital )?gains',
    'capital gains tax': r'\bcapital gains?\b',
    'fbar / fatca': r'\bfbar\b|\bfatca\b',
    'us expat taxes': r'\bfeie\b|foreign earned income|\birs\b|us citizens? abroad|renounc',
    'tax residency certificate': r'tax residen(cy|t) certificate|\btrc\b|residency certificate',
    '183 day rule': r'\b183\b|\b180 days\b|day count',
    'double taxation': r'double tax|dual tax|tax treat(y|ies)',
    'non-dom': r'\bnon-?dom',
    'golden visa': r'golden visa',
    'digital nomad visa': r'digital nomad|nomad visa',
    'citizenship by descent': r'by descent|ancestry|ancestor',
    'citizenship by investment': r'citizenship by investment|second passport|\bcbi\b',
    'tax residency': r'tax residen',
    'foreign bank account': r'bank account|neobank|\bwise\b|revolut',
    'crypto tax': r'crypto',
    'pension / retirement': r'pension|retire|social security|annuit',
    'us llc': r'\bllc\b',
    'company / holding structure': r'\bholding\b|offshore compan|\bbv\b|free zone|incorporat',
    'moving checklist': r'checklist|first steps|moving to|relocat',
    'inheritance / gift tax': r'inherit|gift tax|estate tax',
    'property tax': r'property tax|buying (a )?(house|property)|real estate',
}

# Countries from niche_config.yaml, with aliases for the awkward ones.
with open('niche_config.yaml', encoding='utf-8') as f:
    niche = yaml.safe_load(f)
COUNTRIES = {}
for c in niche['topic_categories']['countries']:
    COUNTRIES[c] = r'\b' + re.escape(c) + r'\b'
COUNTRIES['united kingdom'] = r'\bunited kingdom\b|\buk\b|\bbritain\b|\bhmrc\b'
for generic in ('united states', 'uk'):  # too broad to be a video topic; "us expat taxes" covers the US case
    COUNTRIES.pop(generic, None)
COUNTRIES['united arab emirates'] = r'\buae\b|\bdubai\b|abu dhabi|united arab emirates'
COUNTRIES['netherlands'] = r'\bnetherlands\b|\bdutch\b|\bholland\b|\bamsterdam\b|\bbelastingdienst\b'
COUNTRIES['czech republic'] = r'\bczech'
# A post or comment only counts if it is about tax, residency or money rules, not lifestyle chat.
RELEVANT = re.compile(
    r'tax|visa|residen|citizen|passport|permit|ruling|irs|hmrc|ato|fbar|pension|capital gain|'
    r'inherit|gift|exemption|golden|income|dividend|invest|llc|incorporat|accountant|advisor|adviser|'
    r'lawyer|treaty|box ?3|bv|salary|deduct|filing|return|reporting|compliance|bank account', re.I)
TOPICS = {**{k: re.compile(v, re.I) for k, v in CONCEPTS.items()},
          **{k: re.compile(v, re.I) for k, v in COUNTRIES.items()}}

db = sqlite3.connect(get_competitive_db_path(args.output))
db.row_factory = sqlite3.Row

chan = {r['channel_id']: (r['title'], r['is_my_channel']) for r in db.execute('SELECT channel_id, title, is_my_channel FROM channels')}
comments = db.execute('SELECT channel_id, text, like_count FROM comments').fetchall()
videos = db.execute('SELECT channel_id, title, view_count FROM videos WHERE COALESCE(is_short,0)=0').fetchall()
try:
    posts = db.execute('''
        SELECT p.post_id, p.subreddit, p.title, p.body, p.url, r.feed, r.rank
        FROM reddit_posts p JOIN reddit_post_ranks r USING (post_id)''').fetchall()
except sqlite3.OperationalError:
    posts = []

per_chan = defaultdict(int)
for c in comments:
    per_chan[c['channel_id']] += 1

demand = defaultdict(lambda: {'comp': 0.0, 'comp_q': 0.0, 'own': 0, 'own_q': 0, 'reddit': 0.0, 'samples': []})

for c in comments:
    title, mine = chan.get(c['channel_id'], ('?', 0))
    text = c['text'] or ''
    if not RELEVANT.search(text):
        continue
    q = '?' in text
    for name, rx in TOPICS.items():
        if rx.search(text):
            d = demand[name]
            if mine:
                d['own'] += 1
                d['own_q'] += q
            else:
                scale = 1000.0 / per_chan[c['channel_id']] / max(1, sum(1 for ch in per_chan if not chan.get(ch, ('', 0))[1]))
                d['comp'] += scale
                d['comp_q'] += scale * q
            if q and len(text) > 40:
                d['samples'].append((c['like_count'] or 0, f'[{title}] {text[:170]}'))

seen_post_topic = defaultdict(set)
for p in posts:
    w = (3 if p['rank'] <= 10 else 2 if p['rank'] <= 30 else 1) * (1.5 if p['feed'] == 'top_month' else 1)
    text = f"{p['title']} {p['body'] or ''}"
    if not RELEVANT.search(text):
        continue
    for name, rx in TOPICS.items():
        if rx.search(text):
            demand[name]['reddit'] += w
            if p['post_id'] not in seen_post_topic[name]:
                seen_post_topic[name].add(p['post_id'])
                demand[name]['samples'].append((60 - p['rank'], f"[r/{p['subreddit']}] {p['title'][:170]}"))

coverage = defaultdict(lambda: {'own': [], 'comp': []})
for v in videos:
    mine = chan.get(v['channel_id'], ('', 0))[1]
    for name, rx in TOPICS.items():
        if rx.search(v['title'] or ''):
            coverage[name]['own' if mine else 'comp'].append(v['view_count'] or 0)

rows = []
for name, d in demand.items():
    score = d['comp'] + d['comp_q'] + d['reddit'] * 2 + d['own'] * 5 + d['own_q'] * 5
    if score < args.min_demand:
        continue
    cov = coverage[name]
    own_n = len(cov['own'])
    opp = score / (1 + 2 * own_n)
    rows.append((opp, score, name, d, cov))
rows.sort(key=lambda r: -r[0])


def med(x):
    return int(st.median(x)) if x else 0


lines = ['# Topic signals', '',
         'Demand score = competitor mentions per 1,000 comments (questions count double) + 2 x Reddit rank weight '
         '+ 5 x each own-channel comment (questions count double again). Opportunity = demand / (1 + 2 x your videos on it).',
         f'Inputs: {len(comments)} comments, {len(set(p["post_id"] for p in posts))} Reddit posts, {len(videos)} videos.', '',
         '| Topic | Opportunity | Demand | Reddit | Own comments | Your videos (med views) | Competitor videos (med views) |',
         '|---|---|---|---|---|---|---|']
for opp, score, name, d, cov in rows[:args.top]:
    lines.append(f"| {name} | {opp:.1f} | {score:.1f} | {d['reddit']:.0f} | {d['own']} | "
                 f"{len(cov['own'])} ({med(cov['own'])}) | {len(cov['comp'])} ({med(cov['comp'])}) |")
lines += ['', '## What people actually ask, top 12 topics', '']
for opp, score, name, d, cov in rows[:12]:
    lines.append(f'### {name}')
    for _, s in sorted(d['samples'], reverse=True)[:5]:
        lines.append(f'- {s}')
    lines.append('')

report = '\n'.join(lines)
out = os.path.join(args.output, 'topic_signals.md')
with open(out, 'w', encoding='utf-8') as f:
    f.write(report)
try:
    print(report)
except UnicodeEncodeError:
    print(report.encode('ascii', 'ignore').decode())
print(f'\nWritten to {out}')
