"""Video ideas, title suggestions, content calendar, description template, thumbnail patterns."""

from .common import *
from .metrics import analyze_title_patterns

# =============================================================================
# VIDEO IDEA GENERATOR & CONTENT STRATEGY
# =============================================================================

def generate_video_ideas(videos: list[dict], analytics: dict, competitors_data: dict = None) -> dict:
    """
    Generate video ideas based on content gaps, trends, and high-performing patterns.
    """
    ideas = {
        'gap_based': [],
        'trend_based': [],
        'formula_based': [],
        'competitor_inspired': [],
        'remix_ideas': [],
    }

    # Extract successful patterns
    top_videos = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:20]

    # High-performing keywords
    hp_keywords = analytics.get('keyword_analysis', {}).get('high_performing_keywords', {})
    top_keywords = list(hp_keywords.keys())[:10]

    # High-performing formulas
    formulas = analytics.get('title_analysis', {}).get('common_formulas', {})

    # 1. Gap-based ideas (topics not covered recently)
    all_title_words = []
    recent_topics = set()

    for v in videos:
        words = re.findall(r'\b\w+\b', v['title'].lower())
        all_title_words.extend(words)

        try:
            pub_date = datetime.fromisoformat(v['publish_date'].replace('Z', '+00:00'))
            if (datetime.now(pub_date.tzinfo) - pub_date).days <= 90:
                recent_topics.update(words)
        except:
            pass

    # Find topics covered before but not recently
    old_topics = set(all_title_words) - recent_topics
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'it', 'how', 'what', 'why'}
    gap_topics = [t for t in old_topics if t not in stop_words and len(t) > 3][:5]

    for topic in gap_topics:
        ideas['gap_based'].append({
            'idea': f"Revisit '{topic.title()}' with updated information",
            'reason': 'Previously covered topic not addressed recently',
            'suggested_title': f"The Ultimate Guide to {topic.title()} ({datetime.now().year})",
        })

    # 2. Trend-based ideas (combine trending elements)
    if top_keywords:
        for i in range(min(3, len(top_keywords))):
            kw1 = top_keywords[i]
            kw2 = top_keywords[(i + 1) % len(top_keywords)] if len(top_keywords) > 1 else kw1
            ideas['trend_based'].append({
                'idea': f"Combine '{kw1}' with '{kw2}'",
                'reason': 'Both keywords perform well individually',
                'suggested_title': f"How {kw1.title()} Changes Everything About {kw2.title()}",
            })

    # 3. Formula-based ideas (apply successful formulas to new topics)
    best_formulas = [f for f, count in sorted(formulas.items(), key=lambda x: x[1], reverse=True)[:3]]

    formula_suggestions = {
        'NUMBER': "Create a listicle: '7 Things About [Topic]'",
        'HOW TO': "Create a tutorial: 'How to [Action] in [Timeframe]'",
        'WHY': "Create an explainer: 'Why [Topic] Matters'",
        'X VS Y': "Create a comparison: '[Option A] vs [Option B]'",
        'REVIEW': "Create a review: '[Product/Topic] Review'",
    }

    for formula in best_formulas:
        for key, suggestion in formula_suggestions.items():
            if key in formula:
                ideas['formula_based'].append({
                    'idea': suggestion,
                    'reason': f"Formula '{formula}' performs well on this channel",
                    'formula': formula,
                })
                break

    # 4. Competitor-inspired ideas
    if competitors_data and competitors_data.get('competitors', {}).get('competitors'):
        ideas['competitor_inspired'].append({
            'idea': "Analyze and respond to competitor content",
            'reason': "Competitor channels identified in your niche",
            'suggested_title': "My Response to [Competitor Topic] - Here's What They Got Wrong",
        })

    # 5. Remix ideas (combine top performing video elements)
    if len(top_videos) >= 2:
        v1 = top_videos[0]
        v2 = top_videos[1]
        ideas['remix_ideas'].append({
            'idea': f"Combine elements from '{v1['title'][:30]}...' and '{v2['title'][:30]}...'",
            'reason': 'Both are top performers - combining elements could work',
            'suggested_title': f"The Complete Guide: {v1['title'].split()[0]} + {v2['title'].split()[-1]}",
        })

    # Count total ideas
    total_ideas = sum(len(v) for v in ideas.values())

    return {
        'ideas': ideas,
        'total_ideas': total_ideas,
        'top_keywords_used': top_keywords[:5],
        'best_formulas': best_formulas,
    }


def generate_ab_title_suggestions(video: dict, videos: list[dict]) -> dict:
    """
    Generate A/B title suggestions for a video based on successful patterns.
    """
    original_title = video['title']
    suggestions = []

    # Extract topic from title
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'it', 'how', 'what', 'why', 'i', 'my'}
    words = [w for w in re.findall(r'\b\w+\b', original_title.lower()) if w not in stop_words and len(w) > 2]
    main_topic = ' '.join(words[:3]).title() if words else 'Topic'

    # Get patterns from top videos
    top_videos = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:10]
    top_patterns = analyze_title_patterns(top_videos[0]['title']) if top_videos else {}

    # Generate suggestions based on different patterns
    current_year = datetime.now().year

    # Question format
    if not original_title.endswith('?'):
        suggestions.append({
            'title': f"Is {main_topic} Worth It? Here's The Truth",
            'pattern': 'question',
            'reason': 'Questions increase curiosity clicks',
        })

    # Number format
    if not re.search(r'\d+', original_title):
        suggestions.append({
            'title': f"7 {main_topic} Secrets Nobody Tells You",
            'pattern': 'number',
            'reason': 'Numbers set clear expectations',
        })

    # Brackets format
    if '[' not in original_title and '(' not in original_title:
        suggestions.append({
            'title': f"{main_topic} [{current_year} Complete Guide]",
            'pattern': 'brackets',
            'reason': 'Brackets add context and freshness',
        })

    # Emotional hook
    emotional_present = any(w in original_title.lower() for w in EMOTIONAL_WORDS)
    if not emotional_present:
        suggestions.append({
            'title': f"The Shocking Truth About {main_topic}",
            'pattern': 'emotional',
            'reason': 'Emotional words increase CTR',
        })

    # How-to format
    if not original_title.lower().startswith('how'):
        suggestions.append({
            'title': f"How to Master {main_topic} (Step-by-Step)",
            'pattern': 'how_to',
            'reason': 'How-to titles signal value',
        })

    return {
        'original_title': original_title,
        'suggestions': suggestions[:5],
        'title_score': video.get('title_hook_score', 0),
        'improvement_potential': 'high' if video.get('title_hook_score', 0) < 3 else 'medium' if video.get('title_hook_score', 0) < 5 else 'low',
    }


def build_content_calendar(analytics: dict, videos_per_week: int = 3) -> dict:
    """
    Generate an optimal content calendar based on performance patterns.
    """
    posting_schedule = analytics.get('posting_schedule', {})
    seasonality = analytics.get('seasonality', {})

    # Best days
    day_performance = posting_schedule.get('day_performance', {})
    days_ranked = sorted(day_performance.items(), key=lambda x: x[1].get('avg_virality', 0), reverse=True)

    # Best hours (estimate from data or use defaults)
    best_hours = [9, 12, 17]  # Default: morning, noon, evening

    # Generate calendar for next 4 weeks
    calendar = []
    current_date = datetime.now()

    day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}

    # Select best days for posting
    posting_days = [d[0] for d in days_ranked[:videos_per_week]] if days_ranked else ['Tuesday', 'Thursday', 'Saturday']

    for week in range(4):
        week_start = current_date + timedelta(weeks=week)

        for day_name in posting_days:
            day_num = day_map.get(day_name, 0)
            days_until = (day_num - week_start.weekday()) % 7
            post_date = week_start + timedelta(days=days_until)

            if post_date < current_date:
                post_date += timedelta(weeks=1)

            calendar.append({
                'date': post_date.strftime('%Y-%m-%d'),
                'day': day_name,
                'suggested_time': f"{best_hours[len(calendar) % len(best_hours)]:02d}:00 UTC",
                'week': week + 1,
                'performance_score': day_performance.get(day_name, {}).get('avg_virality', 0),
            })

    # Sort by date
    calendar.sort(key=lambda x: x['date'])

    # Monthly recommendations
    monthly_perf = seasonality.get('monthly_performance', {})
    current_month = datetime.now().strftime('%B')
    month_data = monthly_perf.get(current_month, {})

    return {
        'calendar': calendar[:12],  # Next 12 posting slots
        'posting_days': posting_days,
        'suggested_frequency': f"{videos_per_week} videos/week",
        'current_month_performance': {
            'month': current_month,
            'historical_avg_views': month_data.get('avg_views', 'N/A'),
            'historical_avg_virality': month_data.get('avg_virality', 'N/A'),
        },
        'best_season': seasonality.get('best_season', 'N/A'),
    }


def build_description_template(videos: list[dict]) -> dict:
    """
    Analyze top video descriptions and create an optimized template.
    """
    top_videos = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:20]

    # Analyze patterns
    has_timestamps = 0
    has_links = 0
    has_social = 0
    has_hashtags = 0
    has_discount = 0
    avg_length = 0
    common_phrases = []

    for v in top_videos:
        desc = v.get('description', '')
        avg_length += len(desc)

        if re.search(DESCRIPTION_SECTIONS['timestamps'], desc):
            has_timestamps += 1
        if re.search(DESCRIPTION_SECTIONS['links'], desc):
            has_links += 1
        if re.search(DESCRIPTION_SECTIONS['social_cta'], desc, re.I):
            has_social += 1
        if re.search(DESCRIPTION_SECTIONS['hashtags'], desc):
            has_hashtags += 1
        if re.search(DESCRIPTION_SECTIONS['discount_codes'], desc, re.I):
            has_discount += 1

    avg_length = avg_length // len(top_videos) if top_videos else 0

    # Build template
    template_parts = []

    template_parts.append("[HOOK: 1-2 sentences summarizing video value]")
    template_parts.append("")

    if has_timestamps > len(top_videos) * 0.3:
        template_parts.append("⏱️ TIMESTAMPS:")
        template_parts.append("0:00 - Introduction")
        template_parts.append("1:00 - [Section 1]")
        template_parts.append("5:00 - [Section 2]")
        template_parts.append("")

    if has_links > len(top_videos) * 0.5:
        template_parts.append("🔗 RESOURCES:")
        template_parts.append("• [Link 1]: [URL]")
        template_parts.append("• [Link 2]: [URL]")
        template_parts.append("")

    if has_social > len(top_videos) * 0.4:
        template_parts.append("📱 CONNECT WITH ME:")
        template_parts.append("• Twitter: [URL]")
        template_parts.append("• Instagram: [URL]")
        template_parts.append("")

    if has_discount > len(top_videos) * 0.2:
        template_parts.append("🎁 EXCLUSIVE OFFERS:")
        template_parts.append("• Use code [CODE] for [X]% off")
        template_parts.append("")

    if has_hashtags > len(top_videos) * 0.3:
        template_parts.append("#[topic] #[niche] #[year]")

    return {
        'template': '\n'.join(template_parts),
        'recommendations': {
            'use_timestamps': has_timestamps > len(top_videos) * 0.3,
            'include_links': has_links > len(top_videos) * 0.5,
            'add_social': has_social > len(top_videos) * 0.4,
            'use_hashtags': has_hashtags > len(top_videos) * 0.3,
            'optimal_length': f"{avg_length} characters",
        },
        'pattern_analysis': {
            'videos_with_timestamps': f"{has_timestamps}/{len(top_videos)}",
            'videos_with_links': f"{has_links}/{len(top_videos)}",
            'videos_with_social': f"{has_social}/{len(top_videos)}",
            'videos_with_hashtags': f"{has_hashtags}/{len(top_videos)}",
        }
    }


def analyze_thumbnail_patterns(videos: list[dict]) -> dict:
    """
    Analyze thumbnail URLs and patterns from successful videos.
    Note: Full image analysis would require additional libraries.
    """
    top_videos = sorted(videos, key=lambda x: x.get('virality_score', 0), reverse=True)[:30]

    thumbnails = []
    for v in top_videos:
        thumb_url = v.get('thumbnail_maxres') or v.get('thumbnail_high') or v.get('thumbnail_default')
        if thumb_url:
            thumbnails.append({
                'video_id': v['video_id'],
                'title': v['title'],
                'thumbnail_url': thumb_url,
                'views': v['view_count'],
                'virality': v.get('virality_score', 0),
            })

    # Patterns we can detect from titles (proxy for thumbnail content)
    has_face_indicator = 0  # Words suggesting face in thumb
    has_text_indicator = 0   # All caps words suggesting text overlay
    has_emotion_indicator = 0

    face_words = {'reaction', 'face', 'shocked', 'surprised', 'crying', 'laughing'}
    emotion_words = {'😱', '😂', '🤯', '!', '?'}

    for v in top_videos:
        title_lower = v['title'].lower()
        if any(fw in title_lower for fw in face_words):
            has_face_indicator += 1
        if re.search(r'\b[A-Z]{3,}\b', v['title']):
            has_text_indicator += 1
        if any(ew in v['title'] for ew in emotion_words):
            has_emotion_indicator += 1

    return {
        'top_thumbnails': thumbnails[:10],
        'patterns_detected': {
            'likely_has_faces': f"{has_face_indicator}/{len(top_videos)} top videos",
            'likely_has_text_overlay': f"{has_text_indicator}/{len(top_videos)} top videos",
            'emotional_indicators': f"{has_emotion_indicator}/{len(top_videos)} top videos",
        },
        'recommendations': [
            "Use high-contrast colors for visibility",
            "Include faces showing emotion when relevant",
            "Add 2-4 words of text overlay",
            "Maintain consistent branding/style",
            "Test different thumbnail styles",
        ],
        'download_command': f"python youtube_analyzer.py @channel --thumbnails",
    }

