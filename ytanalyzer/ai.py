"""Optional AI recommendations (Anthropic, OpenAI, Gemini)."""

from .common import *

# =============================================================================
# AI-ENHANCED ANALYSIS
# =============================================================================

def detect_ai_provider() -> tuple[str, str]:
    """
    Detect available AI provider based on API keys in environment.
    Returns (provider_name, api_key) or (None, None) if no provider available.
    Priority: Anthropic > OpenAI > Gemini
    """
    # Check Anthropic
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    if anthropic_key and ANTHROPIC_AVAILABLE:
        return ('anthropic', anthropic_key)

    # Check OpenAI
    openai_key = os.environ.get('OPENAI_API_KEY')
    if openai_key and OPENAI_AVAILABLE:
        return ('openai', openai_key)

    # Check Gemini
    gemini_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if gemini_key and GEMINI_AVAILABLE:
        return ('gemini', gemini_key)

    return (None, None)


def format_analysis_for_ai(
    your_channel: dict,
    your_analytics: dict,
    your_videos: list[dict],
    competitor_channel: dict = None,
    competitor_analytics: dict = None,
    traffic_analysis: dict = None,
) -> str:
    """
    Format analysis data into a prompt for AI analysis.
    """
    prompt_parts = []

    # Your channel summary
    prompt_parts.append(f"""## Your Channel: {your_channel.get('title', 'Unknown')}
- Subscribers: {format_number(your_channel.get('subscriber_count', 0))}
- Total Videos Analyzed: {your_analytics.get('overview', {}).get('total_videos_analyzed', 0)}
- Average Views per Video: {format_number(your_analytics.get('overview', {}).get('average_views_per_video', 0))}
- Average Virality Score: {your_analytics.get('overview', {}).get('average_virality_score', 0):.3f}
- Health Score: {your_analytics.get('health_score', {}).get('total_score', 0):.0f}/100 ({your_analytics.get('health_score', {}).get('grade', 'N/A')})
- Viral Videos: {your_analytics.get('viral_videos', {}).get('count', 0)} ({your_analytics.get('viral_videos', {}).get('percentage', 0):.1f}%)
""")

    # Top performing videos
    top_videos = your_analytics.get('top_videos', {}).get('by_virality', [])[:5]
    if top_videos:
        prompt_parts.append("### Your Top Performing Videos:")
        for v in top_videos:
            prompt_parts.append(f"- \"{v['title']}\" (views: {format_number(v.get('views', 0))}, virality: {v.get('virality', 0):.2f})")
        prompt_parts.append("")

    # Traffic drivers insights
    traffic_drivers = your_analytics.get('traffic_drivers', {})
    if traffic_drivers.get('patterns', {}).get('key_differences'):
        prompt_parts.append("### What Makes Your Top Videos Different:")
        for key, diff in traffic_drivers['patterns']['key_differences'].items():
            prompt_parts.append(f"- {diff}")
        prompt_parts.append("")

    # High performing keywords
    if traffic_drivers.get('top_keywords'):
        keywords = [kw['keyword'] for kw in traffic_drivers['top_keywords'][:10]]
        prompt_parts.append(f"### Your High-Performing Keywords: {', '.join(keywords)}")
        prompt_parts.append("")

    # Content gaps from network
    content_gaps = your_analytics.get('content_gaps', {})
    if content_gaps.get('topic_gaps'):
        high_gaps = [g['topic'] for g in content_gaps['topic_gaps'] if g['opportunity_level'] == 'high'][:10]
        if high_gaps:
            prompt_parts.append(f"### Content Gaps (topics related channels cover that you don't): {', '.join(high_gaps)}")
            prompt_parts.append("")

    # Competitor analysis
    if competitor_channel and competitor_analytics:
        prompt_parts.append(f"""## Competitor Channel: {competitor_channel.get('title', 'Unknown')}
- Subscribers: {format_number(competitor_channel.get('subscriber_count', 0))}
- Average Views per Video: {format_number(competitor_analytics.get('overview', {}).get('average_views_per_video', 0))}
- Average Virality Score: {competitor_analytics.get('overview', {}).get('average_virality_score', 0):.3f}
- Health Score: {competitor_analytics.get('health_score', {}).get('total_score', 0):.0f}/100
""")

        # Competitor top videos
        comp_top = competitor_analytics.get('top_videos', {}).get('by_virality', [])[:5]
        if comp_top:
            prompt_parts.append("### Competitor's Top Performing Videos:")
            for v in comp_top:
                prompt_parts.append(f"- \"{v['title']}\" (views: {format_number(v.get('views', 0))}, virality: {v.get('virality', 0):.2f})")
            prompt_parts.append("")

    # Traffic capture analysis
    if traffic_analysis:
        prompt_parts.append("## Traffic Capture Opportunities:")

        # Keyword gaps
        keyword_gaps = traffic_analysis.get('keyword_gaps', [])[:10]
        if keyword_gaps:
            gaps = [f"{g['keyword']} ({g['opportunity']})" for g in keyword_gaps]
            prompt_parts.append(f"### Keyword Gaps (competitor ranks, you don't): {', '.join(gaps)}")

        # Viral gaps
        viral_gaps = traffic_analysis.get('viral_gaps', [])[:5]
        if viral_gaps:
            prompt_parts.append("### Competitor Viral Videos You Haven't Covered:")
            for gap in viral_gaps:
                prompt_parts.append(f"- \"{gap['competitor_title']}\" ({format_number(gap['views'])} views)")

        # Title patterns
        patterns = traffic_analysis.get('title_patterns', {})
        if patterns.get('competitor') and patterns.get('yours'):
            comp_p = patterns['competitor']
            your_p = patterns['yours']
            prompt_parts.append(f"""### Title Pattern Comparison:
- Numbers in titles: You {your_p.get('percent_with_numbers', 0)}% vs Competitor {comp_p.get('percent_with_numbers', 0)}%
- How-to content: You {your_p.get('percent_how_to', 0)}% vs Competitor {comp_p.get('percent_how_to', 0)}%
- Question titles: You {your_p.get('percent_questions', 0)}% vs Competitor {comp_p.get('percent_questions', 0)}%
""")

    return '\n'.join(prompt_parts)


def get_ai_analysis_prompt(analysis_data: str, focus: str = 'general') -> str:
    """
    Create the full prompt for AI analysis.
    """
    base_prompt = f"""You are a YouTube growth strategist and content consultant. Analyze this YouTube channel data and provide actionable recommendations.

{analysis_data}

Based on this analysis, provide:

1. **Video Topic Ideas** (5-7 specific video ideas with working titles)
   - Each should target a gap or opportunity identified in the data
   - Include the strategic reasoning for each idea

2. **Content Strategy Recommendations** (3-5 actionable strategies)
   - How to improve based on what's working
   - How to capture competitor traffic
   - Posting schedule and format recommendations

3. **Title & Thumbnail Optimization** (specific suggestions)
   - Title formulas that would work for this channel
   - Thumbnail style recommendations based on top performers

4. **Quick Wins** (3 things to implement immediately)
   - Low-effort, high-impact changes

5. **90-Day Growth Plan** (prioritized roadmap)
   - Week 1-2, Week 3-4, Month 2, Month 3

Format your response in clear markdown with headers. Be specific and actionable - avoid generic advice. Reference the actual data provided."""

    return base_prompt


def call_anthropic_api(prompt: str, api_key: str) -> str:
    """Call Anthropic Claude API."""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text
    except Exception as e:
        return f"Error calling Anthropic API: {e}"


def call_openai_api(prompt: str, api_key: str) -> str:
    """Call OpenAI API."""
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error calling OpenAI API: {e}"


def call_gemini_api(prompt: str, api_key: str) -> str:
    """Call Google Gemini API."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error calling Gemini API: {e}"


def get_ai_recommendations(
    your_channel: dict,
    your_analytics: dict,
    your_videos: list[dict],
    competitor_channel: dict = None,
    competitor_analytics: dict = None,
    traffic_analysis: dict = None,
    output_dir: str = None,
) -> dict:
    """
    Get AI-powered recommendations using available AI provider.
    Falls back to generating a prompt file for manual use with Claude Code.
    """
    # Format the analysis data
    analysis_data = format_analysis_for_ai(
        your_channel, your_analytics, your_videos,
        competitor_channel, competitor_analytics, traffic_analysis
    )

    # Create the full prompt
    full_prompt = get_ai_analysis_prompt(analysis_data)

    # Detect available provider
    provider, api_key = detect_ai_provider()

    result = {
        'provider': provider,
        'prompt': full_prompt,
        'recommendations': None,
        'prompt_file': None,
    }

    if provider == 'anthropic':
        print("\n🤖 Generating AI recommendations using Claude...")
        result['recommendations'] = call_anthropic_api(full_prompt, api_key)
    elif provider == 'openai':
        print("\n🤖 Generating AI recommendations using GPT-4...")
        result['recommendations'] = call_openai_api(full_prompt, api_key)
    elif provider == 'gemini':
        print("\n🤖 Generating AI recommendations using Gemini...")
        result['recommendations'] = call_gemini_api(full_prompt, api_key)
    else:
        # No API key - save prompt for manual use
        print("\n⚠️  No AI API key found. Generating prompt file for manual use...")
        print("   Set one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY")

        if output_dir:
            prompt_file = os.path.join(output_dir, 'ai_analysis_prompt.md')
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write("# AI Analysis Prompt\n\n")
                f.write("Copy and paste this prompt into Claude Code, ChatGPT, or any AI assistant:\n\n")
                f.write("---\n\n")
                f.write(full_prompt)
            result['prompt_file'] = prompt_file
            print(f"   📄 Prompt saved to: {prompt_file}")
            print(f"\n   💡 To use with Claude Code, run:")
            print(f"      cat \"{prompt_file}\" | claude")
            print(f"\n   Or copy the contents and paste into any AI chat interface.")

    return result


def generate_ai_recommendations_html(ai_result: dict) -> str:
    """Generate HTML section for AI recommendations."""
    if not ai_result.get('recommendations'):
        if ai_result.get('prompt_file'):
            return f'''
        <div class="section" style="margin-top: 30px; background: linear-gradient(135deg, rgba(255,193,7,0.1) 0%, rgba(255,107,107,0.1) 100%);">
            <h2>🤖 AI Analysis</h2>
            <p style="color:#a0aec0;">No AI API key configured. A prompt file has been generated for manual use.</p>
            <p style="margin-top:15px;">
                <strong>Prompt file:</strong> <code>{ai_result['prompt_file']}</code>
            </p>
            <p style="color:#a0aec0;margin-top:10px;">
                Copy the prompt and paste it into Claude, ChatGPT, or any AI assistant to get personalized recommendations.
            </p>
        </div>
            '''
        return ""

    # Convert markdown to basic HTML
    recommendations = ai_result['recommendations']
    # Simple markdown to HTML conversion
    recommendations_html = recommendations.replace('\n\n', '</p><p>')
    recommendations_html = recommendations_html.replace('**', '<strong>').replace('**', '</strong>')
    recommendations_html = recommendations_html.replace('# ', '<h3>').replace('\n', '<br>')

    provider_names = {
        'anthropic': 'Claude',
        'openai': 'GPT-4',
        'gemini': 'Gemini'
    }
    provider_name = provider_names.get(ai_result.get('provider'), 'AI')

    return f'''
        <div class="section" style="margin-top: 30px; background: linear-gradient(135deg, rgba(102,126,234,0.15) 0%, rgba(56,239,125,0.1) 100%);">
            <h2>🤖 AI-Powered Recommendations</h2>
            <p style="color:#a0aec0;margin-bottom:20px;">Generated by {provider_name} based on your channel analysis.</p>
            <div style="background:rgba(0,0,0,0.2);border-radius:10px;padding:25px;line-height:1.8;">
                <div class="ai-content" style="white-space:pre-wrap;font-size:0.95em;">
{recommendations}
                </div>
            </div>
        </div>
    '''


def save_ai_recommendations(ai_result: dict, output_path: str) -> None:
    """Save AI recommendations to a markdown file."""
    if not ai_result.get('recommendations'):
        return

    provider_names = {
        'anthropic': 'Claude',
        'openai': 'GPT-4',
        'gemini': 'Gemini'
    }
    provider_name = provider_names.get(ai_result.get('provider'), 'AI')

    content = f"""# AI-Powered YouTube Growth Recommendations

*Generated by {provider_name} on {datetime.now().strftime('%Y-%m-%d %H:%M')}*

---

{ai_result['recommendations']}
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"📄 AI recommendations saved: {output_path}")

