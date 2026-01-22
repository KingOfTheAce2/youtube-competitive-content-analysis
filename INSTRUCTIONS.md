# YouTube Competitive Analysis - Step-by-Step Instructions

This guide shows you exactly how to analyze your channel, competitor channels, and find opportunities to capture traffic.

## Prerequisites

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up your API key
echo "YOUTUBE_API_KEY=your_api_key_here" > .env
```

Get your free API key: https://console.cloud.google.com/apis/credentials

---

## Important: PowerShell Users

**If you're using PowerShell on Windows**, you must quote channel handles with `@`:

```powershell
# WRONG - PowerShell interprets @ as special character
python youtube_analyzer.py @YourChannel

# CORRECT - Use quotes
python youtube_analyzer.py "@YourChannel"
```

Alternatively, use the full URL:
```powershell
python youtube_analyzer.py "https://www.youtube.com/@YourChannel"
```

> **Note**: This applies to all commands in this guide. Always quote `@handles` in PowerShell.

---

## Part 1: Deep Analysis of Your Own Channel

### Step 1.1: Basic Analysis
```bash
python youtube_analyzer.py @YourChannelHandle
```

This creates:
- `output/YourChannel_dashboard.html` - Visual dashboard
- `output/YourChannel_analysis.json` - Full data
- `output/YourChannel_videos.csv` - All video data

### Step 1.2: Full Deep Analysis
```bash
python youtube_analyzer.py @YourChannelHandle \
  --network \
  --ideas \
  --calendar \
  --tags \
  --compare
```

| Flag | What it does |
|------|--------------|
| `--network` | Discovers competitors in your niche |
| `--ideas` | Generates video ideas based on gaps |
| `--calendar` | Suggests optimal posting schedule |
| `--tags` | Shows best-performing tags |
| `--compare` | Compares this week vs last week |

### Step 1.3: Track Your Keyword Rankings
```bash
python youtube_analyzer.py @YourChannelHandle \
  --keywords "your main topic" "another topic" "third topic"
```

### Step 1.4: Generate All Reports
```bash
python youtube_analyzer.py @YourChannelHandle \
  --network --ideas --calendar --tags --compare \
  --pdf --rss \
  -f csv json excel sqlite html markdown
```

---

## Part 2: Analyze a Competitor Channel

### Step 2.1: Basic Competitor Analysis
```bash
python youtube_analyzer.py @CompetitorHandle
```

### Step 2.2: Deep Competitor Analysis
```bash
python youtube_analyzer.py @CompetitorHandle \
  --network \
  --ideas \
  --tags
```

This shows you:
- Their health score and metrics
- Who they compete with (your potential competitors too)
- What video ideas work in their space
- Which tags drive their traffic

### Step 2.3: Analyze Multiple Competitors

Create `competitors.txt`:
```
@Competitor1
@Competitor2
@Competitor3
```

Run batch analysis:
```bash
# Sequential
python youtube_analyzer.py --batch competitors.txt

# Parallel (3x faster)
python youtube_analyzer.py --batch competitors.txt --parallel --workers 4
```

This generates `comparison.md` with side-by-side metrics.

---

## Part 3: Cross-Reference Analysis (You vs Competitor)

### Step 3.1: Traffic Capture Analysis

**This is the key command to find opportunities to steal competitor traffic:**

```bash
python youtube_analyzer.py @YourChannel --vs @CompetitorChannel
```

This analyzes:
- **Keyword gaps**: Keywords they rank for that you don't
- **Viral gaps**: Their viral videos you haven't covered
- **Tag opportunities**: Tags that work for them but you don't use
- **Title patterns**: What makes their titles work
- **Action plan**: Prioritized steps to capture their traffic

Output: `output/YourChannel_vs_CompetitorChannel_traffic.json`

### Step 3.2: Full Cross-Reference with All Features
```bash
python youtube_analyzer.py @YourChannel \
  --vs @CompetitorChannel \
  --ideas \
  --tags \
  --compare \
  --network
```

### Step 3.3: Analyze Against Multiple Competitors

Run separately for each competitor:
```bash
python youtube_analyzer.py @YourChannel --vs @Competitor1
python youtube_analyzer.py @YourChannel --vs @Competitor2
python youtube_analyzer.py @YourChannel --vs @Competitor3
```

Or create a script:
```bash
#!/bin/bash
for comp in @Competitor1 @Competitor2 @Competitor3; do
  python youtube_analyzer.py @YourChannel --vs $comp
done
```

---

## Part 4: Complete Workflow Example

Here's a full workflow to maximize insights:

```bash
# Step 1: Deep analysis of your channel
python youtube_analyzer.py @YourChannel \
  --network --ideas --calendar --tags --compare \
  -o ./output/my_channel

# Step 2: Identify top 3 competitors from the network analysis
# (Check the output from Step 1)

# Step 3: Analyze each competitor
python youtube_analyzer.py @Competitor1 --ideas --tags -o ./output/comp1
python youtube_analyzer.py @Competitor2 --ideas --tags -o ./output/comp2
python youtube_analyzer.py @Competitor3 --ideas --tags -o ./output/comp3

# Step 4: Cross-reference against each
python youtube_analyzer.py @YourChannel --vs @Competitor1 -o ./output/vs_comp1
python youtube_analyzer.py @YourChannel --vs @Competitor2 -o ./output/vs_comp2
python youtube_analyzer.py @YourChannel --vs @Competitor3 -o ./output/vs_comp3

# Step 5: Set up monitoring
python youtube_analyzer.py --watch --interval 6
```

---

## Part 5: Interpreting Results

### Traffic Analysis Output

When you run `--vs`, look for:

```
COMPETITOR TRAFFIC CAPTURE ANALYSIS
============================================================

Summary:
   Keyword gaps found: 25        <- Topics to create content on
   Tag opportunities: 18         <- Tags to add to your videos
   Viral content gaps: 8         <- Their viral videos you haven't covered
   Video ideas generated: 12     <- Ready-to-use video ideas

Keyword Gaps (competitor ranks, you don't):
   'tutorial' - opportunity: high     <- CREATE CONTENT ON THIS
   'beginner' - opportunity: high
   '2024' - opportunity: medium

Viral Content You Haven't Covered:
   "How to X in 5 Minutes"           <- MAKE YOUR VERSION
     Views: 1.2M | Virality: 2.45

Action Plan:
   [1] Create videos on 8 topics competitor went viral on
   [2] Use more numbers in titles (they: 65%, you: 20%)
   [3] Adopt 15 high-performing tags
```

### What to Do With Results

| Finding | Action |
|---------|--------|
| High keyword gaps | Create videos targeting those keywords |
| Viral content gaps | Make your own version of their viral topics |
| Tag opportunities | Add these tags to your new videos |
| Title pattern differences | Adjust your titles to match winning patterns |
| Lower virality ratio | Study their thumbnails and hooks |

---

## Part 6: Continuous Monitoring

### Set Up Watch Mode
```bash
# Add competitors to config.yaml
watchlist:
  - @Competitor1
  - @Competitor2
  - @YourChannel

# Optional: Add webhooks
webhooks:
  discord: https://discord.com/api/webhooks/YOUR_URL
  slack: https://hooks.slack.com/services/YOUR/URL
```

Run continuous monitoring:
```bash
# Check every 6 hours
python youtube_analyzer.py --watch

# Check every 2 hours
python youtube_analyzer.py --watch --interval 2
```

### Get Alerts on Demand
```bash
python youtube_analyzer.py --alerts
```

---

## Part 7: AI-Powered Analysis

Get personalized video ideas, content strategy, and growth recommendations using AI.

### Setup (Choose One Provider)

Add one of these API keys to your `.env` file:

```bash
# Option 1: Anthropic Claude (recommended)
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Option 2: OpenAI GPT-4
OPENAI_API_KEY=sk-xxxxx

# Option 3: Google Gemini
GEMINI_API_KEY=xxxxx
```

### Step 7.1: AI Analysis for Single Channel
```bash
python youtube_analyzer.py @YourChannel --network --ai
```

### Step 7.2: AI Analysis with Competitor Comparison
```bash
python youtube_analyzer.py @YourChannel --vs @Competitor --ai
```

This generates:
- **Video Topic Ideas** (5-7 specific ideas with titles)
- **Content Strategy Recommendations**
- **Title & Thumbnail Optimization** tips
- **Quick Wins** (immediate improvements)
- **90-Day Growth Plan**

Output: `output/YourChannel/ai_recommendations.md`

### No API Key? Use Claude Code

If you don't have an API key, the `--ai` flag will generate a prompt file:

```bash
python youtube_analyzer.py @YourChannel --vs @Competitor --ai
# Creates: output/comparisons/ai_analysis_prompt.md
```

Then use with Claude Code:
```bash
cat "output/comparisons/ai_analysis_prompt.md" | claude
```

Or copy the prompt into ChatGPT, Claude, or any AI assistant.

---

## Quick Reference

| Goal | Command |
|------|---------|
| Analyze your channel | `python youtube_analyzer.py @YourChannel` |
| Deep analysis with ideas | `python youtube_analyzer.py @YourChannel --network --ideas --tags` |
| Analyze competitor | `python youtube_analyzer.py @Competitor` |
| Compare you vs competitor | `python youtube_analyzer.py @YourChannel --vs @Competitor` |
| **AI-powered comparison** | `python youtube_analyzer.py @YourChannel --vs @Competitor --ai` |
| Batch compare | `python youtube_analyzer.py --batch channels.txt --parallel` |
| Monitor competitors | `python youtube_analyzer.py --watch` |
| Track keywords | `python youtube_analyzer.py @YourChannel --keywords "topic1" "topic2"` |
| Week comparison | `python youtube_analyzer.py @YourChannel --compare` |
| Generate PDF report | `python youtube_analyzer.py @YourChannel --pdf` |
| White-label report | `python youtube_analyzer.py @YourChannel --white-label "Company Name"` |

---

## Output Files Reference

After running analysis, check these files:

```
output/
├── YourChannel_dashboard.html          # Open in browser - visual charts
├── YourChannel_analysis.json           # Full data for programmatic use
├── YourChannel_videos.csv              # All videos in spreadsheet format
├── YourChannel_vs_Competitor_traffic.json  # Traffic capture opportunities
├── comparison.md                       # Side-by-side channel comparison
```

**Tip**: Start with the HTML dashboard for a quick overview, then dive into the JSON files for detailed data.
