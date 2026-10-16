"""Local analytics API server."""

from .common import *
from .analytics import generate_analytics
from .fetch import fetch_video_ids_from_playlist, fetch_video_metadata_batch, get_channel_info, resolve_channel_id
from .metrics import calculate_virality_score

# =============================================================================
# API SERVER MODE
# =============================================================================

class AnalyticsAPIHandler(http.server.SimpleHTTPRequestHandler):
    """Simple HTTP handler for API mode."""

    youtube = None
    cache = {}
    config = {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/api/analyze':
            self.handle_analyze(params)
        elif path == '/api/health':
            self.send_json({'status': 'ok', 'timestamp': datetime.now().isoformat()})
        elif path == '/api/channels':
            self.handle_channels(params)
        else:
            self.send_error(404, 'Endpoint not found')

    def handle_analyze(self, params):
        channel = params.get('channel', [None])[0]
        if not channel:
            self.send_json({'error': 'channel parameter required'}, 400)
            return

        cache_key = f"analyze_{channel}"
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if (datetime.now() - cache_time).seconds < 3600:  # 1 hour cache
                self.send_json(data)
                return

        try:
            # Quick analysis without file export
            channel_id, channel_title = resolve_channel_id(self.youtube, channel)
            channel_info = get_channel_info(self.youtube, channel_id)
            video_ids = fetch_video_ids_from_playlist(
                self.youtube, channel_info['uploads_playlist_id'], limit=50
            )
            videos = fetch_video_metadata_batch(self.youtube, video_ids, channel_info)

            for v in videos:
                v['virality_score'] = calculate_virality_score(v, channel_info.get('subscriber_count', 1))

            analytics = generate_analytics(videos, channel_info)

            result = {
                'channel': channel_info,
                'analytics': analytics,
                'video_count': len(videos),
                'timestamp': datetime.now().isoformat(),
            }

            self.cache[cache_key] = (datetime.now(), result)
            self.send_json(result)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def handle_channels(self, params):
        # List cached channels
        channels = list(set(k.replace('analyze_', '') for k in self.cache.keys() if k.startswith('analyze_')))
        self.send_json({'channels': channels, 'count': len(channels)})

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def log_message(self, format, *args):
        pass  # Suppress logging


def run_api_server(youtube, port: int = 8080, config: dict = None):
    """
    Run a simple API server for programmatic access.
    """
    AnalyticsAPIHandler.youtube = youtube
    AnalyticsAPIHandler.config = config or {}

    with socketserver.TCPServer(("", port), AnalyticsAPIHandler) as httpd:
        print(f"\n🌐 API Server running at http://localhost:{port}")
        print(f"   Endpoints:")
        print(f"   - GET /api/health")
        print(f"   - GET /api/analyze?channel=@handle")
        print(f"   - GET /api/channels")
        print(f"\nPress Ctrl+C to stop...")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")

