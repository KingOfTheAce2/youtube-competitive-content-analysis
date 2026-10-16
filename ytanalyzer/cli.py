"""Command line entry point."""

from .common import *
from .ai import get_ai_recommendations, save_ai_recommendations
from .alerts import check_trend_alerts, format_alert_message, run_watch_mode
from .analysis_tools import compare_time_periods, format_time_comparison, generate_white_label_html, optimize_tags, process_batch_parallel
from .analyze import analyze_channel, process_batch
from .content_ideas import build_content_calendar, generate_video_ideas
from .discovery import track_keyword_rankings
from .fetch import resolve_channel_id
from .growth import analyze_growth_quality, format_growth_quality
from .interactive import interactive_mode
from .notify import send_discord_webhook, send_slack_webhook
from .progress import analyze_channel_with_resume, clear_progress
from .recommend import discover_and_save_competitors, format_gap_analysis, generate_gap_analysis
from .recommend_titles import format_recommendations_with_titles, generate_recommendations_html, generate_recommendations_with_titles
from .server import run_api_server
from .status import format_status, get_status
from .store import add_competitor_to_config, get_competitive_db_path, get_my_channel_id, list_competitors, migrate_competitive_database, remove_competitor, set_my_channel
from .sync import sync_all, sync_comments, take_snapshot
from .traffic import analyze_competitor_traffic_opportunities, format_traffic_analysis, generate_traffic_analysis_html
from .wizard import format_sync_summary, run_init_wizard

# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='YouTube Competitive Analysis Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('channel', nargs='?', help='Channel to analyze')
    parser.add_argument('--api-key', help='YouTube API key')
    parser.add_argument('--output', '-o', default='./output', help='Output directory')
    parser.add_argument('--format', '-f', nargs='+',
                        choices=['csv', 'json', 'excel', 'sqlite', 'html', 'markdown', 'pdf', 'rss'],
                        default=['csv', 'json', 'excel', 'sqlite', 'html', 'markdown'])
    parser.add_argument('--since', help='Videos after date (YYYY-MM-DD)')
    parser.add_argument('--until', help='Videos before date (YYYY-MM-DD)')
    parser.add_argument('--limit', type=int, help='Max videos')
    parser.add_argument('--min-views', type=int, help='Min view count')
    parser.add_argument('--batch', help='File with channel list')
    parser.add_argument('--incremental', action='store_true', help='Only new videos')
    parser.add_argument('--thumbnails', action='store_true', help='Download thumbnails')
    parser.add_argument('--network', action='store_true', help='Analyze video network & discover competitors')
    parser.add_argument('--vs', metavar='COMPETITOR', help='Analyze traffic capture opportunities vs a competitor')
    parser.add_argument('--interactive', '-i', action='store_true', help='Interactive mode')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--pdf', action='store_true', help='Generate PDF report')
    parser.add_argument('--rss', action='store_true', help='Generate RSS feed')
    parser.add_argument('--api', action='store_true', help='Run as API server')
    parser.add_argument('--port', type=int, default=8080, help='API server port (default: 8080)')
    parser.add_argument('--alerts', action='store_true', help='Check watchlist for trend alerts')
    parser.add_argument('--ideas', action='store_true', help='Generate video ideas')
    parser.add_argument('--calendar', action='store_true', help='Generate content calendar')
    parser.add_argument('--keywords', nargs='+', help='Track keyword rankings')
    parser.add_argument('--watch', action='store_true', help='Continuous monitoring mode')
    parser.add_argument('--interval', type=float, default=6.0, help='Watch mode interval in hours (default: 6)')
    parser.add_argument('--compare', action='store_true', help='Compare this week vs last week')
    parser.add_argument('--tags', action='store_true', help='Optimize tags based on top performers')
    parser.add_argument('--white-label', dest='white_label', metavar='COMPANY', help='Generate white-label report with company name')
    parser.add_argument('--logo', help='Logo URL for white-label reports')
    parser.add_argument('--primary-color', dest='primary_color', default='#667eea', help='Primary color for white-label')
    parser.add_argument('--ai', action='store_true', help='Generate AI-powered recommendations (uses ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY)')
    parser.add_argument('--parallel', action='store_true', help='Process batch channels in parallel')
    parser.add_argument('--workers', type=int, default=3, help='Number of parallel workers (default: 3)')
    parser.add_argument('--resume', action='store_true', help='Resume interrupted analysis')
    parser.add_argument('--clear-progress', dest='clear_progress', action='store_true', help='Clear saved progress')

    # === COMPETITIVE ANALYSIS COMMANDS ===
    parser.add_argument('--set-my-channel', dest='set_my_channel', metavar='CHANNEL',
                        help='Set your channel as the home base for competitive analysis')
    parser.add_argument('--add-competitor', dest='add_competitor', metavar='CHANNEL',
                        help='Add a seed competitor to track')
    parser.add_argument('--remove-competitor', dest='remove_competitor', nargs='+', metavar='NAME',
                        help='Remove competitor(s) by name (partial match supported)')
    parser.add_argument('--discover-competitors', dest='discover_competitors', action='store_true',
                        help='Discover new competitors from your channel and seed competitors')
    parser.add_argument('--list-competitors', dest='list_competitors', action='store_true',
                        help='List all tracked competitors')
    parser.add_argument('--sync', action='store_true',
                        help='Sync my channel + all competitors (incremental, only new videos)')
    parser.add_argument('--sync-comments', dest='sync_comments', action='store_true',
                        help='Sync comments only, for the channels under comment_sync in my_channels.yaml')
    parser.add_argument('--force-refresh', dest='force_refresh', action='store_true',
                        help='Force re-fetch everything during sync')
    parser.add_argument('--snapshot', action='store_true',
                        help='Capture current view/like counts for trend tracking')
    parser.add_argument('--recommend', action='store_true',
                        help='Generate top ranked video topic recommendations')
    parser.add_argument('--top-n', dest='top_n', type=int, default=20,
                        help='Number of recommendations to show (default: 20)')
    parser.add_argument('--growth-quality', dest='growth_quality', action='store_true',
                        help='Check whether recent view growth is organic or algorithm-driven (views vs engagement/subscriber trend)')
    parser.add_argument('--gap-analysis', dest='gap_analysis', action='store_true',
                        help='Generate full gap analysis report vs competitors')
    parser.add_argument('--status', action='store_true',
                        help='Show status overview - my channel, competitors, last sync')
    parser.add_argument('--init', action='store_true',
                        help='Interactive setup wizard for first-time users')

    args = parser.parse_args()

    api_key = args.api_key or os.environ.get('YOUTUBE_API_KEY')
    if not api_key:
        print("❌ No API key. Set YOUTUBE_API_KEY or use --api-key")
        print("\n🔗 Get free key: https://console.cloud.google.com/apis/credentials")
        sys.exit(1)

    config = load_config(args.config)
    import httplib2
    http = httplib2.Http(disable_ssl_certificate_validation=True)
    youtube = build('youtube', 'v3', developerKey=api_key, http=http)

    # Clear progress mode
    if args.clear_progress:
        clear_progress(args.output)
        print("✅ Cleared saved progress")
        return

    # Watch mode (continuous monitoring)
    if args.watch:
        watchlist = config.get('watchlist', [])
        if not watchlist:
            print("❌ No channels in watchlist. Add to config.yaml")
            sys.exit(1)
        run_watch_mode(youtube, config, interval_hours=args.interval)
        return

    # API Server mode
    if args.api:
        run_api_server(youtube, port=args.port, config=config)
        return

    # Interactive mode
    if args.interactive:
        interactive_mode(youtube)
        return

    # Trend alerts mode
    if args.alerts:
        watchlist = config.get('watchlist', [])
        if not watchlist:
            print("❌ No channels in watchlist. Add to config.yaml")
            sys.exit(1)

        print(f"🔔 Checking {len(watchlist)} channels for alerts...")
        alerts = check_trend_alerts(youtube, watchlist, './output/alerts.db', config)

        if alerts:
            print(f"\n📢 Found {len(alerts)} alerts:\n")
            for alert in alerts:
                print(format_alert_message(alert))

            # Send webhooks if configured
            discord_url = config.get('webhooks', {}).get('discord')
            slack_url = config.get('webhooks', {}).get('slack')

            for alert in alerts:
                msg = format_alert_message(alert)
                if discord_url:
                    send_discord_webhook(discord_url, msg)
                if slack_url:
                    send_slack_webhook(slack_url, msg)
        else:
            print("✅ No new alerts")
        return

    # === COMPETITIVE ANALYSIS COMMANDS ===

    # Status command
    if args.status:
        status = get_status(youtube, config, args.output)
        print(format_status(status))
        return

    # Init wizard
    if args.init:
        run_init_wizard(youtube, args.config, args.output)
        return

    # Set my channel
    if args.set_my_channel:
        result = set_my_channel(args.set_my_channel, args.config, args.output)
        print(f"✅ Set my_channel to: {result['channel']}")
        print(f"   Config saved to: {result['config_path']}")
        return

    # Add competitor
    if args.add_competitor:
        result = add_competitor_to_config(args.add_competitor, args.config)
        if result['status'] == 'added':
            print(f"✅ Added competitor: {result['competitor']}")
        else:
            print(f"ℹ️ Competitor already exists: {result['competitor']}")
        return

    # Remove competitor(s)
    if args.remove_competitor:
        db_path = get_competitive_db_path(args.output)
        print(f"\n🗑️ Removing {len(args.remove_competitor)} competitor(s)...")
        for name in args.remove_competitor:
            result = remove_competitor(db_path, name)
            if result.get('success'):
                print(f"   ✅ Removed: {result['removed']} ({result['videos_removed']} videos deleted)")
            elif result.get('matches'):
                print(f"   ⚠️ Multiple matches for '{name}':")
                for m in result['matches']:
                    print(f"      - {m['title']}")
                print(f"      Be more specific.")
            else:
                print(f"   ❌ {result.get('error', 'Unknown error')}")
        return

    # List competitors
    if args.list_competitors:
        db_path = get_competitive_db_path(args.output)
        my_channel_id, my_channel_title = get_my_channel_id(youtube, config, db_path)

        if not my_channel_id:
            print("❌ my_channel not set. Use --set-my-channel first.")
            sys.exit(1)

        competitors = list_competitors(db_path, my_channel_id)

        print(f"\n📊 Tracked Competitors for {my_channel_title}:\n")
        if competitors:
            print(f"{'#':<3} {'Channel':<35} {'Relevance':<10} {'Source':<15} {'Subscribers':<12}")
            print("-" * 80)
            for i, comp in enumerate(competitors, 1):
                print(f"{i:<3} {comp['title'][:33]:<35} {comp['relevance_score']:.2f}       {comp['discovery_source'] or 'N/A':<15} {comp['subscriber_count']:,}")
        else:
            print("No competitors tracked yet.")
            print("\nAdd competitors with: --add-competitor @ChannelHandle")
            print("Or discover: --discover-competitors")
        return

    # Discover competitors
    if args.discover_competitors:
        result = discover_and_save_competitors(youtube, config, args.output)

        if 'error' in result:
            print(f"❌ {result['error']}")
            sys.exit(1)

        print(f"\n✅ Discovery complete for {result['my_channel']}")
        print(f"   Total discovered: {result['total_discovered']}")
        print(f"   Saved (above threshold): {result['saved']}")

        if result['competitors']:
            print(f"\n   Top competitors found:")
            for comp in result['competitors'][:10]:
                print(f"      • {comp['title']} (relevance: {comp['relevance_score']:.2f})")

        if result.get('search_keywords'):
            print(f"\n   Keywords used: {', '.join(result['search_keywords'][:5])}")
        return

    # Sync command
    if args.sync:
        my_channel = config.get('my_channel')
        if not my_channel:
            print("❌ my_channel not set in config. Use --set-my-channel first.")
            print("   Run --init for guided setup.")
            sys.exit(1)

        print(f"\n🔄 Syncing channels (force_refresh={args.force_refresh})...")
        results = sync_all(youtube, config, args.output, force_refresh=args.force_refresh)

        # Use enhanced summary
        print(format_sync_summary(results))
        return

    # Comments-only sync
    if args.sync_comments:
        if not config.get('comment_sync', {}).get('channels'):
            print("❌ No comment_sync.channels in config (add it to my_channels.yaml).")
            sys.exit(1)
        db_path = get_competitive_db_path(args.output)
        print("\n💬 Syncing comments...")
        result = sync_comments(youtube, config, db_path)
        print(f"\nDone: {result['new_comments']} new comments, {len(result['errors'])} errors")
        return

    # Snapshot command
    if args.snapshot:
        db_path = get_competitive_db_path(args.output)
        migrate_competitive_database(db_path)
        result = take_snapshot(db_path)

        if 'error' in result:
            print(f"❌ {result['error']}")
            sys.exit(1)

        print(f"✅ Snapshot captured: {result['snapshot_date']}")
        print(f"   Videos snapshot: {result['videos_snapshot']} / {result['total_videos']}")
        print(f"   Channels snapshot: {result.get('channels_snapshot', 0)} / {result.get('total_channels', 0)}")
        return

    # Growth-quality command (organic vs algorithm-driven view bump)
    if args.growth_quality:
        db_path = get_competitive_db_path(args.output)
        migrate_competitive_database(db_path)
        target_channel = args.channel
        if not target_channel:
            target_channel = config.get('my_channel')
        if not target_channel:
            print("❌ No channel specified and no my_channel set in config.")
            sys.exit(1)
        channel_id, _ = resolve_channel_id(youtube, target_channel)
        result = analyze_growth_quality(db_path, channel_id)
        print(format_growth_quality(result))
        return

    # Recommend command
    if args.recommend:
        # Use enhanced recommendations with title suggestions
        recommendations = generate_recommendations_with_titles(youtube, config, args.output, top_n=args.top_n)
        print(format_recommendations_with_titles(recommendations))

        if 'error' not in recommendations:
            os.makedirs(args.output, exist_ok=True)

            # Save JSON
            json_path = os.path.join(args.output, 'recommendations.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(recommendations, f, indent=2, ensure_ascii=False)

            # Generate HTML dashboard
            html_path = os.path.join(args.output, 'recommendations.html')
            generate_recommendations_html(recommendations, html_path)

            print(f"\n📁 Saved to:")
            print(f"   • {json_path}")
            print(f"   • {html_path} (open in browser)")
        return

    # Gap analysis command
    if args.gap_analysis:
        analysis = generate_gap_analysis(youtube, config, args.output)
        report = format_gap_analysis(analysis)
        print(report)

        if 'error' not in analysis:
            # Save to file
            output_path = os.path.join(args.output, 'gap_analysis.md')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\n📁 Saved to: {output_path}")
        return

    # === END COMPETITIVE ANALYSIS COMMANDS ===

    if not args.channel and not args.batch:
        parser.error("Provide channel or --batch or --interactive or --api or --alerts or competitive commands")

    since = datetime.strptime(args.since, '%Y-%m-%d') if args.since else None
    until = datetime.strptime(args.until, '%Y-%m-%d') if args.until else None

    try:
        if args.batch:
            # Read channels from file
            with open(args.batch, 'r') as f:
                channels = [l.strip() for l in f if l.strip() and not l.startswith('#')]

            if args.parallel:
                # Parallel batch processing
                print(f"🚀 Processing {len(channels)} channels in parallel ({args.workers} workers)")
                results = process_batch_parallel(
                    youtube, channels, args.output, args.format,
                    config=config, max_workers=args.workers,
                    since=since, until=until, limit=args.limit,
                    min_views=args.min_views, incremental=args.incremental,
                    download_thumbs=args.thumbnails
                )
                print(f"\n✅ Completed {len(results)} channels")
            else:
                # Sequential batch processing
                process_batch(youtube, args.batch, args.output, args.format,
                             config=config, since=since, until=until,
                             limit=args.limit, min_views=args.min_views,
                             incremental=args.incremental, download_thumbs=args.thumbnails)
        else:
            # Add pdf/rss to formats if requested
            formats = list(args.format)
            if args.pdf and 'pdf' not in formats:
                formats.append('pdf')
            if args.rss and 'rss' not in formats:
                formats.append('rss')

            # Use resume-capable analysis if requested
            if args.resume:
                result = analyze_channel_with_resume(
                    youtube, args.channel, args.output, formats,
                    resume=True, since=since, until=until, limit=args.limit,
                    min_views=args.min_views, incremental=args.incremental,
                    download_thumbs=args.thumbnails, analyze_network=args.network,
                    config=config
                )
            else:
                result = analyze_channel(youtube, args.channel, args.output, formats,
                               since=since, until=until, limit=args.limit,
                               min_views=args.min_views, incremental=args.incremental,
                               download_thumbs=args.thumbnails, analyze_network=args.network,
                               config=config)

            # Time comparison (this week vs last week)
            if args.compare and result.get('videos'):
                print("\n📊 Time Period Comparison:")
                comparison = compare_time_periods(result['videos'], result['channel'])
                print(format_time_comparison(comparison))

            # Tag optimization
            if args.tags and result.get('videos'):
                print("\n🏷️ Tag Optimization Analysis:")
                tag_analysis = optimize_tags(result['videos'])
                print(f"\n  Top recommended tags ({len(tag_analysis['recommended_tags'])}):")
                for tag in tag_analysis['recommended_tags'][:15]:
                    print(f"    • {tag}")
                if tag_analysis.get('high_performing_tags'):
                    print(f"\n  High-performing tags (from viral videos):")
                    for tag in tag_analysis['high_performing_tags'][:10]:
                        stats = tag_analysis.get('tag_stats', {}).get(tag, {})
                        virality = stats.get('avg_virality', 0)
                        print(f"    • {tag} (avg virality: {virality:.2f})")

            # White-label report
            if args.white_label and result.get('videos'):
                branding = {
                    'company_name': args.white_label,
                    'logo_url': args.logo,
                    'primary_color': args.primary_color,
                }
                channel_dir = result.get('output_dir', args.output)
                wl_path = os.path.join(channel_dir, f"whitelabel_report.html")
                generate_white_label_html(result['videos'], result['analytics'],
                                         result['channel'], wl_path, branding)
                print(f"\n🏢 White-label report: {wl_path}")

            # Additional features
            if args.ideas:
                print("\n💡 Generating video ideas...")
                ideas = generate_video_ideas(result['videos'], result['analytics'], result.get('neighborhood'))
                print(f"\n📝 Generated {ideas['total_ideas']} video ideas:\n")
                for category, idea_list in ideas['ideas'].items():
                    if idea_list:
                        print(f"  {category.upper()}:")
                        for idea in idea_list[:3]:
                            print(f"    • {idea['idea']}")
                            if idea.get('suggested_title'):
                                print(f"      Title: \"{idea['suggested_title']}\"")

            if args.calendar:
                print("\n📅 Generating content calendar...")
                calendar = build_content_calendar(result['analytics'])
                print(f"\n  Suggested posting days: {', '.join(calendar['posting_days'])}")
                print(f"  Suggested frequency: {calendar['suggested_frequency']}\n")
                print("  Upcoming schedule:")
                for slot in calendar['calendar'][:8]:
                    print(f"    {slot['date']} ({slot['day']}) at {slot['suggested_time']}")

            if args.keywords:
                print(f"\n🔍 Tracking keywords: {', '.join(args.keywords)}")
                channel_id = result['channel']['channel_id']
                channel_dir = result.get('output_dir', args.output)
                db_path = os.path.join(channel_dir, f"data.db")
                rankings = track_keyword_rankings(youtube, args.keywords, channel_id, db_path)
                print(f"\n  In top 10: {rankings['in_top_10']}/{len(args.keywords)}")
                print(f"  In top 50: {rankings['in_top_50']}/{len(args.keywords)}")
                for kw, data in rankings['rankings'].items():
                    pos = data.get('position', 'Not found')
                    print(f"    '{kw}': Position {pos}")

            # Competitor traffic capture analysis
            if args.vs and result.get('videos'):
                print(f"\n🎯 Analyzing traffic opportunities vs {args.vs}...")

                # Analyze competitor channel
                comp_result = analyze_channel(youtube, args.vs, args.output, ['json'],
                                             since=since, until=until, limit=args.limit,
                                             min_views=args.min_views, config=config)

                if comp_result.get('videos'):
                    traffic_analysis = analyze_competitor_traffic_opportunities(
                        result['videos'],
                        result['channel'],
                        comp_result['videos'],
                        comp_result['channel']
                    )

                    # Print analysis
                    print(format_traffic_analysis(traffic_analysis))

                    # Save to comparisons folder
                    safe_your = safe_filename(result['channel']['title'])
                    safe_comp = safe_filename(comp_result['channel']['title'])

                    comparisons_dir = os.path.join(args.output, 'comparisons')
                    os.makedirs(comparisons_dir, exist_ok=True)

                    # JSON
                    analysis_path = os.path.join(comparisons_dir, f"{safe_your}_vs_{safe_comp}.json")
                    with open(analysis_path, 'w', encoding='utf-8') as f:
                        json.dump(traffic_analysis, f, indent=2, ensure_ascii=False)
                    print(f"\n📁 JSON saved: {analysis_path}")

                    # HTML
                    html_path = os.path.join(comparisons_dir, f"{safe_your}_vs_{safe_comp}.html")
                    generate_traffic_analysis_html(traffic_analysis, html_path)

                    # AI-powered recommendations for comparison
                    if args.ai:
                        ai_result = get_ai_recommendations(
                            your_channel=result['channel'],
                            your_analytics=result['analytics'],
                            your_videos=result['videos'],
                            competitor_channel=comp_result['channel'],
                            competitor_analytics=comp_result['analytics'],
                            traffic_analysis=traffic_analysis,
                            output_dir=comparisons_dir,
                        )

                        if ai_result.get('recommendations'):
                            print("\n" + "=" * 60)
                            print("🤖 AI-POWERED RECOMMENDATIONS")
                            print("=" * 60)
                            print(ai_result['recommendations'])

                            # Save to markdown file
                            ai_path = os.path.join(comparisons_dir, f"{safe_your}_vs_{safe_comp}_ai_recommendations.md")
                            save_ai_recommendations(ai_result, ai_path)
                else:
                    print(f"❌ Could not analyze competitor: {args.vs}")

            # AI analysis for single channel (without --vs)
            elif args.ai and result.get('videos'):
                channel_dir = result.get('output_dir', args.output)
                ai_result = get_ai_recommendations(
                    your_channel=result['channel'],
                    your_analytics=result['analytics'],
                    your_videos=result['videos'],
                    output_dir=channel_dir,
                )

                if ai_result.get('recommendations'):
                    print("\n" + "=" * 60)
                    print("🤖 AI-POWERED RECOMMENDATIONS")
                    print("=" * 60)
                    print(ai_result['recommendations'])

                    # Save to markdown file
                    safe_name = safe_filename(result['channel']['title'])
                    ai_path = os.path.join(channel_dir, f"ai_recommendations.md")
                    save_ai_recommendations(ai_result, ai_path)

    except HttpError as e:
        print(f"\n❌ API Error: {e.resp.status}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

