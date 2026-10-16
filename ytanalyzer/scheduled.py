"""Scheduled report generation."""

from .common import *
from .analyze import analyze_channel

def generate_scheduled_report(youtube, channel_ids: list[str], output_dir: str, config: dict = None) -> dict:
    """
    Generate scheduled reports for multiple channels.
    Designed to be called from cron/scheduler.
    """
    results = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')

    for channel_id in channel_ids:
        try:
            result = analyze_channel(
                youtube, channel_id, output_dir,
                ['json', 'html', 'markdown'],
                config=config
            )
            results.append({
                'channel': channel_id,
                'status': 'success',
                'timestamp': timestamp,
            })
        except Exception as e:
            results.append({
                'channel': channel_id,
                'status': 'error',
                'error': str(e),
                'timestamp': timestamp,
            })

    # Save summary
    summary_path = os.path.join(output_dir, f'scheduled_report_{timestamp}.json')
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)

    return {
        'reports_generated': len([r for r in results if r['status'] == 'success']),
        'errors': len([r for r in results if r['status'] == 'error']),
        'summary_path': summary_path,
    }

