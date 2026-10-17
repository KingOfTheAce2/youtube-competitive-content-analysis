"""
Full topic review: what your channel covers vs competitor gaps + search demand.

Parameterized for multi-channel use: point --output at a channel's own
output directory and this derives "my channel" from the database's
is_my_channel flag (set via `youtube_analyzer.py --set-my-channel`) rather
than a hardcoded channel ID - so the same script works for any channel
scope without editing.
"""
import argparse, os, sys, sqlite3, re
from collections import Counter, defaultdict

sys.path.insert(0, '.')
from google_search_analyzer import TOPIC_CATEGORIES, load_niche_config

parser = argparse.ArgumentParser(description="Topic coverage and competitor gap review")
parser.add_argument('--output', default='./output', help='Output directory containing competitive_analysis.db (default: ./output)')
parser.add_argument('--niche-config', default=None,
                     help='Path to a niche config YAML - if given, topic/keyword lists below are '
                          'derived from it instead of the built-in expat-tax defaults (needed for '
                          'a second channel in a different niche, e.g. private/niche_config_legalwriter.yaml)')
args = parser.parse_args()

_niche_terms = None
if args.niche_config:
    if not load_niche_config(args.niche_config):
        print(f"Warning: {args.niche_config} not found, falling back to built-in expat-tax topic lists.")
    else:
        _niche_terms = sorted(set(
            TOPIC_CATEGORIES.get('tax_terms', [])
            + TOPIC_CATEGORIES.get('visa_types', [])
            + TOPIC_CATEGORIES.get('countries', [])
        ))

# Off-niche channels to leave out of the gap list: gap_exclude_channels in my_channels.yaml (gitignored)
try:
    import yaml
    with open('my_channels.yaml', encoding='utf-8') as f:
        GAP_EXCLUDE = (yaml.safe_load(f) or {}).get('gap_exclude_channels') or []
except FileNotFoundError:
    GAP_EXCLUDE = []

DB = os.path.join(args.output, 'competitive_analysis.db')
conn = sqlite3.connect(DB)

my_channel_row = conn.execute(
    "SELECT channel_id, title FROM channels WHERE is_my_channel = 1 LIMIT 1"
).fetchone()
if not my_channel_row:
    print(f"No channel marked is_my_channel=1 in {DB}.")
    print("Run: python youtube_analyzer.py --output "
          f"{args.output} --set-my-channel @YourChannel")
    sys.exit(1)

MY_CHANNEL_ID, MY_CHANNEL_TITLE = my_channel_row

# ── 1. All my channel's titles ────────────────────────────────────────────────
my_rows = conn.execute(
    "SELECT title, view_count, publish_date FROM videos "
    "WHERE channel_id=? ORDER BY publish_date DESC",
    (MY_CHANNEL_ID,)
).fetchall()

print(f"=== {MY_CHANNEL_TITLE.upper()}: ALL {len(my_rows)} VIDEOS ===")
for title, views, pub in my_rows:
    print(f"  {str(pub)[:10]} | {(views or 0):>6,} | {title[:85]}")

# ── 2. Extract topic keywords from my channel's titles ───────────────────────
my_titles_text = ' '.join(t[0].lower() for t in my_rows)
# Key topic phrases already covered - built-in expat-tax defaults, overridden
# by --niche-config if one was loaded above.
COVERED_CHECKS = _niche_terms or [
    'feie', 'foreign earned income', 'foreign tax credit', 'ftc',
    'exit tax', 'fbar', 'gilti', 'cfc',
    'georgia', 'dubai', 'uae', 'spain', 'portugal', 'malaysia', 'turkey',
    'ireland', 'netherlands', 'italy', 'cyprus', 'romania', 'serbia',
    'north macedonia', 'madeira', 'canary', 'svalbard', 'andorra',
    'thailand', 'poland', 'russia', 'hong kong', 'singapore', 'germany',
    'france', 'brazil', 'greece', 'switzerland', 'austria', 'hungary',
    'golden visa', 'digital nomad', 'beckham', 'nhr', 'territorial',
    'capital gains', 'wealth tax', 'second passport', 'citizenship',
    'transfer pricing', 'retirement', 'retire', 'cost of living',
    'residence permit', 'residency', 'tax residency', '183',
    'free zone', 'banking', 'company setup', 'incorporation',
]

print("\n=== TOPIC COVERAGE CHECK ===")
covered = []
not_covered = []
for topic in COVERED_CHECKS:
    if topic in my_titles_text:
        covered.append(topic)
    else:
        not_covered.append(topic)

print("COVERED in titles:")
for t in covered:
    print(f"  [x] {t}")
print("\nNOT covered in titles:")
for t in not_covered:
    print(f"  [ ] {t}")

# ── 3. Top competitor videos NOT in my channel's topic space ─────────────────
comp_rows = conn.execute("""
    SELECT c.title, v.title, v.view_count, v.publish_date
    FROM videos v JOIN channels c ON v.channel_id=c.channel_id
    WHERE v.channel_id != ?
""" + "".join("      AND c.title NOT LIKE ?\n" for _ in GAP_EXCLUDE) + """
    ORDER BY v.view_count DESC
    LIMIT 60
""", (MY_CHANNEL_ID, *[f'%{t}%' for t in GAP_EXCLUDE])).fetchall()

print("\n=== TOP NICHE COMPETITOR VIDEOS ===")
for ch, title, views, pub in comp_rows:
    print(f"  {(views or 0):>9,} | [{ch[:22]}] {title[:70]}")

# ── 4. Topics competitors cover a lot that my channel hasn't ─────────────────
# Count keyword frequency across competitor titles weighted by views
topic_demand: Counter = Counter()
KEYWORDS = _niche_terms or [
    'feie', 'foreign earned income', 'foreign tax credit',
    'exit tax', 'fbar', 'gilti', 'cfc', 'pfic',
    'andorra', 'singapore', 'germany', 'france', 'austria', 'switzerland',
    'hong kong', 'colombia', 'panama', 'paraguay', 'costa rica',
    'golden visa', 'citizenship by investment', 'second passport',
    'digital nomad visa', 'passive income', 'offshore company',
    'capital gains', 'wealth tax', 'inheritance tax',
    'territorial tax', 'worldwide tax',
    'free zone', 'company setup', 'incorporation',
    'banking abroad', 'crypto tax',
    'us expat', 'american expat', 'uk expat',
    'retire abroad', 'retirement',
]

all_comp = conn.execute("""
    SELECT v.title, v.view_count
    FROM videos v JOIN channels c ON v.channel_id=c.channel_id
    WHERE v.channel_id != ?
""", (MY_CHANNEL_ID,)).fetchall()

for title, views in all_comp:
    tl = title.lower()
    w = max(1, views or 1)
    for kw in KEYWORDS:
        if kw in tl:
            topic_demand[kw] += w

print("\n=== COMPETITOR KEYWORD DEMAND (view-weighted, excl. your channel) ===")
for kw, score in topic_demand.most_common(40):
    in_my = '[x]' if kw in my_titles_text else '[ ]'
    print(f"  {in_my} {score:>10,}  {kw}")

# ── 5. My channel's top performers ───────────────────────────────────────────
print(f"\n=== YOUR TOP 20 VIDEOS BY VIEWS ===")
top_mine = conn.execute(
    "SELECT title, view_count, publish_date FROM videos "
    "WHERE channel_id=? "
    "ORDER BY view_count DESC LIMIT 20",
    (MY_CHANNEL_ID,)
).fetchall()
for title, views, pub in top_mine:
    print(f"  {(views or 0):>6,} | {str(pub)[:10]} | {title[:85]}")

conn.close()
