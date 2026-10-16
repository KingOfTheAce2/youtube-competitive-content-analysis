"""Resume support for interrupted analyses."""

from .common import *
from .analyze import analyze_channel

# =============================================================================
# PROGRESS RESUME - SAVE/LOAD STATE
# =============================================================================

PROGRESS_FILE = '.youtube_analyzer_progress.pkl'


def save_progress(data: dict, output_dir: str = './output'):
    """Save analysis progress for later resumption."""
    progress_path = os.path.join(output_dir, PROGRESS_FILE)
    os.makedirs(output_dir, exist_ok=True)

    progress = {
        'timestamp': datetime.now().isoformat(),
        'data': data,
        'version': '1.0',
    }

    with open(progress_path, 'wb') as f:
        pickle.dump(progress, f)

    print(f"💾 Progress saved to {progress_path}")


def load_progress(output_dir: str = './output') -> Optional[dict]:
    """Load saved progress if available."""
    progress_path = os.path.join(output_dir, PROGRESS_FILE)

    if not os.path.exists(progress_path):
        return None

    try:
        with open(progress_path, 'rb') as f:
            progress = pickle.load(f)

        # Check if progress is recent (within 24 hours)
        saved_time = datetime.fromisoformat(progress['timestamp'])
        if (datetime.now() - saved_time).days >= 1:
            print("⚠️ Saved progress is more than 24 hours old, starting fresh")
            return None

        print(f"📂 Found saved progress from {saved_time.strftime('%Y-%m-%d %H:%M')}")
        return progress['data']
    except Exception as e:
        print(f"⚠️ Could not load progress: {e}")
        return None


def clear_progress(output_dir: str = './output'):
    """Clear saved progress file."""
    progress_path = os.path.join(output_dir, PROGRESS_FILE)
    if os.path.exists(progress_path):
        os.remove(progress_path)
        print("🗑️ Progress cleared")


def analyze_channel_with_resume(youtube, channel_input: str, output_dir: str, formats: list[str],
                                 resume: bool = True, **kwargs) -> dict:
    """
    Analyze channel with progress saving for resumption.
    """
    progress_key = f"channel_{hashlib.md5(channel_input.encode()).hexdigest()[:8]}"

    if resume:
        saved = load_progress(output_dir)
        if saved and progress_key in saved:
            print(f"📂 Resuming analysis for {channel_input}")
            # Could implement partial resume here
            # For now, just return saved data
            return saved[progress_key]

    # Run full analysis
    result = analyze_channel(youtube, channel_input, output_dir, formats, **kwargs)

    # Save progress
    progress_data = load_progress(output_dir) or {}
    progress_data[progress_key] = result
    save_progress(progress_data, output_dir)

    return result

