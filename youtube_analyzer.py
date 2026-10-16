#!/usr/bin/env python3
"""
YouTube Competitive Content Analysis Tool - Ultimate Edition

A powerful tool for analyzing YouTube channels to gain competitive insights,
identify content opportunities, and develop data-driven content strategies.

=== API KEY SETUP (FREE) ===
The YouTube Data API is free with 10,000 units/day quota.

Quick links:
  - Create project: https://console.cloud.google.com/projectcreate
  - Enable API:     https://console.cloud.google.com/apis/library/youtube.googleapis.com
  - Get API key:    https://console.cloud.google.com/apis/credentials

=== FEATURES ===
- Virality score & channel health score
- Title pattern analysis & hook scoring
- Shorts vs Long-form analytics
- Channel comparison & content gap analysis
- Historical trend tracking & growth rates
- Estimated revenue calculations
- Video series & collaboration detection
- Upload consistency scoring
- Seasonality analysis
- HTML dashboard with interactive charts
- Discord/Slack webhook alerts
- YAML config file support
- Multiple export formats (CSV, JSON, Excel, SQLite, Markdown, HTML)
- Interactive CLI mode

License: MIT
"""

# The implementation now lives in the ytanalyzer/ package. This file stays as the command line
# entry point and re-exports every name so existing imports (from youtube_analyzer import ...) keep working.
from ytanalyzer.common import *
from ytanalyzer.ai import *
from ytanalyzer.alerts import *
from ytanalyzer.analysis_tools import *
from ytanalyzer.analytics import *
from ytanalyzer.analyze import *
from ytanalyzer.audience import *
from ytanalyzer.benchmarks import *
from ytanalyzer.comments import *
from ytanalyzer.content_ideas import *
from ytanalyzer.discovery import *
from ytanalyzer.excel import *
from ytanalyzer.exports import *
from ytanalyzer.exports_extra import *
from ytanalyzer.fetch import *
from ytanalyzer.growth import *
from ytanalyzer.interactive import *
from ytanalyzer.metrics import *
from ytanalyzer.notify import *
from ytanalyzer.progress import *
from ytanalyzer.recommend import *
from ytanalyzer.recommend_titles import *
from ytanalyzer.scheduled import *
from ytanalyzer.server import *
from ytanalyzer.status import *
from ytanalyzer.store import *
from ytanalyzer.sync import *
from ytanalyzer.traffic import *
from ytanalyzer.wizard import *
from ytanalyzer.cli import main


if __name__ == '__main__':
    main()
