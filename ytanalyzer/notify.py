"""Discord and Slack notifications."""

from .common import *

# =============================================================================
# WEBHOOK ALERTS
# =============================================================================

def send_discord_webhook(webhook_url: str, message: str, embeds: list = None) -> bool:
    """Send notification to Discord webhook."""
    try:
        data = {'content': message}
        if embeds:
            data['embeds'] = embeds

        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Discord webhook error: {e}")
        return False


def send_slack_webhook(webhook_url: str, message: str, blocks: list = None) -> bool:
    """Send notification to Slack webhook."""
    try:
        data = {'text': message}
        if blocks:
            data['blocks'] = blocks

        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Slack webhook error: {e}")
        return False


def send_new_video_alert(config: dict, channel_name: str, new_videos: list[dict]) -> None:
    """Send alerts for new videos."""
    if not new_videos:
        return

    message = f"🎬 **{channel_name}** posted {len(new_videos)} new video(s)!\n\n"
    for v in new_videos[:5]:
        message += f"• {v['title']}\n  Views: {format_number(v['view_count'])}\n"
        message += f"  https://youtube.com/watch?v={v['video_id']}\n\n"

    # Discord
    discord_url = config.get('webhooks', {}).get('discord')
    if discord_url:
        send_discord_webhook(discord_url, message)
        print("Sent Discord alert")

    # Slack
    slack_url = config.get('webhooks', {}).get('slack')
    if slack_url:
        send_slack_webhook(slack_url, message.replace('**', '*'))
        print("Sent Slack alert")

