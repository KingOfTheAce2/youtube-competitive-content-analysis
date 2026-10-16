"""Keyword rankings, playlists, related videos, competitor discovery, video network."""

from .common import *

# =============================================================================
# KEYWORD TRACKING
# =============================================================================

def track_keyword_rankings(youtube, keywords: list[str], channel_id: str, db_path: str) -> dict:
    """
    Track how channel videos rank for specific keywords over time.
    """
    rankings = {}

    for keyword in keywords[:10]:  # Limit to save quota
        try:
            response = retry_with_backoff(lambda kw=keyword: youtube.search().list(
                part='snippet',
                q=kw,
                type='video',
                maxResults=50,
            ).execute())

            position = None
            for i, item in enumerate(response.get('items', [])):
                if item['snippet']['channelId'] == channel_id:
                    position = i + 1
                    break

            rankings[keyword] = {
                'position': position,
                'in_top_10': position is not None and position <= 10,
                'in_top_50': position is not None,
                'timestamp': datetime.now().isoformat(),
            }
        except:
            rankings[keyword] = {'position': None, 'error': True}

    # Store in database if available
    if db_path and os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS keyword_rankings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT,
                keyword TEXT,
                position INTEGER,
                tracked_at TEXT
            )''')

            for keyword, data in rankings.items():
                if data.get('position'):
                    cursor.execute(
                        'INSERT INTO keyword_rankings (channel_id, keyword, position, tracked_at) VALUES (?,?,?,?)',
                        (channel_id, keyword, data['position'], data['timestamp'])
                    )

            conn.commit()
            conn.close()
        except:
            pass

    return {
        'rankings': rankings,
        'keywords_tracked': len(keywords),
        'in_top_10': sum(1 for r in rankings.values() if r.get('in_top_10')),
        'in_top_50': sum(1 for r in rankings.values() if r.get('in_top_50')),
    }


# =============================================================================
# PLAYLIST ANALYSIS
# =============================================================================

def analyze_playlists(youtube, channel_id: str) -> dict:
    """
    Analyze channel playlists and their performance.
    """
    try:
        response = retry_with_backoff(lambda: youtube.playlists().list(
            part='snippet,contentDetails',
            channelId=channel_id,
            maxResults=50,
        ).execute())

        playlists = []
        for item in response.get('items', []):
            playlists.append({
                'playlist_id': item['id'],
                'title': item['snippet']['title'],
                'description': item['snippet'].get('description', '')[:200],
                'video_count': item['contentDetails']['itemCount'],
                'published_at': item['snippet']['publishedAt'],
            })

        # Sort by video count
        playlists.sort(key=lambda x: x['video_count'], reverse=True)

        return {
            'total_playlists': len(playlists),
            'playlists': playlists[:20],
            'largest_playlist': playlists[0] if playlists else None,
            'total_videos_in_playlists': sum(p['video_count'] for p in playlists),
        }
    except Exception as e:
        return {'error': str(e), 'total_playlists': 0}


# =============================================================================
# VIDEO NETWORK & COMPETITOR DISCOVERY
# =============================================================================

def discover_related_videos(youtube, video: dict, max_results: int = MAX_RELATED_SEARCH_RESULTS) -> list[dict]:
    """
    Find videos related to a given video by searching for similar content.
    Note: YouTube deprecated relatedToVideoId, so we use keyword-based search.
    """
    # Extract keywords from title and tags
    title_words = re.findall(r'\b\w+\b', video['title'].lower())
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                  'of', 'with', 'by', 'from', 'is', 'it', 'this', 'that', 'i', 'you', 'we',
                  'my', 'your', 'how', 'what', 'why', 'when', 'where', 'which'}

    keywords = [w for w in title_words if w not in stop_words and len(w) > 3][:5]

    # Add top tags if available
    if video.get('tags'):
        keywords.extend(video['tags'][:3])

    if not keywords:
        return []

    search_query = ' '.join(keywords[:5])

    try:
        response = retry_with_backoff(lambda: youtube.search().list(
            part='snippet',
            q=search_query,
            type='video',
            maxResults=max_results,
            relevanceLanguage='en'
        ).execute())

        related = []
        for item in response.get('items', []):
            # Skip the same video
            if item['id']['videoId'] == video['video_id']:
                continue

            related.append({
                'video_id': item['id']['videoId'],
                'title': item['snippet']['title'],
                'channel_id': item['snippet']['channelId'],
                'channel_title': item['snippet']['channelTitle'],
                'description': item['snippet'].get('description', '')[:200],
                'published_at': item['snippet']['publishedAt'],
                'thumbnail': item['snippet'].get('thumbnails', {}).get('medium', {}).get('url', ''),
            })

        return related
    except Exception as e:
        print(f"Related video search error: {e}")
        return []


def discover_competitor_channels(youtube, channel_info: dict, videos: list[dict],
                                  max_channels: int = MAX_COMPETITOR_CHANNELS) -> dict:
    """
    Discover competitor channels based on:
    1. Channels that appear in related video searches
    2. Channels with similar content (keyword overlap)
    3. Channels mentioned in video descriptions
    """
    competitor_scores = defaultdict(lambda: {'score': 0, 'reasons': [], 'videos': []})
    own_channel_id = channel_info['channel_id']

    # Collect keywords from analyzed channel
    all_tags = []
    all_title_words = []

    for v in videos:
        all_tags.extend([t.lower() for t in v.get('tags', [])])
        words = re.findall(r'\b\w+\b', v['title'].lower())
        all_title_words.extend([w for w in words if len(w) > 3])

    top_tags = [tag for tag, _ in Counter(all_tags).most_common(10)]
    top_words = [w for w, _ in Counter(all_title_words).most_common(10)]

    # Search for competitors using top keywords/tags
    search_queries = []
    if top_tags:
        search_queries.append(' '.join(top_tags[:4]))
    if top_words:
        search_queries.append(' '.join(top_words[:4]))

    # Add category-specific search
    categories = Counter(v['category_name'] for v in videos).most_common(1)
    if categories:
        main_category = categories[0][0]
        if main_category != 'Unknown':
            search_queries.append(f"{main_category} {' '.join(top_words[:2])}")

    print(f"  Searching for competitors...")

    for query in search_queries[:3]:  # Limit to 3 searches to save quota
        try:
            response = retry_with_backoff(lambda q=query: youtube.search().list(
                part='snippet',
                q=q,
                type='channel',
                maxResults=15,
                relevanceLanguage='en'
            ).execute())

            for item in response.get('items', []):
                ch_id = item['snippet']['channelId']
                if ch_id == own_channel_id:
                    continue

                competitor_scores[ch_id]['channel_id'] = ch_id
                competitor_scores[ch_id]['title'] = item['snippet']['title']
                competitor_scores[ch_id]['description'] = item['snippet'].get('description', '')[:200]
                competitor_scores[ch_id]['thumbnail'] = item['snippet'].get('thumbnails', {}).get('medium', {}).get('url', '')
                competitor_scores[ch_id]['score'] += 1
                competitor_scores[ch_id]['reasons'].append(f"Found in search: {query[:30]}...")
        except Exception as e:
            print(f"  Competitor search error: {e}")

    # Also search for related videos from top-performing content
    top_videos = sorted(videos, key=lambda x: x['virality_score'], reverse=True)[:5]

    for v in top_videos:
        related = discover_related_videos(youtube, v, max_results=10)
        for rel in related:
            ch_id = rel['channel_id']
            if ch_id == own_channel_id:
                continue

            competitor_scores[ch_id]['channel_id'] = ch_id
            competitor_scores[ch_id]['title'] = rel['channel_title']
            competitor_scores[ch_id]['score'] += 2  # Higher weight for video-based discovery
            competitor_scores[ch_id]['reasons'].append(f"Related to: {v['title'][:30]}...")
            competitor_scores[ch_id]['videos'].append(rel['video_id'])

    # Extract channels mentioned in descriptions
    youtube_channel_pattern = r'(?:youtube\.com/(?:channel/|c/|@))([a-zA-Z0-9_-]+)'
    for v in videos[:50]:  # Check top 50 video descriptions
        matches = re.findall(youtube_channel_pattern, v.get('description', ''))
        for match in matches:
            # Note: This is a handle/custom URL, not channel ID
            competitor_scores[match]['score'] += 1
            competitor_scores[match]['reasons'].append("Mentioned in description")

    # Sort by score and return top competitors
    sorted_competitors = sorted(
        competitor_scores.items(),
        key=lambda x: x[1]['score'],
        reverse=True
    )[:max_channels]

    # Get additional info for top competitors
    competitors_list = []
    for ch_id, data in sorted_competitors:
        if data.get('title'):  # Only include if we have channel info
            competitors_list.append({
                'channel_id': ch_id,
                'title': data.get('title', 'Unknown'),
                'description': data.get('description', ''),
                'thumbnail': data.get('thumbnail', ''),
                'relevance_score': data['score'],
                'discovery_reasons': list(set(data['reasons']))[:3],  # Unique reasons
                'related_videos': data['videos'][:5],
            })

    return {
        'competitors': competitors_list,
        'total_found': len(competitors_list),
        'search_keywords': top_tags[:5] + top_words[:5],
    }


def build_video_network(youtube, videos: list[dict], channel_info: dict,
                        sample_size: int = 10) -> dict:
    """
    Build a network map showing how videos relate to the broader YouTube ecosystem.
    Shows which other channels/videos are in the same "content neighborhood".
    """
    print("  Building video network map...")

    network = {
        'center_channel': {
            'id': channel_info['channel_id'],
            'title': channel_info['title'],
            'subscribers': channel_info.get('subscriber_count', 0),
        },
        'related_channels': defaultdict(lambda: {'appearances': 0, 'videos': []}),
        'content_clusters': [],
        'network_stats': {},
    }

    # Sample top-performing videos for network analysis
    sample_videos = sorted(videos, key=lambda x: x['virality_score'], reverse=True)[:sample_size]

    all_related_channels = []

    for v in progress_bar(sample_videos, desc="Mapping network"):
        related = discover_related_videos(youtube, v, max_results=15)

        for rel in related:
            ch_id = rel['channel_id']
            if ch_id == channel_info['channel_id']:
                continue

            network['related_channels'][ch_id]['channel_id'] = ch_id
            network['related_channels'][ch_id]['title'] = rel['channel_title']
            network['related_channels'][ch_id]['appearances'] += 1
            network['related_channels'][ch_id]['videos'].append({
                'source_video': v['title'][:50],
                'related_video': rel['title'][:50],
                'related_video_id': rel['video_id'],
            })

            all_related_channels.append(ch_id)

    # Convert to list and sort by appearances (no limit - keep all)
    related_list = sorted(
        network['related_channels'].values(),
        key=lambda x: x['appearances'],
        reverse=True
    )

    # Calculate network stats
    unique_channels = len(set(all_related_channels))
    most_connected = related_list[0] if related_list else None

    network['related_channels'] = related_list
    network['network_stats'] = {
        'videos_analyzed': len(sample_videos),
        'unique_related_channels': unique_channels,
        'avg_connections_per_video': round(len(all_related_channels) / max(len(sample_videos), 1), 1),
        'most_connected_channel': most_connected['title'] if most_connected else None,
        'most_connected_appearances': most_connected['appearances'] if most_connected else 0,
    }

    # Identify content clusters (channels that appear together frequently)
    channel_pairs = defaultdict(int)
    for i, v in enumerate(sample_videos):
        related = discover_related_videos(youtube, v, max_results=10)
        channels_in_related = [r['channel_id'] for r in related if r['channel_id'] != channel_info['channel_id']]

        # Count co-occurrences
        for j, ch1 in enumerate(channels_in_related):
            for ch2 in channels_in_related[j+1:]:
                pair = tuple(sorted([ch1, ch2]))
                channel_pairs[pair] += 1

    # Top channel pairs that often appear together
    top_pairs = sorted(channel_pairs.items(), key=lambda x: x[1], reverse=True)[:10]
    network['content_clusters'] = [
        {'channels': list(pair), 'co_occurrences': count}
        for pair, count in top_pairs
    ]

    return network


def analyze_content_neighborhood(youtube, channel_info: dict, videos: list[dict]) -> dict:
    """
    Comprehensive analysis of the channel's position in the YouTube ecosystem.
    Combines competitor discovery and video network analysis.
    """
    print("\n🌐 Analyzing content neighborhood...")

    # Discover competitors
    competitors = discover_competitor_channels(youtube, channel_info, videos)

    # Build video network (limited to save API quota)
    network = build_video_network(youtube, videos, channel_info, sample_size=15)

    # Combine insights
    neighborhood = {
        'competitors': competitors,
        'video_network': network,
        'insights': [],
    }

    # Generate insights
    if competitors['competitors']:
        top_comp = competitors['competitors'][0]
        neighborhood['insights'].append(
            f"Top competitor: {top_comp['title']} (relevance score: {top_comp['relevance_score']})"
        )

    if network['network_stats'].get('most_connected_channel'):
        neighborhood['insights'].append(
            f"Most connected channel in your niche: {network['network_stats']['most_connected_channel']}"
        )

    if network['network_stats'].get('unique_related_channels', 0) > 20:
        neighborhood['insights'].append(
            "Your content connects to a diverse range of channels - broad appeal"
        )
    elif network['network_stats'].get('unique_related_channels', 0) < 10:
        neighborhood['insights'].append(
            "Your content has a focused niche - consider expanding topics for growth"
        )

    return neighborhood

