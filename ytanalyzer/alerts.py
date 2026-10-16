"""Trend alerts and watch mode."""

from .common import *
from .fetch import fetch_video_ids_from_playlist, fetch_video_metadata_batch, get_channel_info, resolve_channel_id
from .metrics import calculate_trend_velocity, calculate_virality_score
from .notify import send_discord_webhook, send_slack_webhook

# =============================================================================
# TREND ALERTS SYSTEM
# =============================================================================

def check_trend_alerts(youtube, watchlist: list[str], db_path: str, config: dict = None) -> list[dict]:
    """
    Check watchlist channels for trending/viral videos and new uploads.
    Returns alerts for significant events.
    """
    alerts = []
    config = config or {}

    for channel_id in watchlist:
        try:
            # Get channel info
            try:
                ch_id, ch_title = resolve_channel_id(youtube, channel_id)
            except:
                continue

            channel_info = get_channel_info(youtube, ch_id)

            # Get recent videos (last 7 days)
            video_ids = fetch_video_ids_from_playlist(
                youtube, channel_info['uploads_playlist_id'], limit=20
            )
            videos = fetch_video_metadata_batch(youtube, video_ids, channel_info)

            for v in videos:
                v['virality_score'] = calculate_virality_score(v, channel_info.get('subscriber_count', 1))
                velocity = calculate_trend_velocity(v, channel_info.get('subscriber_count', 1))
                v['velocity'] = velocity

                # Check for alerts
                try:
                    pub_date = datetime.fromisoformat(v['publish_date'].replace('Z', '+00:00'))
                    hours_old = (datetime.now(pub_date.tzinfo) - pub_date).total_seconds() / 3600
                except:
                    hours_old = 999

                # New video alert (< 24 hours)
                if hours_old < 24:
                    alerts.append({
                        'type': 'new_video',
                        'channel': ch_title,
                        'channel_id': ch_id,
                        'video_title': v['title'],
                        'video_id': v['video_id'],
                        'views': v['view_count'],
                        'hours_old': round(hours_old, 1),
                        'url': f"https://www.youtube.com/watch?v={v['video_id']}",
                    })

                # Trending alert (high velocity)
                if velocity['trend_status'] in ['exploding', 'trending']:
                    alerts.append({
                        'type': 'trending',
                        'channel': ch_title,
                        'channel_id': ch_id,
                        'video_title': v['title'],
                        'video_id': v['video_id'],
                        'views': v['view_count'],
                        'velocity_score': velocity['velocity_score'],
                        'trend_status': velocity['trend_status'],
                        'url': f"https://www.youtube.com/watch?v={v['video_id']}",
                    })

                # Viral alert (virality > 2)
                if v['virality_score'] > 2.0 and hours_old < 168:  # Within a week
                    alerts.append({
                        'type': 'viral',
                        'channel': ch_title,
                        'channel_id': ch_id,
                        'video_title': v['title'],
                        'video_id': v['video_id'],
                        'views': v['view_count'],
                        'virality_score': v['virality_score'],
                        'url': f"https://www.youtube.com/watch?v={v['video_id']}",
                    })

        except Exception as e:
            print(f"Error checking {channel_id}: {e}")

    # Deduplicate alerts
    seen = set()
    unique_alerts = []
    for alert in alerts:
        key = f"{alert['type']}_{alert['video_id']}"
        if key not in seen:
            seen.add(key)
            unique_alerts.append(alert)

    return unique_alerts


def format_alert_message(alert: dict) -> str:
    """Format an alert for display/notification."""
    if alert['type'] == 'new_video':
        return f"🆕 NEW: {alert['channel']} posted \"{alert['video_title']}\" ({alert['hours_old']}h ago, {format_number(alert['views'])} views)"
    elif alert['type'] == 'trending':
        return f"📈 TRENDING: \"{alert['video_title']}\" by {alert['channel']} is {alert['trend_status']}!"
    elif alert['type'] == 'viral':
        return f"🔥 VIRAL: \"{alert['video_title']}\" by {alert['channel']} (virality: {alert['virality_score']:.2f})"
    return str(alert)


# =============================================================================
# WATCH MODE - CONTINUOUS MONITORING
# =============================================================================

class WatchMode:
    """Continuous monitoring mode for watchlist channels."""

    def __init__(self, youtube, config: dict, interval_hours: float = 6):
        self.youtube = youtube
        self.config = config
        self.interval = interval_hours * 3600  # Convert to seconds
        self.running = False
        self.seen_alerts = set()  # Track sent alerts to avoid duplicates

    def start(self):
        """Start continuous monitoring."""
        self.running = True
        print(f"\n👁️  WATCH MODE ACTIVE")
        print(f"   Monitoring {len(self.config.get('watchlist', []))} channels")
        print(f"   Check interval: {self.interval / 3600:.1f} hours")
        print(f"   Press Ctrl+C to stop\n")

        # Handle graceful shutdown
        def signal_handler(sig, frame):
            print("\n\n🛑 Stopping watch mode...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)

        check_count = 0
        while self.running:
            check_count += 1
            print(f"\n{'='*50}")
            print(f"🔍 Check #{check_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print('='*50)

            self._run_check()

            if self.running:
                next_check = datetime.now() + timedelta(seconds=self.interval)
                print(f"\n⏰ Next check at {next_check.strftime('%H:%M:%S')}")

                # Sleep in small increments to allow interrupt
                for _ in range(int(self.interval / 10)):
                    if not self.running:
                        break
                    time.sleep(10)

        print("👋 Watch mode stopped")

    def _run_check(self):
        """Run a single monitoring check."""
        watchlist = self.config.get('watchlist', [])
        if not watchlist:
            print("❌ No channels in watchlist")
            return

        alerts = check_trend_alerts(self.youtube, watchlist, './output/watch.db', self.config)

        # Filter out already-seen alerts
        new_alerts = []
        for alert in alerts:
            alert_key = f"{alert['type']}_{alert['video_id']}"
            if alert_key not in self.seen_alerts:
                new_alerts.append(alert)
                self.seen_alerts.add(alert_key)

        if new_alerts:
            print(f"\n📢 {len(new_alerts)} new alert(s):\n")
            for alert in new_alerts:
                msg = format_alert_message(alert)
                print(f"  {msg}")

                # Send webhooks
                discord_url = self.config.get('webhooks', {}).get('discord')
                slack_url = self.config.get('webhooks', {}).get('slack')

                if discord_url:
                    send_discord_webhook(discord_url, msg)
                if slack_url:
                    send_slack_webhook(slack_url, msg)
        else:
            print("✅ No new alerts")

        # Clean old alerts from memory (keep last 1000)
        if len(self.seen_alerts) > 1000:
            self.seen_alerts = set(list(self.seen_alerts)[-500:])


def run_watch_mode(youtube, config: dict, interval_hours: float = 6):
    """Run continuous watch mode."""
    watcher = WatchMode(youtube, config, interval_hours)
    watcher.start()

