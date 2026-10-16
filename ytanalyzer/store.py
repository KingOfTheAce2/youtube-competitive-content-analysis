"""Competitive database, private config, competitor management."""

from .common import *
from .fetch import resolve_channel_id

# =============================================================================
# COMPETITIVE ANALYSIS - DATABASE MIGRATION & CONFIG MANAGEMENT
# =============================================================================

def get_competitive_db_path(output_dir: str = './output') -> str:
    """Get the path to the shared competitive analysis database."""
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, 'competitive_analysis.db')


def migrate_competitive_database(db_path: str) -> None:
    """
    Migrate database schema to support competitive analysis features.
    Safe to run multiple times - only adds missing columns/tables.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check existing columns in channels table
    cursor.execute("PRAGMA table_info(channels)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Create channels table if not exists
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (
        channel_id TEXT PRIMARY KEY, title TEXT, subscriber_count INTEGER,
        video_count INTEGER, view_count INTEGER, fetched_at TEXT
    )''')

    # Add new columns to channels table
    new_columns = [
        ('last_fetched_at', 'TEXT'),
        ('is_my_channel', 'INTEGER DEFAULT 0'),
        ('is_competitor', 'INTEGER DEFAULT 0'),
        ('handle', 'TEXT'),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f'ALTER TABLE channels ADD COLUMN {col_name} {col_type}')
            except sqlite3.OperationalError:
                pass  # Column may already exist

    # Create videos table if not exists
    cursor.execute('''CREATE TABLE IF NOT EXISTS videos (
        video_id TEXT PRIMARY KEY, channel_id TEXT, title TEXT, publish_date TEXT,
        view_count INTEGER, like_count INTEGER, comment_count INTEGER,
        engagement_rate REAL, duration_seconds INTEGER, virality_score REAL,
        title_hook_score INTEGER, is_short INTEGER, is_series INTEGER, is_collab INTEGER,
        estimated_revenue_mid REAL, thumbnail_high TEXT
    )''')

    # Video snapshots for trend tracking
    cursor.execute('''CREATE TABLE IF NOT EXISTS video_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id TEXT NOT NULL,
        snapshot_date TEXT NOT NULL,
        view_count INTEGER,
        like_count INTEGER,
        comment_count INTEGER,
        UNIQUE(video_id, snapshot_date)
    )''')

    # Channel-level snapshots for organic-vs-algorithm growth tracking
    cursor.execute('''CREATE TABLE IF NOT EXISTS channel_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT NOT NULL,
        snapshot_date TEXT NOT NULL,
        subscriber_count INTEGER,
        view_count INTEGER,
        video_count INTEGER,
        UNIQUE(channel_id, snapshot_date)
    )''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_channel_snapshots_channel ON channel_snapshots(channel_id)')

    # Top-level comments on tracked competitor videos (see sync_comments)
    cursor.execute('''CREATE TABLE IF NOT EXISTS comments (
        comment_id TEXT PRIMARY KEY,
        video_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        author TEXT,
        text TEXT,
        like_count INTEGER,
        reply_count INTEGER,
        published_at TEXT,
        fetched_at TEXT
    )''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_video ON comments(video_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_channel ON comments(channel_id)')

    # Competitors table - persistent tracking
    cursor.execute('''CREATE TABLE IF NOT EXISTS competitors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT NOT NULL,
        my_channel_id TEXT NOT NULL,
        relevance_score REAL DEFAULT 0,
        discovery_source TEXT,
        discovered_at TEXT,
        last_synced_at TEXT,
        UNIQUE(channel_id, my_channel_id)
    )''')

    # Topics table
    cursor.execute('''CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_name TEXT NOT NULL UNIQUE,
        topic_keywords TEXT,
        created_at TEXT
    )''')

    # Video-topic mapping
    cursor.execute('''CREATE TABLE IF NOT EXISTS video_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id TEXT NOT NULL,
        topic_id INTEGER NOT NULL,
        confidence REAL DEFAULT 1.0,
        UNIQUE(video_id, topic_id),
        FOREIGN KEY(topic_id) REFERENCES topics(id)
    )''')

    # Topic recommendations
    cursor.execute('''CREATE TABLE IF NOT EXISTS topic_recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        my_channel_id TEXT NOT NULL,
        topic_name TEXT NOT NULL,
        opportunity_score REAL,
        gap_score REAL,
        performance_score REAL,
        alignment_score REAL,
        competitor_coverage INTEGER,
        my_coverage INTEGER,
        avg_competitor_views INTEGER,
        avg_competitor_virality REAL,
        recommendation_type TEXT,
        generated_at TEXT,
        UNIQUE(my_channel_id, topic_name)
    )''')

    # Create indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_video ON video_snapshots(video_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_date ON video_snapshots(snapshot_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_competitors_my_channel ON competitors(my_channel_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_topics_video ON video_topics(video_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_topics_topic ON video_topics(topic_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_recommendations_channel ON topic_recommendations(my_channel_id)')

    conn.commit()
    conn.close()


def save_config(config: dict, config_path: str = "config.yaml") -> None:
    """Save configuration to YAML file."""
    if not YAML_AVAILABLE:
        print("YAML not available (pip install pyyaml)")
        return

    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def save_private_config(private_data: dict, config_path: str = "config.yaml") -> str:
    """
    Save private competitive analysis data to my_channels.yaml (gitignored).
    Returns the path to the private config file.
    """
    if not YAML_AVAILABLE:
        print("YAML not available (pip install pyyaml)")
        return ""

    private_config_path = os.path.join(os.path.dirname(config_path) or '.', 'my_channels.yaml')

    # Load existing private config
    existing = {}
    if os.path.exists(private_config_path):
        try:
            with open(private_config_path, 'r', encoding='utf-8') as f:
                existing = yaml.safe_load(f) or {}
        except:
            pass

    # Merge new data
    existing.update(private_data)

    # Save
    with open(private_config_path, 'w', encoding='utf-8') as f:
        f.write("# Private Competitive Analysis Config\n")
        f.write("# This file is gitignored - safe for your personal channel data\n\n")
        yaml.dump(existing, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return private_config_path


def set_my_channel(channel_handle: str, config_path: str = "config.yaml", output_dir: str = "./output") -> dict:
    """
    Set your channel as the home base for competitive analysis.
    Saves to my_channels.yaml (private, gitignored) and marks in database.
    """
    # Save to private config file
    private_path = save_private_config({'my_channel': channel_handle}, config_path)

    db_path = get_competitive_db_path(output_dir)
    migrate_competitive_database(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Reset any existing my_channel flags
    cursor.execute('UPDATE channels SET is_my_channel = 0')

    # Try to find and mark this channel
    cursor.execute('''
        UPDATE channels SET is_my_channel = 1, handle = ?
        WHERE channel_id = ? OR handle = ? OR title LIKE ?
    ''', (channel_handle, channel_handle, channel_handle, f'%{channel_handle.replace("@", "")}%'))

    conn.commit()
    conn.close()

    return {'channel': channel_handle, 'config_path': private_path, 'status': 'saved'}


def add_competitor_to_config(competitor_handle: str, config_path: str = "config.yaml") -> dict:
    """Add a seed competitor to my_channels.yaml (private, gitignored)."""
    private_config_path = os.path.join(os.path.dirname(config_path) or '.', 'my_channels.yaml')

    # Load existing private config
    existing = {}
    if os.path.exists(private_config_path):
        try:
            with open(private_config_path, 'r', encoding='utf-8') as f:
                existing = yaml.safe_load(f) or {}
        except:
            pass

    if not existing.get('seed_competitors'):
        existing['seed_competitors'] = []

    if competitor_handle not in existing['seed_competitors']:
        existing['seed_competitors'].append(competitor_handle)
        save_private_config(existing, config_path)
        return {'competitor': competitor_handle, 'status': 'added'}
    else:
        return {'competitor': competitor_handle, 'status': 'already_exists'}


def save_competitor_to_db(youtube, competitor_input: str, my_channel_id: str,
                          relevance_score: float, discovery_source: str,
                          db_path: str) -> dict:
    """Save a competitor to the database."""
    try:
        channel_id, channel_title = resolve_channel_id(youtube, competitor_input)
    except Exception as e:
        return {'error': str(e)}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO competitors
        (channel_id, my_channel_id, relevance_score, discovery_source, discovered_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (channel_id, my_channel_id, relevance_score, discovery_source, datetime.now().isoformat()))

    # Also update/insert into channels table
    cursor.execute('''
        INSERT OR IGNORE INTO channels (channel_id, title, is_competitor)
        VALUES (?, ?, 1)
    ''', (channel_id, channel_title))

    cursor.execute('''
        UPDATE channels SET is_competitor = 1, handle = ?
        WHERE channel_id = ?
    ''', (competitor_input if competitor_input.startswith('@') else None, channel_id))

    conn.commit()
    conn.close()

    return {
        'channel_id': channel_id,
        'title': channel_title,
        'relevance_score': relevance_score,
        'status': 'saved'
    }


def get_my_channel_id(youtube, config: dict, db_path: str) -> tuple:
    """Get my channel ID from config, resolving if needed."""
    my_channel = config.get('my_channel')
    if not my_channel:
        return None, None

    try:
        channel_id, channel_title = resolve_channel_id(youtube, my_channel)

        # Update database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO channels (channel_id, title, is_my_channel, handle)
            VALUES (?, ?, 1, ?)
        ''', (channel_id, channel_title, my_channel))
        conn.commit()
        conn.close()

        return channel_id, channel_title
    except Exception as e:
        print(f"Could not resolve my_channel '{my_channel}': {e}")
        return None, None


def list_competitors(db_path: str, my_channel_id: str = None) -> list:
    """List all tracked competitors."""
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if my_channel_id:
        cursor.execute('''
            SELECT c.channel_id, ch.title, c.relevance_score, c.discovery_source,
                   c.discovered_at, c.last_synced_at, ch.subscriber_count
            FROM competitors c
            LEFT JOIN channels ch ON c.channel_id = ch.channel_id
            WHERE c.my_channel_id = ?
            ORDER BY c.relevance_score DESC
        ''', (my_channel_id,))
    else:
        cursor.execute('''
            SELECT c.channel_id, ch.title, c.relevance_score, c.discovery_source,
                   c.discovered_at, c.last_synced_at, ch.subscriber_count
            FROM competitors c
            LEFT JOIN channels ch ON c.channel_id = ch.channel_id
            ORDER BY c.relevance_score DESC
        ''')

    rows = cursor.fetchall()
    conn.close()

    return [{
        'channel_id': row[0],
        'title': row[1] or 'Unknown',
        'relevance_score': row[2] or 0,
        'discovery_source': row[3],
        'discovered_at': row[4],
        'last_synced_at': row[5],
        'subscriber_count': row[6] or 0,
    } for row in rows]


def remove_competitor(db_path: str, channel_name: str, my_channel_id: str = None) -> dict:
    """Remove a competitor from tracking by name or channel ID."""
    if not os.path.exists(db_path):
        return {'error': 'Database not found'}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find the competitor by name (partial match) or channel_id
    cursor.execute('''
        SELECT c.channel_id, ch.title
        FROM competitors c
        LEFT JOIN channels ch ON c.channel_id = ch.channel_id
        WHERE ch.title LIKE ? OR c.channel_id = ?
    ''', (f'%{channel_name}%', channel_name))

    matches = cursor.fetchall()

    if not matches:
        conn.close()
        return {'error': f'No competitor found matching "{channel_name}"'}

    if len(matches) > 1:
        conn.close()
        return {
            'error': f'Multiple matches found for "{channel_name}"',
            'matches': [{'channel_id': m[0], 'title': m[1]} for m in matches]
        }

    channel_id, title = matches[0]

    # Delete from competitors table
    cursor.execute('DELETE FROM competitors WHERE channel_id = ?', (channel_id,))

    # Also delete their videos to clean up the database
    cursor.execute('DELETE FROM videos WHERE channel_id = ?', (channel_id,))

    conn.commit()
    deleted_videos = cursor.rowcount
    conn.close()

    return {
        'success': True,
        'removed': title,
        'channel_id': channel_id,
        'videos_removed': deleted_videos
    }


def remove_competitors_bulk(db_path: str, channel_names: list, my_channel_id: str = None) -> dict:
    """Remove multiple competitors at once."""
    results = []
    for name in channel_names:
        result = remove_competitor(db_path, name, my_channel_id)
        results.append({'name': name, **result})
    return {
        'removed': [r for r in results if r.get('success')],
        'failed': [r for r in results if not r.get('success')]
    }

