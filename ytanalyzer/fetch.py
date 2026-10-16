"""YouTube API: channel resolution, playlist and video metadata."""

from .common import *
from .metrics import analyze_title_patterns, calculate_virality_score, detect_collaboration, detect_series, estimate_revenue, extract_links_from_description, extract_title_formula

# =============================================================================
# CHANNEL RESOLUTION
# =============================================================================

def extract_channel_id_from_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    path = parsed.path.strip('/')

    if path.startswith('channel/'):
        return path.split('/')[1]
    if path.startswith('@'):
        return path
    if path.startswith('c/'):
        return path
    if path.startswith('user/'):
        return path
    return None


def resolve_channel_id(youtube, identifier: str) -> tuple[str, str]:
    if identifier.startswith('UC') and len(identifier) == 24:
        response = retry_with_backoff(lambda: youtube.channels().list(
            part='snippet', id=identifier
        ).execute())
        if response.get('items'):
            return identifier, response['items'][0]['snippet']['title']
        raise ValueError(f"Channel not found: {identifier}")

    if identifier.startswith('@'):
        handle = identifier[1:]
        response = retry_with_backoff(lambda: youtube.channels().list(
            part='snippet', forHandle=handle
        ).execute())
        if response.get('items'):
            item = response['items'][0]
            return item['id'], item['snippet']['title']
        raise ValueError(f"Channel not found: {identifier}")

    if identifier.startswith('c/'):
        custom_name = identifier[2:]
        response = retry_with_backoff(lambda: youtube.search().list(
            part='snippet', q=custom_name, type='channel', maxResults=5
        ).execute())
        for item in response.get('items', []):
            return item['snippet']['channelId'], item['snippet']['channelTitle']
        raise ValueError(f"Channel not found: {identifier}")

    if identifier.startswith('user/'):
        username = identifier[5:]
        response = retry_with_backoff(lambda: youtube.channels().list(
            part='snippet', forUsername=username
        ).execute())
        if response.get('items'):
            item = response['items'][0]
            return item['id'], item['snippet']['title']
        raise ValueError(f"Channel not found: {identifier}")

    # Try handle then ID
    response = retry_with_backoff(lambda: youtube.channels().list(
        part='snippet', forHandle=identifier
    ).execute())
    if response.get('items'):
        item = response['items'][0]
        return item['id'], item['snippet']['title']

    response = retry_with_backoff(lambda: youtube.channels().list(
        part='snippet', id=identifier
    ).execute())
    if response.get('items'):
        return identifier, response['items'][0]['snippet']['title']

    raise ValueError(f"Could not resolve: {identifier}")


def get_channel_info(youtube, channel_id: str) -> dict:
    response = retry_with_backoff(lambda: youtube.channels().list(
        part='snippet,statistics,contentDetails,brandingSettings',
        id=channel_id
    ).execute())

    if not response.get('items'):
        raise ValueError(f"Channel not found: {channel_id}")

    item = response['items'][0]

    return {
        'channel_id': channel_id,
        'title': item['snippet']['title'],
        'description': item['snippet'].get('description', ''),
        'custom_url': item['snippet'].get('customUrl', ''),
        'published_at': item['snippet'].get('publishedAt', ''),
        'country': item['snippet'].get('country', ''),
        'subscriber_count': int(item['statistics'].get('subscriberCount', 0)),
        'video_count': int(item['statistics'].get('videoCount', 0)),
        'view_count': int(item['statistics'].get('viewCount', 0)),
        'uploads_playlist_id': item['contentDetails']['relatedPlaylists']['uploads'],
        'thumbnail_url': item['snippet'].get('thumbnails', {}).get('high', {}).get('url', ''),
    }


# =============================================================================
# VIDEO FETCHING
# =============================================================================

def fetch_video_ids_from_playlist(youtube, playlist_id: str,
                                   since: Optional[datetime] = None,
                                   until: Optional[datetime] = None,
                                   limit: Optional[int] = None) -> list[str]:
    video_ids = []
    next_page_token = None

    print("Fetching video IDs...")

    while True:
        response = retry_with_backoff(lambda: youtube.playlistItems().list(
            part='contentDetails,snippet',
            playlistId=playlist_id,
            maxResults=MAX_RESULTS_PER_PAGE,
            pageToken=next_page_token
        ).execute())

        for item in response.get('items', []):
            video_id = item['contentDetails']['videoId']
            published_at_str = item['snippet'].get('publishedAt', '')

            if published_at_str:
                published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                if since and published_at.replace(tzinfo=None) < since:
                    continue
                if until and published_at.replace(tzinfo=None) > until:
                    continue

            video_ids.append(video_id)

            if limit and len(video_ids) >= limit:
                return video_ids

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    print(f"Found {len(video_ids)} videos")
    return video_ids


def fetch_video_metadata_batch(youtube, video_ids: list[str], channel_info: dict,
                                min_views: Optional[int] = None) -> list[dict]:
    all_videos = []
    channel_subscribers = channel_info.get('subscriber_count', 0)

    print(f"\nFetching metadata for {len(video_ids)} videos...")

    batches = [video_ids[i:i + MAX_RESULTS_PER_PAGE]
               for i in range(0, len(video_ids), MAX_RESULTS_PER_PAGE)]

    for batch in progress_bar(batches, desc="Fetching"):
        response = retry_with_backoff(lambda b=batch: youtube.videos().list(
            part='snippet,statistics,contentDetails,topicDetails,status',
            id=','.join(b)
        ).execute())

        for item in response.get('items', []):
            stats = item.get('statistics', {})
            view_count = int(stats.get('viewCount', 0))

            if min_views and view_count < min_views:
                continue

            snippet = item['snippet']
            content_details = item.get('contentDetails', {})
            status = item.get('status', {})

            like_count = int(stats.get('likeCount', 0))
            comment_count = int(stats.get('commentCount', 0))
            engagement_rate = ((like_count + comment_count) / view_count * 100) if view_count > 0 else 0
            duration_seconds = parse_duration(content_details.get('duration', ''))

            title_patterns = analyze_title_patterns(snippet['title'])
            title_formula = extract_title_formula(snippet['title'])
            series_info = detect_series(snippet['title'])
            collab_info = detect_collaboration(snippet['title'], snippet.get('description', ''))
            description_links = extract_links_from_description(snippet.get('description', ''))

            category_name = VIDEO_CATEGORIES.get(snippet.get('categoryId', ''), 'Unknown')
            revenue_est = estimate_revenue({'view_count': view_count}, category_name)

            video_data = {
                'video_id': item['id'],
                'title': snippet['title'],
                'description': snippet.get('description', ''),
                'publish_date': snippet['publishedAt'],
                'channel_id': snippet['channelId'],
                'channel_title': snippet['channelTitle'],

                'view_count': view_count,
                'like_count': like_count,
                'comment_count': comment_count,
                'engagement_rate': round(engagement_rate, 4),

                'duration_seconds': duration_seconds,
                'duration_formatted': format_duration(duration_seconds),
                'definition': content_details.get('definition', ''),
                'caption': content_details.get('caption', 'false'),

                'category_id': snippet.get('categoryId', ''),
                'category_name': category_name,
                'tags': snippet.get('tags', []),
                'tags_count': len(snippet.get('tags', [])),

                'thumbnail_default': snippet.get('thumbnails', {}).get('default', {}).get('url', ''),
                'thumbnail_high': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                'thumbnail_maxres': snippet.get('thumbnails', {}).get('maxres', {}).get('url', ''),

                'publish_day_of_week': '',
                'publish_hour': 0,
                'publish_month': '',
                'title_length': len(snippet['title']),
                'description_length': len(snippet.get('description', '')),
                'has_tags': len(snippet.get('tags', [])) > 0,
                'is_short': 0 < duration_seconds <= 60,
                'is_long_form': duration_seconds > 600,

                'title_hook_score': title_patterns['title_hook_score'],
                'title_has_number': title_patterns['has_number'],
                'title_is_question': title_patterns['is_question'],
                'title_has_emotional_word': title_patterns['has_emotional_word'],
                'title_has_brackets': title_patterns['has_brackets'] or title_patterns['has_parentheses'],
                'title_formula': title_formula,

                'is_series': series_info['is_series'],
                'series_number': series_info['series_number'],
                'is_collab': collab_info['is_collab'],

                'description_link_count': description_links['total_links'],
                'has_affiliate_links': description_links['has_affiliate_links'],

                'estimated_revenue_low': revenue_est['estimated_revenue_low'],
                'estimated_revenue_mid': revenue_est['estimated_revenue_mid'],
                'estimated_revenue_high': revenue_est['estimated_revenue_high'],

                'virality_score': 0.0,
            }

            try:
                pub_date = datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00'))
                video_data['publish_day_of_week'] = pub_date.strftime('%A')
                video_data['publish_hour'] = pub_date.hour
                video_data['publish_month'] = pub_date.strftime('%B')
            except:
                pass

            video_data['virality_score'] = calculate_virality_score(video_data, channel_subscribers)

            all_videos.append(video_data)

    return all_videos

