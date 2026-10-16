"""Init wizard and sync summary."""

from .common import *
from .fetch import resolve_channel_id
from .store import add_competitor_to_config, set_my_channel
from .sync import sync_all

def run_init_wizard(youtube, config_path: str = "config.yaml", output_dir: str = "./output") -> dict:
    """
    Interactive setup wizard for first-time users.
    """
    print("")
    print("=" * 60)
    print("  🚀 YOUTUBE COMPETITIVE ANALYSIS - SETUP WIZARD")
    print("=" * 60)
    print("")
    print("Let's set up your competitive analysis in 3 easy steps.")
    print("")

    config = load_config(config_path)
    results = {'my_channel': None, 'competitors': [], 'synced': False}

    # Step 1: My Channel
    print("-" * 40)
    print("STEP 1: Your Channel")
    print("-" * 40)

    current_channel = config.get('my_channel', '')
    if current_channel:
        print(f"Current: {current_channel}")
        use_current = input("Keep this channel? (Y/n): ").strip().lower()
        if use_current != 'n':
            results['my_channel'] = current_channel
        else:
            current_channel = ''

    if not results['my_channel']:
        while True:
            channel = input("Enter your channel handle (e.g., @YourChannel): ").strip()
            if channel:
                if not channel.startswith('@'):
                    channel = '@' + channel
                # Verify channel exists
                print(f"Verifying {channel}...")
                try:
                    channel_id, channel_title = resolve_channel_id(youtube, channel)
                    print(f"✅ Found: {channel_title}")
                    results['my_channel'] = channel
                    set_my_channel(channel, config_path, output_dir)
                    break
                except Exception as e:
                    print(f"❌ Could not find channel: {e}")
                    print("Please try again.")
            else:
                print("Channel handle is required.")

    # Step 2: Competitors
    print("")
    print("-" * 40)
    print("STEP 2: Add Competitors")
    print("-" * 40)
    print("Add 2-3 competitors you want to track.")
    print("(Enter blank to finish)")
    print("")

    existing_competitors = config.get('seed_competitors', [])
    if existing_competitors:
        print(f"Current competitors: {', '.join(existing_competitors)}")
        keep = input("Keep these? (Y/n): ").strip().lower()
        if keep != 'n':
            results['competitors'] = existing_competitors.copy()

    while len(results['competitors']) < 10:
        prompt = f"Competitor #{len(results['competitors'])+1} (or blank to skip): "
        comp = input(prompt).strip()

        if not comp:
            if len(results['competitors']) >= 1:
                break
            print("Add at least 1 competitor for best results.")
            continue

        if not comp.startswith('@'):
            comp = '@' + comp

        print(f"Verifying {comp}...")
        try:
            channel_id, channel_title = resolve_channel_id(youtube, comp)
            print(f"✅ Found: {channel_title}")
            if comp not in results['competitors']:
                results['competitors'].append(comp)
                add_competitor_to_config(comp, config_path)
        except Exception as e:
            print(f"❌ Could not find: {e}")

    # Step 3: Initial Sync
    print("")
    print("-" * 40)
    print("STEP 3: Initial Sync")
    print("-" * 40)
    print("Sync your channel and competitors to fetch video data.")
    print("")

    do_sync = input("Run initial sync now? (Y/n): ").strip().lower()
    if do_sync != 'n':
        print("")
        config = load_config(config_path)  # Reload with updates
        sync_results = sync_all(youtube, config, output_dir, force_refresh=False)
        results['synced'] = True

        total_videos = sum(c.get('new_videos', 0) for c in [sync_results.get('my_channel')] + sync_results.get('competitors', []) if c and 'error' not in c)
        print(f"\n✅ Synced {total_videos} videos!")

    # Done!
    print("")
    print("=" * 60)
    print("  ✅ SETUP COMPLETE!")
    print("=" * 60)
    print("")
    print("Next steps:")
    print("  1. Generate recommendations:  python youtube_analyzer.py --recommend")
    print("  2. View full gap analysis:    python youtube_analyzer.py --gap-analysis")
    print("  3. Check status anytime:      python youtube_analyzer.py --status")
    print("")

    return results


def format_sync_summary(results: dict) -> str:
    """Format sync results with 'what's changed' summary."""
    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  SYNC COMPLETE")
    lines.append("=" * 60)

    # My channel
    if results.get('my_channel') and 'error' not in results['my_channel']:
        mc = results['my_channel']
        lines.append("")
        lines.append(f"📺 Your Channel: {mc['title']}")
        lines.append(f"   New videos: {mc['new_videos']}")

    # Competitors summary
    comp_results = [c for c in results.get('competitors', []) if c and 'error' not in c]
    if comp_results:
        lines.append("")
        lines.append(f"🎯 Competitors Synced: {len(comp_results)}")

        # What's new from competitors
        new_competitor_videos = []
        for c in comp_results:
            if c.get('new_videos', 0) > 0:
                new_competitor_videos.append({
                    'channel': c['title'],
                    'count': c['new_videos']
                })

        if new_competitor_videos:
            lines.append("")
            lines.append("📰 What's New from Competitors:")
            for nv in sorted(new_competitor_videos, key=lambda x: x['count'], reverse=True)[:5]:
                lines.append(f"   • {nv['channel']}: {nv['count']} new videos")

    # Totals
    total_new = sum(c.get('new_videos', 0) for c in [results.get('my_channel')] + comp_results if c)
    total_channels = 1 + len(comp_results) if results.get('my_channel') else len(comp_results)

    lines.append("")
    lines.append("-" * 40)
    lines.append(f"Total: {total_new} new videos from {total_channels} channels")

    # Errors
    errors = results.get('errors', [])
    if errors:
        lines.append("")
        lines.append(f"⚠️ Errors: {len(errors)}")
        for err in errors[:3]:
            lines.append(f"   • {err.get('channel', 'Unknown')}: {err.get('error', 'Unknown error')}")

    # Next steps
    if total_new > 0:
        lines.append("")
        lines.append("💡 Run --recommend to see updated opportunities!")

    lines.append("")

    return '\n'.join(lines)

