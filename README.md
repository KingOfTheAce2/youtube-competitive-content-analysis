# YouTube Competitive Content Analysis Tool

The ultimate Python tool for YouTube channel analysis and competitive intelligence. Get comprehensive insights on content performance, generate video ideas, track trends, discover competitors, and build data-driven content strategies.

## What This Tool Does

Analyze any YouTube channel and get:
- **Virality scores** - Find videos that overperformed relative to channel size
- **Channel health score** - Overall grade (A+ to F) based on engagement, virality, consistency
- **Competitor discovery** - Automatically find channels competing for the same audience
- **Video network analysis** - See the "web" of related channels in your niche
- **Video idea generator** - AI-powered content suggestions based on gaps and trends
- **Content calendar builder** - Optimal posting schedule based on performance data
- **Trend velocity detection** - Identify exploding content early
- **Title A/B suggestions** - Optimize underperforming video titles
- **Revenue estimates** - CPM-based earnings calculations
- **Keyword rank tracking** - Monitor search rankings over time
- **Playlist analysis** - Track playlist performance
- **Collaboration ROI** - Measure collab vs solo content performance
- **Interactive HTML dashboard** - Beautiful charts and visualizations
- **API server mode** - Integrate with your own tools
- **Trend alerts** - Get notified when competitors go viral
- **Watch mode** - Continuous background monitoring
- **White-label reports** - Branded reports for clients
- **Parallel processing** - Fast batch analysis
- **Progress resume** - Continue interrupted analyses
- **Traffic capture analysis** - Find opportunities to steal competitor traffic

> **New to the tool?** See [INSTRUCTIONS.md](INSTRUCTIONS.md) for step-by-step workflows.

## Folder map: what is public and what is private

**Pipeline (committed, safe on GitHub)**

| File | What it does |
|---|---|
| `youtube_analyzer.py` | Command line entry point; the code lives in the `ytanalyzer/` package (about 30 modules: `fetch`, `metrics`, `exports`, `sync`, `recommend`, `cli`, ...) |
| `transcript_fetcher.py` | Fetches and searches video captions |
| `google_search_analyzer.py`, `news_signal_scanner.py`, `topic_signals.py`, `topic_review.py`, `reddit_topic_scanner.py`, `reddit_story_scan.py` | Topic and demand research |
| `my_channel_analytics.py`, `sync_my_channel.py` | Your own channel's analytics (needs your own OAuth credentials) |
| `clip_picker.py` | Proposes Shorts moments from a long video's captions; optional local LLM (Ollama) and ffmpeg render |
| `clip_dashboard.py` | Builds a local review page for the proposed moments |
| `short_maker.py` | Renders chosen moments as finished Shorts: smoothed face-follow 9:16 crop that keeps the source's lower thirds out of frame, hook card in a band above the head, jump cuts on dead air, word-highlight captions inside the Shorts safe zone, alternating punch-in at cuts, plus a .txt with title, description and hashtags |
| `config.yaml`, `niche_config.yaml`, `.env.example`, `requirements.txt` | Generic settings and templates |

**Private (git-ignored, never commit)**

| Path | Why |
|---|---|
| `.env`, `client_secret.json`, `youtube_oauth_token.json`, `cookies.txt` | API keys, OAuth credentials, login cookies |
| `my_channels.yaml` | Your channel, competitor list and priority channels |
| `output/` | All analysis results, databases, clip proposals and the review dashboard |
| `content_drafts/`, `private/` | Draft scripts, own-channel video lists, a second channel's workspace, scratch files |
| `*.db`, `vectors.db` | Local databases |

Rule of thumb: if a file names your channels, lists your videos or holds a credential, it belongs in the private list. Check with `git add -n -A .` before any commit.

### Shorts clip workflow

```bash
python clip_picker.py VIDEO_ID --llm          # propose moments (needs Ollama running)
python clip_picker.py --batch ids.txt --llm   # many videos, resumable
python clip_dashboard.py                      # build output/clips/dashboard.html, review in browser
python short_maker.py VIDEO_ID --pick 1 3     # finished 9:16 Shorts: download, face-follow crop, burned-in word captions
python short_maker.py --decisions clip_decisions.json   # everything marked Keep in the dashboard
python short_maker.py VIDEO_ID --pick 2 --force --out scratch   # re-render elsewhere; also --no-cuts, --no-punch, --hook-secs 3, --progress-bar
```

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Set API key (free from Google Cloud Console)
echo "YOUTUBE_API_KEY=your_key" > .env

# Basic analysis
python youtube_analyzer.py @competitor_channel

# Full analysis with competitor discovery
python youtube_analyzer.py @competitor_channel --network

# Generate video ideas
python youtube_analyzer.py @competitor_channel --ideas

# Build content calendar
python youtube_analyzer.py @competitor_channel --calendar

# Track keyword rankings
python youtube_analyzer.py @competitor_channel --keywords "python tutorial" "coding"

# Run as API server
python youtube_analyzer.py --api --port 8080

# Check for trend alerts
python youtube_analyzer.py --alerts

# Continuous watch mode (monitors every 6 hours)
python youtube_analyzer.py --watch --interval 6

# Compare this week vs last week
python youtube_analyzer.py @competitor_channel --compare

# Get tag optimization suggestions
python youtube_analyzer.py @competitor_channel --tags

# White-label report for clients
python youtube_analyzer.py @competitor_channel --white-label "Acme Analytics" --logo "https://example.com/logo.png"

# Batch analysis with parallel processing (3x faster)
python youtube_analyzer.py --batch channels.txt --parallel --workers 4

# Resume interrupted analysis
python youtube_analyzer.py @competitor_channel --resume

# Compare your channel vs competitor (find traffic opportunities)
python youtube_analyzer.py @YourChannel --vs @CompetitorChannel

# AI-powered recommendations (requires ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY)
python youtube_analyzer.py @YourChannel --vs @CompetitorChannel --ai

# Interactive mode
python youtube_analyzer.py --interactive
```

## Features

### Core Analytics
| Feature | Description |
|---------|-------------|
| **Virality Score** | Views / subscribers × time factor. Score > 1.0 = viral |
| **Channel Health Score** | 0-100 score with A+ to F grade |
| **Momentum Score** | Combines recent activity, virality, trend direction |
| **Title Pattern Analysis** | Detects questions, numbers, emotional words, hooks |
| **Revenue Estimates** | CPM-based earnings (low/mid/high range) |
| **Shorts vs Long-form** | Separate analytics for each content format |
| **Engagement Metrics** | Like ratio, comment ratio, engagement rate |
| **Retention Estimation** | Estimated watch time based on duration and engagement |
| **Upload Consistency** | Score based on upload frequency regularity |

### Strategic Intelligence
| Feature | Description |
|---------|-------------|
| **Video Idea Generator** | Content suggestions based on gaps, trends, formulas |
| **Content Calendar Builder** | Optimal posting schedule with best days/times |
| **Title A/B Suggestions** | Optimized title alternatives for any video |
| **Description Template** | Build templates from top-performing patterns |
| **Thumbnail Analysis** | Detect patterns in successful thumbnails |
| **Tag Optimization** | Discover high-performing tags from viral videos |
| **Trend Velocity** | Identify exploding content in first 48 hours |
| **Video Lifecycle Analysis** | Track performance by content age |

### Competitive Intelligence
| Feature | Description |
|---------|-------------|
| **AI-Powered Recommendations** | Get video ideas, strategy, and growth plans from Claude/GPT-4/Gemini (--ai) |
| **Traffic Capture Analysis** | Find opportunities to steal competitor traffic (--vs) |
| **Competitor Discovery** | Automatically find competing channels (--network) |
| **Video Network Map** | See which channels share your content neighborhood |
| **Audience Overlap Score** | Estimate shared audience with competitors |
| **Channel Comparison** | Side-by-side metrics for multiple channels |
| **Keyword Gap Analysis** | Keywords competitor ranks for that you don't |
| **Viral Content Gaps** | Their viral videos you haven't covered |
| **Content Saturation Index** | Measure topic crowding in your niche |
| **Collaboration ROI** | Compare collab vs solo content performance |
| **Niche Benchmarks** | Compare against category averages |

### Tracking & Monitoring
| Feature | Description |
|---------|-------------|
| **Keyword Rank Tracking** | Monitor search positions over time |
| **Trend Alerts** | Get notified for new videos, trending, viral content |
| **Watch Mode** | Continuous background monitoring with configurable intervals |
| **Time Comparison** | Compare this week vs last week performance |
| **Playlist Analysis** | Track playlist performance |
| **Historical Tracking** | Monitor channel growth over time |
| **Incremental Updates** | Only fetch new videos since last run |
| **Progress Resume** | Continue interrupted analyses where you left off |

### Automation & Integration
| Feature | Description |
|---------|-------------|
| **API Server Mode** | REST API for programmatic access |
| **Watch Mode** | Continuous background monitoring with alerts |
| **Parallel Processing** | Process multiple channels simultaneously |
| **Discord Webhooks** | Get alerts in Discord |
| **Slack Webhooks** | Get alerts in Slack |
| **Scheduled Reports** | Automated report generation |
| **Cron Setup Helper** | Easy automated scheduling |
| **Interactive CLI** | Menu-driven interface |
| **YAML Config** | Persistent configuration |

### Data Export
| Feature | Description |
|---------|-------------|
| **HTML Dashboard** | Interactive charts with Chart.js (no server needed - just open in browser) |
| **White-label Reports** | Custom branded reports for clients |
| **PDF Report** | Professional formatted reports |
| **RSS Feed** | Subscribe to channel analytics |
| **CSV** | All video data in flat format |
| **JSON** | Full data with analytics |
| **Excel** | Multi-sheet report |
| **SQLite** | Queryable database |
| **Markdown** | Human-readable report |

## Installation

```bash
git clone https://github.com/yourusername/youtube-competitive-content-analysis.git
cd youtube-competitive-content-analysis
pip install -r requirements.txt
```

### Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| `google-api-python-client` | YouTube Data API | Yes |
| `tqdm` | Progress bars | No |
| `python-dotenv` | .env file support | No |
| `openpyxl` | Excel export | No |
| `pyyaml` | Config file support | No |
| `reportlab` | PDF export | No |

## API Key Setup

The YouTube Data API is **free** with 10,000 units/day quota.

### Quick Links

| Step | Direct Link |
|------|-------------|
| Create Project | https://console.cloud.google.com/projectcreate |
| Enable YouTube API | https://console.cloud.google.com/apis/library/youtube.googleapis.com |
| Create API Key | https://console.cloud.google.com/apis/credentials |

### Setup Steps

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable YouTube Data API v3
4. Create an API key
5. Save to `.env` file:
```bash
echo "YOUTUBE_API_KEY=your_api_key_here" > .env
```

## Command Reference

| Argument | Description |
|----------|-------------|
| `channel` | YouTube channel ID, @handle, or URL |
| `--api-key` | YouTube API key (or use env var) |
| `--output`, `-o` | Output directory (default: `./output`) |
| `--format`, `-f` | Output formats: csv, json, excel, sqlite, html, markdown, pdf, rss |
| `--since` | Only videos after date (YYYY-MM-DD) |
| `--until` | Only videos before date (YYYY-MM-DD) |
| `--limit` | Maximum number of videos to fetch |
| `--min-views` | Minimum view count filter |
| `--batch` | File with channel list (one per line) |
| `--incremental` | Only fetch new videos since last run |
| `--thumbnails` | Download thumbnails of top videos |
| `--network` | Analyze video network & discover competitors |
| `--vs COMPETITOR` | Analyze traffic capture opportunities vs competitor |
| `--ideas` | Generate video ideas based on analysis |
| `--calendar` | Generate content calendar |
| `--keywords` | Track keyword rankings (space-separated) |
| `--pdf` | Generate PDF report |
| `--rss` | Generate RSS feed |
| `--api` | Run as API server |
| `--port` | API server port (default: 8080) |
| `--alerts` | Check watchlist for trend alerts |
| `--watch` | Continuous monitoring mode |
| `--interval` | Watch mode interval in hours (default: 6) |
| `--compare` | Compare this week vs last week |
| `--tags` | Optimize tags based on top performers |
| `--white-label` | Company name for white-label report |
| `--logo` | Logo URL for white-label reports |
| `--primary-color` | Primary color for white-label (default: #667eea) |
| `--parallel` | Process batch channels in parallel |
| `--workers` | Number of parallel workers (default: 3) |
| `--resume` | Resume interrupted analysis |
| `--clear-progress` | Clear saved progress |
| `--interactive`, `-i` | Interactive menu mode |
| `--config` | Config file path (default: config.yaml) |

## Usage Examples

### Basic Analysis
```bash
python youtube_analyzer.py @mkbhd
python youtube_analyzer.py https://www.youtube.com/@veritasium
```

### Generate Video Ideas
```bash
python youtube_analyzer.py @channel --ideas

# Output:
# GAP_BASED:
#   • Revisit 'Python' with updated information
#     Title: "The Ultimate Guide to Python (2024)"
# TREND_BASED:
#   • Combine 'react' with 'typescript'
#     Title: "How React Changes Everything About Typescript"
```

### Build Content Calendar
```bash
python youtube_analyzer.py @channel --calendar

# Output:
# Suggested posting days: Tuesday, Thursday, Saturday
# Suggested frequency: 3 videos/week
#
# Upcoming schedule:
#   2024-01-15 (Tuesday) at 09:00 UTC
#   2024-01-17 (Thursday) at 12:00 UTC
```

### Track Keyword Rankings
```bash
python youtube_analyzer.py @channel --keywords "python tutorial" "react hooks" "typescript"

# Output:
# In top 10: 2/3
# In top 50: 3/3
#   'python tutorial': Position 5
#   'react hooks': Position 12
#   'typescript': Position 3
```

### Run API Server
```bash
python youtube_analyzer.py --api --port 8080

# Endpoints:
# GET /api/health
# GET /api/analyze?channel=@handle
# GET /api/channels
```

### Trend Alerts
```bash
# Add channels to config.yaml watchlist first
python youtube_analyzer.py --alerts

# Output:
# 🆕 NEW: MrBeast posted "I Gave Away $1M" (2.5h ago, 5.2M views)
# 📈 TRENDING: "New Video Title" by TechChannel is exploding!
# 🔥 VIRAL: "Viral Video" by Creator (virality: 3.45)
```

### Batch Comparison
```bash
# Create competitors.txt:
# @mkbhd
# @veritasium
# @LinusTechTips

python youtube_analyzer.py --batch competitors.txt --output ./comparison

# Parallel batch processing (3x faster with 4 workers)
python youtube_analyzer.py --batch competitors.txt --parallel --workers 4
```

### Watch Mode (Continuous Monitoring)
```bash
# Monitor watchlist channels every 6 hours
python youtube_analyzer.py --watch

# Custom interval (every 2 hours)
python youtube_analyzer.py --watch --interval 2

# Press Ctrl+C to stop gracefully
```

### Time Comparison
```bash
python youtube_analyzer.py @channel --compare

# Output:
# This Week vs Last Week:
#   Views:       +23.5% (125K → 154K)
#   Videos:      3 → 4
#   Avg Views:   +15.2%
#   Engagement:  +0.3%
#   Trend:       ↗️ Growing
```

### Tag Optimization
```bash
python youtube_analyzer.py @channel --tags

# Output:
# Top recommended tags (15):
#   • python
#   • tutorial
#   • programming
#   ...
#
# High-performing tags (from viral videos):
#   • beginner (score: 8.5)
#   • 2024 (score: 7.2)
```

### White-label Reports
```bash
# Basic white-label
python youtube_analyzer.py @channel --white-label "Acme Analytics"

# With logo and custom colors
python youtube_analyzer.py @channel \
  --white-label "Acme Analytics" \
  --logo "https://example.com/logo.png" \
  --primary-color "#FF5722"
```

### Resume Interrupted Analysis
```bash
# Start analysis with resume enabled
python youtube_analyzer.py @large_channel --resume

# If interrupted, run the same command to continue
python youtube_analyzer.py @large_channel --resume

# Clear saved progress
python youtube_analyzer.py --clear-progress
```

### Traffic Capture Analysis (You vs Competitor)
```bash
# Find opportunities to capture competitor's traffic
python youtube_analyzer.py @YourChannel --vs @CompetitorChannel

# Output includes:
# - Keyword gaps (topics they rank for, you don't)
# - Viral content gaps (their hits you haven't covered)
# - Tag opportunities (their winning tags)
# - Title pattern comparison
# - Prioritized action plan

# Full analysis with all features
python youtube_analyzer.py @YourChannel --vs @Competitor --ideas --tags --compare
```

### AI-Powered Recommendations

Get personalized video ideas, content strategy, and growth plans using AI.

```bash
# Add one of these API keys to your .env file:
# ANTHROPIC_API_KEY=sk-ant-xxxxx  (Claude - recommended)
# OPENAI_API_KEY=sk-xxxxx         (GPT-4)
# GEMINI_API_KEY=xxxxx            (Google Gemini)

# AI analysis for single channel
python youtube_analyzer.py @YourChannel --network --ai

# AI analysis with competitor comparison (most powerful)
python youtube_analyzer.py @YourChannel --vs @Competitor --ai

# Output includes:
# - 5-7 specific video topic ideas with titles
# - Content strategy recommendations
# - Title & thumbnail optimization tips
# - Quick wins (immediate improvements)
# - 90-day growth plan
```

**No API key?** The `--ai` flag generates a prompt file you can use with Claude Code or any AI chat:
```bash
python youtube_analyzer.py @YourChannel --vs @Competitor --ai
# Creates: output/comparisons/ai_analysis_prompt.md

# Use with Claude Code:
cat "output/comparisons/ai_analysis_prompt.md" | claude
```

## Configuration File

Create `config.yaml`:

```yaml
# Default output directory
output_dir: ./output

# Channels to monitor for alerts
watchlist:
  - @competitor1
  - @competitor2
  - @competitor3

# Webhook notifications
webhooks:
  discord: https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
  slack: https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Default filters
defaults:
  min_views: 1000
  limit: 500

# CPM overrides by category (USD per 1000 views)
cpm:
  Science & Technology: 6.0
  Education: 5.0
  Gaming: 3.0

# Custom scoring weights (must sum to 1.0)
scoring:
  views: 0.3
  engagement: 0.2
  virality: 0.3
  recency: 0.2
```

## Understanding the Metrics

### Channel Health Score (0-100)

| Component | Max Points | Based On |
|-----------|------------|----------|
| Engagement | 25 | Average engagement rate |
| Virality | 25 | Average virality score |
| Consistency | 25 | Upload schedule regularity |
| Growth | 25 | Percentage of viral videos |

### Momentum Score (0-100)

| Component | Max Points | Based On |
|-----------|------------|----------|
| Activity | 25 | Recent upload frequency |
| Virality | 25 | Recent video performance |
| Trend | 25 | Performance direction |
| Engagement | 25 | Recent engagement rates |

### Trend Velocity Status

| Status | Meaning | Timeframe |
|--------|---------|-----------|
| Exploding | Exceptional velocity | First 48h |
| Trending | High velocity | First 48h |
| Gaining | Moderate velocity | First 48h |
| Hot | Still performing well | First week |
| Evergreen | Consistent long-term | 7+ days |
| Dormant | Low activity | 7+ days |

### Revenue Estimates

Based on category-specific CPM:
- **Low estimate**: 50% of avg CPM × 50% monetized views
- **Mid estimate**: Avg CPM × 55% monetized views
- **High estimate**: 2× avg CPM × 55% monetized views

## API Server

Run the tool as a REST API:

```bash
python youtube_analyzer.py --api --port 8080
```

### Endpoints

**GET /api/health**
```json
{"status": "ok", "timestamp": "2024-01-15T10:30:00"}
```

**GET /api/analyze?channel=@mkbhd**
```json
{
  "channel": {"title": "MKBHD", "subscriber_count": 18000000},
  "analytics": {"overview": {...}, "health_score": {...}},
  "video_count": 50,
  "timestamp": "2024-01-15T10:30:00"
}
```

**GET /api/channels**
```json
{"channels": ["@mkbhd", "@veritasium"], "count": 2}
```

## Viewing the Dashboard

The HTML dashboard is a **static file** - no server required:

```bash
# Just open in your browser
open output/ChannelName/dashboard.html         # macOS
start output\ChannelName\dashboard.html        # Windows
xdg-open output/ChannelName/dashboard.html     # Linux

# Or drag-and-drop the file into your browser
```

> **Note**: Requires internet connection for Chart.js to load from CDN. All other data is embedded in the file.

## Output Files

Organized by channel for easy management:

```
output/
├── ChannelA/                          # Your channel folder
│   ├── dashboard.html                 # Interactive HTML dashboard
│   ├── analysis.json                  # Full analytics + competitors
│   ├── videos.csv                     # All video data
│   ├── report.xlsx                    # Excel workbook
│   ├── report.md                      # Markdown report
│   ├── report.pdf                     # PDF report (if --pdf)
│   ├── feed.xml                       # RSS feed (if --rss)
│   ├── whitelabel_report.html         # White-label (if --white-label)
│   ├── data.db                        # SQLite database
│   └── thumbnails/                    # Downloaded thumbnails
│
├── ChannelB/                          # Competitor channel folder
│   ├── dashboard.html
│   ├── analysis.json
│   └── ...
│
└── comparisons/                      # All comparison reports
    ├── ChannelA_vs_ChannelB.html      # Traffic capture analysis
    ├── ChannelA_vs_ChannelB.json
    └── batch_comparison.md            # Batch comparison table
```

## API Quota

YouTube Data API: **10,000 units/day** (free)

| Operation | Cost |
|-----------|------|
| Channel info | 1 unit |
| 50 video IDs | 1 unit |
| 50 video details | 1 unit |
| Search (--network) | 100 units |
| Comments | 1 unit per 100 |

**Standard analysis**: ~41 units per 1,000 videos
**With --network**: Additional ~300-500 units

## Troubleshooting

### "API Error: 403"
- Verify API key is correct
- Check YouTube Data API v3 is enabled
- May have exceeded daily quota (resets at midnight Pacific)

### "Channel not found"
- Try using the full URL instead of @handle
- Channel may be private or terminated

### Missing features
```bash
pip install openpyxl    # Excel export
pip install pyyaml      # Config file
pip install reportlab   # PDF export
pip install tqdm        # Progress bars
```

## License

MIT License - see [LICENSE](LICENSE)

## Disclaimer

This tool uses the official YouTube Data API and complies with YouTube's Terms of Service. Use responsibly for legitimate competitive analysis and research.