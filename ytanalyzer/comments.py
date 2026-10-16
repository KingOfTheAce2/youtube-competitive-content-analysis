"""Comment fetching and sentiment."""

from .common import *

# =============================================================================
# SENTIMENT & COMMENTS ANALYSIS
# =============================================================================

def analyze_comment_sentiment(comments: list[str]) -> dict:
    """
    Simple sentiment analysis on comments using keyword matching.
    """
    if not comments:
        return {'sentiment_score': 0, 'sentiment_label': 'neutral', 'analyzed': 0}

    positive_count = 0
    negative_count = 0
    neutral_count = 0

    for comment in comments:
        comment_lower = comment.lower()
        pos = sum(1 for w in POSITIVE_WORDS if w in comment_lower)
        neg = sum(1 for w in NEGATIVE_WORDS if w in comment_lower)

        if pos > neg:
            positive_count += 1
        elif neg > pos:
            negative_count += 1
        else:
            neutral_count += 1

    total = len(comments)
    sentiment_score = (positive_count - negative_count) / total if total > 0 else 0

    if sentiment_score > 0.3:
        label = 'very_positive'
    elif sentiment_score > 0.1:
        label = 'positive'
    elif sentiment_score > -0.1:
        label = 'neutral'
    elif sentiment_score > -0.3:
        label = 'negative'
    else:
        label = 'very_negative'

    return {
        'sentiment_score': round(sentiment_score, 3),
        'sentiment_label': label,
        'positive_count': positive_count,
        'negative_count': negative_count,
        'neutral_count': neutral_count,
        'analyzed': total,
    }


def fetch_video_comments(youtube, video_id: str, max_comments: int = 100) -> list[str]:
    """
    Fetch comments for a video (requires additional API quota).
    """
    try:
        comments = []
        next_page = None

        while len(comments) < max_comments:
            response = retry_with_backoff(lambda: youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=min(100, max_comments - len(comments)),
                pageToken=next_page,
                textFormat='plainText'
            ).execute())

            for item in response.get('items', []):
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(comment)

            next_page = response.get('nextPageToken')
            if not next_page:
                break

        return comments
    except Exception as e:
        return []

