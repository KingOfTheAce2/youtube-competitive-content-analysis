#!/usr/bin/env python3
"""
Transcript Fetcher — YouTube Competitive Content Analysis
Fetches YouTube auto-captions for tracked channels, stores them in SQLite,
and surfaces keyword/topic analysis to enrich competitive insights.

Usage:
  # Fetch transcripts for top N videos per channel (default top 20 by views)
  python transcript_fetcher.py --fetch --top-n 20

  # Fetch only for specific channels
  python transcript_fetcher.py --fetch --channels CHANNEL_A CHANNEL_B

  # Analyse stored transcripts: keyword frequency, topic gaps
  python transcript_fetcher.py --analyze

  # Search transcript content
  python transcript_fetcher.py --search "free zone" --search "beckham law"

  # Show transcript for a single video
  python transcript_fetcher.py --video <video_id>
"""

import argparse
import glob
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict

PYTHONIOENCODING = "utf-8"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OUTPUT_DIR = "./output"
TRANSCRIPT_DB = os.path.join(OUTPUT_DIR, "transcripts.db")

# Stop words — kept minimal so tax/finance terms survive
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "was", "are", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "that", "this", "these", "those",
    "it", "its", "i", "you", "we", "they", "he", "she", "me", "us", "them",
    "my", "your", "our", "their", "if", "so", "as", "up", "out", "about",
    "into", "than", "then", "when", "where", "which", "who", "what", "how",
    "not", "no", "all", "just", "can", "also", "more", "some", "there",
    "like", "very", "really", "going", "get", "got", "going", "make",
    "know", "one", "two", "three", "now", "here", "s", "re", "ve", "ll",
    "um", "uh", "okay", "right", "actually", "basically",
}

FINANCE_BIGRAMS = {
    "transfer pricing", "tax haven", "free zone", "golden visa", "digital nomad",
    "capital gains", "wealth tax", "income tax", "corporate tax", "tax rate",
    "tax residency", "tax treaty", "double taxation", "beckham law", "nhr regime",
    "real estate", "holding company", "substance requirements", "arm's length",
    "oecd guidelines", "vat registration", "tax compliance", "tax planning",
    "offshore company", "nominee director",
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def init_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
            video_id    TEXT PRIMARY KEY,
            channel     TEXT,
            title       TEXT,
            view_count  INTEGER,
            language    TEXT,
            is_auto     INTEGER,
            full_text   TEXT,
            word_count  INTEGER,
            fetched_at  TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fetch_errors (
            video_id  TEXT PRIMARY KEY,
            channel   TEXT,
            title     TEXT,
            reason    TEXT,
            tried_at  TEXT
        )
    """)
    conn.commit()
    return conn


def already_fetched(conn: sqlite3.Connection, video_id: str) -> bool:
    r = conn.execute("SELECT 1 FROM transcripts WHERE video_id=?", (video_id,)).fetchone()
    if r:
        return True
    r = conn.execute("SELECT 1 FROM fetch_errors WHERE video_id=?", (video_id,)).fetchone()
    return bool(r)


# Channels that always get processed first within a daily batch.
# Everything else follows alphabetically — no channel is ever excluded.
def _private_config() -> dict:
    """Read my_channels.yaml (git-ignored): priority_channels, my_channel."""
    try:
        import yaml
        with open("my_channels.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (ImportError, OSError):
        return {}


_PRIVATE = _private_config()
PRIORITY_CHANNELS = list(_PRIVATE.get("priority_channels") or [])
MY_CHANNEL_NAME = str(_PRIVATE.get("my_channel") or "").lstrip("@").lower()


# ---------------------------------------------------------------------------
# Source — iterate channel DBs
# ---------------------------------------------------------------------------

def iter_channel_dbs(filter_channels: list[str] | None = None):
    """
    Yield (channel_name, db_path) for every channel output directory.
    Priority channels (priority_channels in my_channels.yaml) come first; all others
    follow alphabetically. filter_channels narrows the set but never
    re-orders priority.
    """
    pattern = os.path.join(OUTPUT_DIR, "*/data.db")
    all_paths = {
        os.path.basename(os.path.dirname(p)): p
        for p in glob.glob(pattern)
    }

    ordered: list[str] = []
    # Priority first
    for ch in PRIORITY_CHANNELS:
        if ch in all_paths:
            ordered.append(ch)
    # Then the rest, alphabetically
    for ch in sorted(all_paths):
        if ch not in ordered:
            ordered.append(ch)

    for channel in ordered:
        if filter_channels and channel not in filter_channels:
            continue
        yield channel, all_paths[channel]


def get_top_videos(db_path: str, top_n: int, min_views: int = 100) -> list[dict]:
    """Return top-N videos by view_count, excluding Shorts (< 65 s)."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT video_id, title, view_count
        FROM   videos
        WHERE  view_count >= ?
          AND  (duration_seconds IS NULL OR duration_seconds >= 65)
        ORDER  BY view_count DESC
        LIMIT  ?
    """, (min_views, top_n)).fetchall()
    conn.close()
    return [{"video_id": r[0], "title": r[1], "view_count": r[2]} for r in rows]


# ---------------------------------------------------------------------------
# Fetch transcripts
# ---------------------------------------------------------------------------

def _build_api(cookies_path: str | None = None):
    """Build a YouTubeTranscriptApi instance, optionally using a cookies file."""
    from youtube_transcript_api import YouTubeTranscriptApi
    if cookies_path:
        import requests
        session = requests.Session()
        try:
            import http.cookiejar
            cj = http.cookiejar.MozillaCookieJar(cookies_path)
            cj.load(ignore_discard=True, ignore_expires=True)
            session.cookies = cj  # type: ignore[assignment]
        except Exception as e:
            print(f"  ⚠  Could not load cookies file: {e}")
        return YouTubeTranscriptApi(http_client=session)
    return YouTubeTranscriptApi()


def fetch_transcript(video_id: str, api=None) -> tuple[str, str, bool]:
    """
    Returns (full_text, language_code, is_auto).
    Raises on failure — caller handles.
    """
    from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled

    if api is None:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()

    # Try English auto-generated first, then any English, then any language
    preferred = ["en", "en-US", "en-GB"]
    transcript_list = api.list(video_id)

    transcript = None
    is_auto = False

    # Try manual English
    for lang in preferred:
        try:
            transcript = transcript_list.find_manually_created_transcript([lang])
            is_auto = False
            break
        except Exception:
            pass

    # Try auto-generated English
    if transcript is None:
        for lang in preferred:
            try:
                transcript = transcript_list.find_generated_transcript([lang])
                is_auto = True
                break
            except Exception:
                pass

    # Fall back to first available, translate if needed
    if transcript is None:
        available = list(transcript_list)
        if not available:
            raise NoTranscriptFound(video_id, preferred, transcript_list)
        transcript = available[0]
        is_auto = transcript.is_generated
        if transcript.language_code not in ("en", "en-US", "en-GB"):
            try:
                transcript = transcript.translate("en")
                is_auto = True
            except Exception:
                pass  # use original language

    fetched = transcript.fetch()
    snippets = list(fetched)
    lang_code = transcript.language_code
    full_text = " ".join(s.text for s in snippets)
    # Clean up HTML entities and tags from auto-captions
    full_text = re.sub(r"<[^>]+>", " ", full_text)
    full_text = full_text.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
    full_text = re.sub(r"\s+", " ", full_text).strip()
    return full_text, lang_code, is_auto


def run_fetch(top_n: int, filter_channels: list[str] | None, min_views: int,
              delay: float, cookies_path: str | None = None, retries: int = 2,
              daily_limit: int | None = None):
    """
    Fetch transcripts across all channels, stopping once daily_limit successes
    are reached. On the next run, cached videos are skipped automatically so
    progress resumes from where it left off.
    """
    conn = init_db(TRANSCRIPT_DB)

    total_ok = 0
    total_skip = 0
    total_err = 0
    quota_hit = False

    # Build one shared API instance for the whole run
    api = _build_api(cookies_path)

    for channel, db_path in iter_channel_dbs(filter_channels):
        if quota_hit:
            break

        videos = get_top_videos(db_path, top_n, min_views)
        if not videos:
            continue

        new_for_channel = [v for v in videos if not already_fetched(conn, v["video_id"])]
        if not new_for_channel:
            print(f"  ⏭  {channel}: all top-{top_n} already fetched")
            continue

        remaining_quota = (daily_limit - total_ok) if daily_limit else len(new_for_channel)
        batch = new_for_channel[:remaining_quota]

        print(f"\n📥 {channel} — fetching {len(batch)} transcripts "
              f"({len(videos) - len(new_for_channel)} cached, "
              f"{len(new_for_channel) - len(batch)} deferred to next run)")

        for v in batch:
            vid = v["video_id"]
            title = v["title"][:80]
            last_err = None
            ip_blocked = False
            for attempt in range(retries + 1):
                try:
                    full_text, lang, is_auto = fetch_transcript(vid, api=api)
                    word_count = len(full_text.split())
                    conn.execute("""
                        INSERT OR REPLACE INTO transcripts
                        (video_id, channel, title, view_count, language, is_auto,
                         full_text, word_count, fetched_at)
                        VALUES (?,?,?,?,?,?,?,?,datetime('now'))
                    """, (vid, channel, v["title"], v["view_count"], lang,
                          1 if is_auto else 0, full_text, word_count))
                    conn.commit()
                    flag = "🤖" if is_auto else "📝"
                    print(f"  ✅ {flag} [{lang}] {title[:60]} ({word_count:,} words)")
                    total_ok += 1
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    msg = str(e).lower()
                    # IP block — no point retrying, stop the entire run
                    if "blocking" in msg or ("ip" in msg and "block" in msg):
                        ip_blocked = True
                        break
                    # Permanent errors (captions disabled, private, etc.) — skip, don't retry
                    if any(x in msg for x in ["disabled", "no transcript", "private", "unavailable"]):
                        break
                    if attempt < retries:
                        backoff = delay * (2 ** attempt) + 2
                        print(f"  ⏳ Retry {attempt+1}/{retries} for {title[:40]} (wait {backoff:.0f}s)…")
                        time.sleep(backoff)

            if last_err is not None:
                reason = str(last_err)[:200]
                conn.execute("""
                    INSERT OR REPLACE INTO fetch_errors
                    (video_id, channel, title, reason, tried_at)
                    VALUES (?,?,?,?,datetime('now'))
                """, (vid, channel, v["title"], reason))
                conn.commit()
                if ip_blocked:
                    print(f"\n  🚫 IP blocked by YouTube after {total_ok} fetches.")
                    print(f"     Add --cookies cookies.txt to bypass, or run again tomorrow.")
                    print(f"     (This video and all remaining are queued for next run.)")
                    quota_hit = True  # stop all further processing
                    break
                print(f"  ❌ {title[:50]}")
                total_err += 1

            time.sleep(delay)

            if daily_limit and total_ok >= daily_limit:
                quota_hit = True
                print(f"\n  🛑 Daily limit of {daily_limit} reached — run again tomorrow to continue.")
                break

    conn.close()
    print(f"\n{'='*60}")
    print(f"  Fetched: {total_ok}  |  Errors: {total_err}  |  Skipped: {total_skip}")
    if daily_limit:
        _print_progress(daily_limit)
    print(f"  Stored in: {TRANSCRIPT_DB}")


def _print_progress(daily_limit: int):
    """Print a quick summary of how many remain to be fetched."""
    conn = sqlite3.connect(TRANSCRIPT_DB)
    done = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
    errors = conn.execute("SELECT COUNT(*) FROM fetch_errors").fetchone()[0]
    conn.close()

    # Count total available from all channel DBs
    total_available = 0
    for _, db_path in iter_channel_dbs(None):
        try:
            c = sqlite3.connect(db_path)
            n = c.execute(
                "SELECT COUNT(*) FROM videos WHERE view_count >= 100 AND (duration_seconds IS NULL OR duration_seconds >= 65)"
            ).fetchone()[0]
            total_available += n
            c.close()
        except Exception:
            pass

    remaining = max(0, total_available - done - errors)
    days_left = -(-remaining // daily_limit)  # ceiling division
    print(f"  Progress: {done} done / {total_available} available — "
          f"~{remaining} remaining (~{days_left} days at {daily_limit}/day)")


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def extract_keywords(text: str, top_n: int = 30) -> list[tuple[str, int]]:
    """Return (phrase, count) list — bigrams scored against finance terms first."""
    text_lower = text.lower()
    counts: Counter = Counter()

    # Score known finance bigrams first
    for bigram in FINANCE_BIGRAMS:
        c = text_lower.count(bigram)
        if c:
            counts[bigram] += c * 2  # weight bigrams

    # Unigrams
    words = re.findall(r"\b[a-z]{3,}\b", text_lower)
    for w in words:
        if w not in STOP_WORDS:
            counts[w] += 1

    # Generic bigrams
    for i in range(len(words) - 1):
        bg = f"{words[i]} {words[i+1]}"
        if words[i] not in STOP_WORDS and words[i+1] not in STOP_WORDS:
            counts[bg] += 1

    return counts.most_common(top_n)


def run_analyze(filter_channels: list[str] | None, top_n: int):
    conn = init_db(TRANSCRIPT_DB)

    # Per-channel keyword profiles
    channel_keywords: dict[str, Counter] = defaultdict(Counter)
    channel_meta: dict[str, dict] = {}

    query = "SELECT channel, title, view_count, full_text, word_count FROM transcripts"
    params: list = []
    if filter_channels:
        placeholders = ",".join("?" * len(filter_channels))
        query += f" WHERE channel IN ({placeholders})"
        params = filter_channels

    rows = conn.execute(query, params).fetchall()
    if not rows:
        print("No transcripts stored yet. Run --fetch first.")
        return

    for channel, title, views, full_text, wc in rows:
        kws = extract_keywords(full_text or "", top_n=50)
        for kw, cnt in kws:
            # Weight by view count so viral videos count more
            channel_keywords[channel][kw] += cnt * (1 + views / 10000)
        if channel not in channel_meta:
            channel_meta[channel] = {"videos": 0, "total_words": 0}
        channel_meta[channel]["videos"] += 1
        channel_meta[channel]["total_words"] += wc or 0

    # Summary per channel
    print("\n" + "=" * 70)
    print("  TRANSCRIPT KEYWORD ANALYSIS")
    print("=" * 70)

    for channel in sorted(channel_keywords):
        meta = channel_meta.get(channel, {})
        print(f"\n📺 {channel}  "
              f"({meta.get('videos', 0)} transcripts, "
              f"{meta.get('total_words', 0):,} total words)")
        top = channel_keywords[channel].most_common(top_n)
        for kw, score in top:
            bar = "█" * min(int(score / max(1, top[0][1]) * 20), 20)
            print(f"  {bar:<20} {kw}")

    # Cross-channel gap: competitor topics your channel doesn't use
    my_channel = None
    for ch in channel_keywords:
        if MY_CHANNEL_NAME and MY_CHANNEL_NAME in ch.lower():
            my_channel = ch
            break

    if my_channel and filter_channels is None:
        print("\n" + "=" * 70)
        print(f"  TOPIC GAPS: What competitors say that {my_channel} doesn't")
        print("=" * 70)

        my_kws = {kw for kw, _ in channel_keywords[my_channel].most_common(100)}

        for channel in sorted(channel_keywords):
            if channel == my_channel:
                continue
            their_top = channel_keywords[channel].most_common(60)
            gaps = [(kw, sc) for kw, sc in their_top if kw not in my_kws][:15]
            if gaps:
                print(f"\n  vs {channel}:")
                for kw, sc in gaps:
                    print(f"    • {kw}")

    conn.close()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def run_search(terms: list[str], filter_channels: list[str] | None, context_chars: int = 150):
    conn = init_db(TRANSCRIPT_DB)

    query = "SELECT channel, title, view_count, video_id, full_text FROM transcripts"
    params: list = []
    if filter_channels:
        placeholders = ",".join("?" * len(filter_channels))
        query += f" WHERE channel IN ({placeholders})"
        params = list(filter_channels)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    pattern = re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)

    print(f"\n🔍 Searching {len(rows)} transcripts for: {terms}\n")

    hits = []
    for channel, title, views, vid, full_text in rows:
        if not full_text:
            continue
        matches = list(pattern.finditer(full_text))
        if matches:
            hits.append((views, channel, title, vid, matches, full_text))

    hits.sort(reverse=True)  # highest views first

    for views, channel, title, vid, matches, full_text in hits:
        print(f"  [{channel}] {title[:70]}")
        print(f"  Views: {views:,} | https://youtube.com/watch?v={vid}")
        for m in matches[:3]:
            start = max(0, m.start() - context_chars // 2)
            end = min(len(full_text), m.end() + context_chars // 2)
            snippet = full_text[start:end].replace("\n", " ")
            print(f"    …{snippet}…")
        print()

    print(f"Found {len(hits)} videos matching [{', '.join(terms)}]")


# ---------------------------------------------------------------------------
# Single video viewer
# ---------------------------------------------------------------------------

def run_show_video(video_id: str):
    conn = init_db(TRANSCRIPT_DB)
    row = conn.execute(
        "SELECT channel, title, view_count, language, is_auto, full_text, word_count "
        "FROM transcripts WHERE video_id=?", (video_id,)
    ).fetchone()
    conn.close()

    if not row:
        print(f"No transcript stored for video_id={video_id}. Run --fetch first.")
        return

    channel, title, views, lang, is_auto, full_text, wc = row
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"  Channel: {channel} | Views: {views:,} | Lang: {lang} | "
          f"{'Auto' if is_auto else 'Manual'} | {wc:,} words")
    print("=" * 70)
    print(full_text or "(empty)")
    print()
    print("Top keywords:")
    for kw, cnt in extract_keywords(full_text or "", top_n=20):
        print(f"  {cnt:>4}x  {kw}")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def run_status():
    conn = init_db(TRANSCRIPT_DB)
    rows = conn.execute(
        "SELECT channel, COUNT(*), SUM(word_count) FROM transcripts GROUP BY channel ORDER BY channel"
    ).fetchall()
    errors = conn.execute(
        "SELECT channel, COUNT(*) FROM fetch_errors GROUP BY channel ORDER BY channel"
    ).fetchall()
    conn.close()

    print("\n📊 Transcript Store Status")
    print(f"{'Channel':<35} {'Transcripts':>12} {'Total Words':>12}")
    print("-" * 60)
    total_vids = 0
    total_words = 0
    for ch, cnt, wds in rows:
        print(f"  {ch:<33} {cnt:>12,} {(wds or 0):>12,}")
        total_vids += cnt
        total_words += wds or 0
    print("-" * 60)
    print(f"  {'TOTAL':<33} {total_vids:>12,} {total_words:>12,}")

    if errors:
        print("\n⚠  Fetch errors by channel:")
        for ch, cnt in errors:
            print(f"  {ch}: {cnt} errors")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch & analyse YouTube transcripts for competitive insights",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--fetch", action="store_true",
                        help="Fetch transcripts from YouTube")
    parser.add_argument("--analyze", action="store_true",
                        help="Analyse stored transcripts (keywords, topic gaps)")
    parser.add_argument("--search", nargs="+", metavar="TERM",
                        help="Search transcript text for terms")
    parser.add_argument("--video", metavar="VIDEO_ID",
                        help="Show full transcript for a video ID")
    parser.add_argument("--status", action="store_true",
                        help="Show transcript store stats")
    parser.add_argument("--channels", nargs="+", metavar="NAME",
                        help="Limit to these channel names (folder names under output/)")
    parser.add_argument("--top-n", dest="top_n", type=int, default=500,
                        help="Top N videos per channel to fetch, sorted by views (default: 500)")
    parser.add_argument("--min-views", dest="min_views", type=int, default=100,
                        help="Skip videos below this view count (default: 100)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Seconds between requests (default: 1.5)")
    parser.add_argument("--cookies", metavar="FILE",
                        help="Path to Netscape-format cookies.txt (export from browser via "
                             "'Get cookies.txt LOCALLY' extension). Bypasses YouTube IP blocks.")
    parser.add_argument("--retry", type=int, default=1,
                        help="Retry attempts on transient errors (default: 1, IP blocks always abort immediately)")
    parser.add_argument("--daily-limit", dest="daily_limit", type=int, default=None,
                        help="Max transcripts to fetch in this run (e.g. 25). "
                             "Re-run daily — cached videos are skipped automatically.")
    parser.add_argument("--clear-errors", dest="clear_errors", action="store_true",
                        help="Clear IP-block errors so they are retried on the next --fetch run")

    args = parser.parse_args()

    if not any([args.fetch, args.analyze, args.search, args.video, args.status, args.clear_errors]):
        parser.print_help()
        return

    if args.clear_errors:
        conn = init_db(TRANSCRIPT_DB)
        n = conn.execute(
            "DELETE FROM fetch_errors WHERE reason LIKE '%blocking%' OR reason LIKE '%IP%'"
        ).rowcount
        conn.commit()
        conn.close()
        print(f"  Cleared {n} retryable IP-block errors — they will be retried on next --fetch run.")

    if args.status:
        run_status()

    if args.fetch:
        run_fetch(args.top_n, args.channels, args.min_views, args.delay,
                  cookies_path=args.cookies, retries=args.retry,
                  daily_limit=args.daily_limit)

    if args.analyze:
        run_analyze(args.channels, top_n=25)

    if args.search:
        run_search(args.search, args.channels)

    if args.video:
        run_show_video(args.video)


if __name__ == "__main__":
    main()
