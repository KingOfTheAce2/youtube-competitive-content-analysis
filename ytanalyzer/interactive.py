"""Cron helper and interactive mode."""

from .common import *
from .analyze import analyze_channel, process_batch

def generate_cron_setup(channel: str, output_dir: str) -> str:
    """Generate cron job setup instructions."""
    script_path = os.path.abspath(__file__)

    cron_daily = f"0 9 * * * cd {os.path.dirname(script_path)} && python {script_path} {channel} --incremental -o {output_dir}"
    cron_weekly = f"0 9 * * 1 cd {os.path.dirname(script_path)} && python {script_path} {channel} -o {output_dir}"

    instructions = f"""
# ============================================
# CRON SETUP FOR AUTOMATED MONITORING
# ============================================

# Daily incremental check (9 AM):
{cron_daily}

# Weekly full analysis (Monday 9 AM):
{cron_weekly}

# To install, run: crontab -e
# Then paste the desired line above

# For Windows Task Scheduler, create a task with:
# Program: python
# Arguments: {script_path} {channel} --incremental -o {output_dir}
# Schedule: Daily at 9:00 AM
"""
    return instructions


# =============================================================================
# INTERACTIVE CLI
# =============================================================================

def interactive_mode(youtube) -> None:
    """Interactive CLI mode."""
    print("\n" + "=" * 60)
    print("  YouTube Competitive Analysis - Interactive Mode")
    print("=" * 60)

    config = load_config()

    while True:
        print("\n📋 Menu:")
        print("  1. Analyze a channel")
        print("  2. Compare multiple channels")
        print("  3. Check for new videos (watchlist)")
        print("  4. View cron setup instructions")
        print("  5. Exit")

        choice = input("\nSelect option (1-5): ").strip()

        if choice == '1':
            channel = input("Enter channel (@handle, URL, or ID): ").strip()
            if not channel:
                continue

            output_dir = input("Output directory [./output]: ").strip() or './output'
            do_network = input("Analyze video network & discover competitors? (y/N): ").strip().lower() == 'y'

            try:
                result = analyze_channel(youtube, channel, output_dir,
                                        ['csv', 'json', 'excel', 'sqlite', 'html', 'markdown'],
                                        analyze_network=do_network, config=config)
                print("\n✅ Analysis complete!")
            except Exception as e:
                print(f"\n❌ Error: {e}")

        elif choice == '2':
            channels = []
            print("Enter channels (empty line to finish):")
            while True:
                ch = input("  Channel: ").strip()
                if not ch:
                    break
                channels.append(ch)

            if len(channels) < 2:
                print("Need at least 2 channels")
                continue

            output_dir = input("Output directory [./output]: ").strip() or './output'

            # Create temp file
            temp_file = os.path.join(output_dir, '.temp_channels.txt')
            os.makedirs(output_dir, exist_ok=True)
            with open(temp_file, 'w') as f:
                f.write('\n'.join(channels))

            try:
                process_batch(youtube, temp_file, output_dir,
                             ['csv', 'json', 'excel', 'sqlite', 'html', 'markdown'],
                             config=config)
                os.remove(temp_file)
                print("\n✅ Comparison complete!")
            except Exception as e:
                print(f"\n❌ Error: {e}")

        elif choice == '3':
            watchlist = config.get('watchlist', [])
            if not watchlist:
                print("No watchlist configured in config.yaml")
                continue

            output_dir = config.get('output_dir', './output')
            for channel in watchlist:
                try:
                    print(f"\nChecking {channel}...")
                    analyze_channel(youtube, channel, output_dir,
                                   ['sqlite'], incremental=True, config=config)
                except Exception as e:
                    print(f"Error: {e}")

        elif choice == '4':
            channel = input("Channel to monitor: ").strip()
            output_dir = input("Output directory [./output]: ").strip() or './output'
            print(generate_cron_setup(channel, output_dir))

        elif choice == '5':
            print("\nGoodbye! 👋")
            break

